#!/usr/bin/env python
# -*- coding: utf-8

# Copyright (C) 2013 Stefan Hacker <dd0t@users.sourceforge.net>
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:

# - Redistributions of source code must retain the above copyright notice,
#   this list of conditions and the following disclaimer.
# - Redistributions in binary form must reproduce the above copyright notice,
#   this list of conditions and the following disclaimer in the documentation
#   and/or other materials provided with the distribution.
# - Neither the name of the Mumble Developers nor the names of its
#   contributors may be used to endorse or promote products derived from this
#   software without specific prior written permission.

# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# `AS IS'' AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED.  IN NO EVENT SHALL THE FOUNDATION OR
# CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
# EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
# PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR
# PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF
# LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
# NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

#
# source.py
# This module manages ACL/channel movements based on source
# gamestate reported by Mumble positional audio plugins
#

from mumo_module import (MumoModule,
                         commaSeperatedIntegers,
                         commaSeperatedStrings,
                         x2bool)

from db import SourceDB
from users import (User, UserRegistry)

import re
    
class source(MumoModule):
    default_game_config = (
                             ('name', str, "%(game)s"),
                             ('servername', str, "%(server)s"),
                             ('teams', commaSeperatedStrings, ["Lobby", "Spectator", "Team one", "Team two", "Team three", "Team four"]),
                             ('groups', commaSeperatedStrings, ["%(game)s", "%(game)s_%(team)s", "%(game)s_%(team)s_%(channelid)d"]),
                             ('restrict', x2bool, True),
                             ('serverregex', re.compile, re.compile("^\[[\w\d\-\(\):]{1,20}\]$")),
                             ('createifmissing', x2bool, True),
                             ('deleteifunused', x2bool, False) 
                          )
    
    default_config = {'source':(
                             ('database', str, "source.sqlite"),
                             ('basechannelid', int, 0),
                             ('servers', commaSeperatedIntegers, []),
                             ('gameregex', re.compile, re.compile("^(tf|dod|cstrike)$"))
                             ),
                      
                      # The generic section defines default values which can be overridden in
                      # optional game specific "game:<gameshorthand>" sections

                      'generic': default_game_config,
                      lambda x: re.match('^game:\w+$', x): default_game_config
                      
                    }
    
    def __init__(self, name, manager, configuration=None):
        MumoModule.__init__(self, name, manager, configuration)
        self.murmur = manager.getMurmurModule()

    def onStart(self):
        MumoModule.onStart(self)
        cfg = self.cfg()
        self.db = SourceDB(cfg.source.database)
    
    def onStop(self):
        MumoModule.onStop(self)
        self.db.close()
        
    def connected(self):
        cfg = self.cfg()
        manager = self.manager()
        log = self.log()
        log.debug("Register for Server callbacks")
        
        self.meta = manager.getMeta()
        
        servers = set(cfg.source.servers)
        if not servers:
            servers = manager.SERVERS_ALL
        
        self.users = UserRegistry()
        
        self.validateChannelDB()
        
        manager.subscribeServerCallbacks(self, servers)
        manager.subscribeMetaCallbacks(self, servers)
        
    
    def validateChannelDB(self):
        log = self.log()
        log.debug("Validating channel database")
                
        current_sid = -1
        current_mumble_server = None
        
        for sid, cid, _, _, _ in self.db.registeredChannels():
            if current_sid != sid:
                current_mumble_server = self.meta.getServer(sid)
                current_sid = sid
                
            try:
                current_mumble_server.getChannelState(cid)
                #TODO: Verify ACL?
            except self.murmur.InvalidChannelException:
                # Channel no longer exists
                log.debug("(%d) Channel %d no longer exists. Dropped.", sid, cid)
                self.db.dropChannel(sid, cid)
    
    def disconnected(self): pass
    
    def userTransition(self, server, old, new):
        sid = server.id()

        assert(not old or old.valid())
                
        relevant = old or (new and new.valid()) 
        if not relevant:
            return
        
        user_new = not old and new
        user_gone = old and (not new or not new.valid())
        
        if not user_new:
            # Nuke previous group memberships if any
            
            #TODO: Remove group memberships
            
            pass
        
        if not user_gone:
            #TODO: Establish new group memberships
            self.moveUser(server,
                          new.state,
                          new.game,
                          new.server,
                          new.identity["team"])
        else:
            # User gone
            if not new:
                self.dlog(sid, old.state, "User gone")
            else:
                self.dlog(sid, old.state, "User stopped playing")
    
    
    def getGameName(self, game):
        return self.gameCfg(game, "name")
    
    def getServerName(self, game):
        return self.gameCfg(game, "servername")
        
    def getTeamName(self, game, index):
        try:
            return self.gameCfg(game, "teams")[index]
        except IndexError:
            return str(index)
    

    def getOrCreateGameChannelFor(self, mumble_server, game, server, sid, cfg, log, namevars):
        game_cid = self.db.cidFor(sid, game)
        if game_cid == None:
            game_channel_name = self.getGameName(game) % namevars
            log.debug("(%d) Creating game channel '%s' below %d", sid, game_channel_name, cfg.source.basechannelid)
            game_cid = mumble_server.addChannel(game_channel_name, cfg.source.basechannelid)
            self.db.registerChannel(sid, game_cid, game) # Make sure we don't have orphaned server channels around
            self.db.unregisterChannel(sid, game, server)
            log.debug("(%d) Game channel created and registered (cid %d)", sid, game_cid)
        return game_cid


    def getOrCreateServerChannelFor(self, mumble_server, game, server, team, sid, log, namevars, game_cid):
        server_cid = self.db.cidFor(sid, game, server)
        if server_cid == None:
            server_channel_name = self.getServerName(game) % namevars
            log.debug("(%d) Creating server channel '%s' below %d", sid, server_channel_name, game_cid)
            server_cid = mumble_server.addChannel(server_channel_name, game_cid)
            self.db.registerChannel(sid, server_cid, game, server)
            self.db.unregisterChannel(sid, game, server, team) # Make sure we don't have orphaned team channels around
            log.debug("(%d) Server channel created and registered (cid %d)", sid, server_cid)
        return server_cid


    def getOrCreateTeamChannelFor(self, mumble_server, game, server, team, sid, log, server_cid):
        team_cid = self.db.cidFor(sid, game, server, team)
        if team_cid == None:
            team_channel_name = self.getTeamName(game, team)
            log.debug("(%d) Creating team channel '%s' below %d", sid, team_channel_name, server_cid)
            team_cid = mumble_server.addChannel(team_channel_name, server_cid)
            self.db.registerChannel(sid, team_cid, game, server, team)
            log.debug("(%d) Team channel created and registered (cid %d)", sid, team_cid)
        return team_cid

    def getOrCreateChannelFor(self, mumble_server, game, server, team):
        sid = mumble_server.id()
        cfg = self.cfg()
        log = self.log()
        
        #TODO: Apply ACLs if needed
        #TODO: Make robust against channel changes not in the db
        
        namevars = {'game' : game,
                    'server' : server}
        
        game_cid = self.getOrCreateGameChannelFor(mumble_server, game, server, sid, cfg, log, namevars)
        server_cid = self.getOrCreateServerChannelFor(mumble_server, game, server, team, sid, log, namevars, game_cid)
        team_cid = self.getOrCreateTeamChannelFor(mumble_server, game, server, team, sid, log, server_cid)
        
        return team_cid
    
    def moveUserToCid(self, server, state, cid):
        self.dlog(server.id(), state, "Moving from channel %d to %d", state.channel, cid)
        state.channel = cid
        server.setState(state)
        
    def moveUser(self, mumble_server, state, game, server, team):
        source_cid = state.channel
        target_cid = self.getOrCreateChannelFor(mumble_server, game, server, team)
        if source_cid != target_cid:
            self.moveUserToCid(mumble_server, state, target_cid)
        
        # TODO: Source channel deletion if unused
            
        return True
               
    def validGameType(self, game):
        return self.cfg().source.gameregex.match(game) != None
    
    def validServer(self, game, server):
        return self.gameCfg(game, "serverregex").match(server) != None
    
    def parseSourceContext(self, context):
        """
        Parse source engine context string. Returns tuple with
        game name and server identification. Returns None for both 
        if context string is invalid.
        """
        try:
            prefix, server = context.split('\x00')[0:2]
            source, game = [s.strip() for s in prefix.split(':', 1)]
            
            if source != "Source engine":
                # Not a source engine context
                return (None, None)
            
            if not self.validGameType(game) or not self.validServer(game, server):
                return (None, None)
            
            return (game, server)
            
        except (AttributeError, ValueError),e:
            return (None, None);
    
    def parseSourceIdentity(self, identity):
        """
        Parse comma separated source engine identity string key value pairs
        and return them as a dict. Returns None for invalid identity strings.
        
        Usage: parseSourceIndentity("universe:0;account_type:0;id:00000000;instance:0;team:0")    
        """
        try:
            # For now all values are integers
            d = {k:int(v) for k, v in [var.split(':', 1) for var in identity.split(';')]}
            
            # Make sure mandatory values are present
            if not "team" in d: return None
            
            return d 
        except (AttributeError, ValueError):
            return None
           
    def gameCfg(self, game, variable):
        """Return the game specific value for the given variable if it exists. Otherwise the generic value"""
        sectionname = "game:" + game
        cfg = self.cfg()

        if sectionname not in cfg:
            return cfg.generic[variable]
        
        return cfg[sectionname][variable]
        
    def dlog(self, sid, state, what, *argc):
        """ Debug log output helper for user state related things """
        self.log().debug("(%d) (%d|%d) " + what, sid, state.session, state.userid, *argc)
        
    def handle(self, server, new_state):
        log = self.log()
        sid = server.id()
        session = new_state.session
        
        self.dlog(sid, new_state, "Handle state change")
        
        old_user = self.users.get(sid, session)
        
        if old_user and not old_user.hasContextOrIdentityChanged(new_state):
            # No change in relevant fields. Simply update state for reference
            old_user.updateState(new_state)
            self.dlog(sid, new_state, "State change irrelevant for plugin")
            return
        
        game, game_server = self.parseSourceContext(new_state.context)
        identity = self.parseSourceIdentity(new_state.identity)
        self.dlog(sid, new_state, "Context: '%s' -> '%s'", game, game_server)
        self.dlog(sid, new_state, "Identity: '%s'", identity)
        
        updated_user = User(new_state, identity, game, game_server)
        
        self.dlog(sid, new_state, "Starting transition")
        self.userTransition(server, old_user, updated_user)
        
        if updated_user.valid():
            self.users.addOrUpdate(sid, session, updated_user)
            self.dlog(sid, new_state, "Transition completed")
        else:
            # User isn't relevant for this plugin        
            self.users.remove(sid, session)
            self.dlog(sid, new_state, "User not of concern for plugin")
            
    #
    #--- Server callback functions
    #
    
    def userDisconnected(self, server, state, context=None):
        sid = server.id()
        session = state.session
        
        self.userTransition(server, self.users.get(sid, session), None)
         
    def userStateChanged(self, server, state, context=None):
        self.handle(server, state)
        
    def userConnected(self, server, state, context=None):
        self.handle(server, state)
        
    def channelRemoved(self, server, state, context=None):
        cid = state.id
        sid = server.id()
        
        self.log().debug("(%d) Channel %d removed.", sid, cid)
        self.db.dropChannel(sid, cid)
    
    def userTextMessage(self, server, user, message, current=None): pass
    def channelCreated(self, server, state, context=None): pass
    def channelStateChanged(self, server, state, context=None): pass
    
    #
    #--- Meta callback functions
    #

    def started(self, server, context=None):
        self.log().debug("Started")
        
    def stopped(self, server, context=None):
        self.log().debug("Stopped")
