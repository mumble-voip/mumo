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
    """
    This class combines the basic mumble moderator callbacks with
    server level callbacks for handling source game positional audio
    context and identity information.
    """
    default_game_config = (
                             ('name', str, "%(game)s"),
                             ('servername', str, "%(server)s"),
                             ('teams', commaSeperatedStrings, ["Lobby", "Spectator", "Team one", "Team two", "Team three", "Team four"]),
                             ('restrict', x2bool, True),
                             ('serverregex', re.compile, re.compile("^\[[\w\d\-\(\):]{1,20}\]$")),
                             ('deleteifunused', x2bool, True)
                          )
    
    default_config = {'source':(
                             ('database', str, "source.sqlite"),
                             ('basechannelid', int, 0),
                             ('mumbleservers', commaSeperatedIntegers, []),
                             ('gameregex', re.compile, re.compile("^(tf|dod|cstrike|hl2mp)$")),
                             ('groupprefix', str, "source_")
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
        """
        Makes sure the the plugin is correctly configured once the connection
        to the mumble server is (re-)established.
        """
        cfg = self.cfg()
        manager = self.manager()
        log = self.log()
        log.debug("Register for Server callbacks")
        
        self.meta = manager.getMeta()
        
        servers = set(cfg.source.mumbleservers)
        if not servers:
            servers = manager.SERVERS_ALL
        
        self.users = UserRegistry()
        
        self.validateChannelDB()
        
        manager.subscribeServerCallbacks(self, servers)
        manager.subscribeMetaCallbacks(self, servers)
        
    
    def validateChannelDB(self):
        """
        Makes sure the plugins internal datatbase
        matches the actual state of the servers.
        """
        log = self.log()
        log.debug("Validating channel database")
                
        current_sid = -1
        current_mumble_server = None
        
        for sid, cid, game, server, team in self.db.registeredChannels():
            if current_sid != sid:
                current_mumble_server = self.meta.getServer(sid)
                current_sid = sid
                
            try:
                state = current_mumble_server.getChannelState(cid)
                self.db.mapName(state.name, sid, game, server, team)
                #TODO: Verify ACL?
                
            except self.murmur.InvalidChannelException:
                # Channel no longer exists
                log.debug("(%d) Channel %d no longer exists. Dropped.", sid, cid)
                self.db.dropChannel(sid, cid)
            except AttributeError:
                # Server no longer exists
                assert(current_mumble_server == None)
                log.debug("(%d) Server for channel %d no longer exists. Dropped.", sid, cid)
                self.db.dropChannel(sid, cid)
    
    def disconnected(self): pass
    
    def removeFromGroups(self, mumble_server, session, game, server, team):
        """
        Removes the client from all relevant groups
        """
        sid = mumble_server.id()
        prefix = self.cfg().source.groupprefix
        game_cid = self.db.cidFor(sid, game)
        
        group = prefix + game
        mumble_server.removeUserFromGroup(game_cid, session, group) # Game
        
        group += "_" + server
        mumble_server.removeUserFromGroup(game_cid, session, group) # Server
        
        group += "_" + str(team)
        mumble_server.removeUserFromGroup(game_cid, session, group) # Team 
    
    def addToGroups(self, mumble_server, session, game, server, team):
        """
        Adds the client to all relevant groups
        """
        sid = mumble_server.id()
        prefix = self.cfg().source.groupprefix
        game_cid = self.db.cidFor(sid, game)
        assert(game_cid != None)
        
        group = prefix + game
        mumble_server.addUserToGroup(game_cid, session, group) # Game
        
        group += "_" + server
        mumble_server.addUserToGroup(game_cid, session, group) # Server
        
        group += "_" + str(team)
        mumble_server.addUserToGroup(game_cid, session, group) # Team 
    

    def transitionPresentUser(self, mumble_server, old, new, sid, user_new):
        """
        Transitions a user that has been and is currently playing
        """
        assert(new)
        
        target_cid = self.getOrCreateTargetChannelFor(mumble_server, new)
        
        if user_new:
            self.dlog(sid, new.state, "User started playing: g/s/t %s/%s/%d", new.game, new.server, new.identity["team"])
            self.addToGroups(mumble_server, new.state.session, new.game, new.server, new.identity["team"])
        else:
            assert old
            self.dlog(sid, old.state, "User switched: g/s/t %s/%s/%d", new.game, new.server, new.identity["team"])
            self.removeFromGroups(mumble_server, old.state.session, old.game, old.server, old.identity["team"])
            self.addToGroups(mumble_server, new.state.session, new.game, new.server, new.identity["team"])
        
        return self.moveUser(mumble_server, new, target_cid)


    def transitionGoneUser(self, mumble_server, old, new, sid):
        """
        Transitions a user that played but is no longer doing so now.
        """
        assert(old)
        
        self.users.remove(sid, old.state.session)
        self.removeFromGroups(mumble_server, old.state.session, old.game, old.server, old.identity["team"])
        
        if new:
            bcid = self.cfg().source.basechannelid
            self.dlog(sid, old.state, "User stopped playing. Moving to %d.", bcid)
            self.moveUserToCid(mumble_server, new.state, bcid)
        else:
            self.dlog(sid, old.state, "User gone")
        return True


    def userLeftChannel(self, mumble_server, old, sid):
        """
        User left channel. Make sure we check for vacancy it if the game it
        belongs to is configured that way.
        """
        chan = self.db.channelFor(sid, old.game, old.server, old.identity['team'])
        if chan:
            _, cid, game, _, _ = chan
            if self.getGameConfig(game, "deleteifunused"):
                self.deleteIfUnused(mumble_server, cid)

    def userTransition(self, mumble_server, old, new):
        """
        Handles the transition of the user between given old and new states.
        
        If no old state is available (connect, starting to play, ...) old can be
        None. If an old state is given it is assumed that it is valid.
        
        If no new state is available (disconnect) new can be None. A new state
        can be either valid (playing) or invalid (not or no longer playing).
        
        Depending on the previous and the new state this function performs all
        needed actions.
        """
        sid = mumble_server.id()

        assert(not old or old.valid())
        
        relevant = old or (new and new.valid()) 
        if not relevant:
            return
        
        user_new = not old and new and new.valid()
        user_gone = old and (not new or not new.valid())
        
        if not user_gone:
            moved = self.transitionPresentUser(mumble_server, old, new, sid, user_new)
            
        else:
            moved = self.transitionGoneUser(mumble_server, old, new, sid)
        
        
        if moved and old:
            self.userLeftChannel(mumble_server, old, sid)
                    
    def getGameName(self, game):
        """
        Returns the unexpanded game specific game name template.
        """
        return self.getGameConfig(game, "name")
    
    def getServerName(self, game):
        """
        Returns the unexpanded game specific server name template.
        """
        return self.getGameConfig(game, "servername")
        
    def getTeamName(self, game, index):
        """
        Returns the game specific team name for the given team index.
        If the index is invalid the stringified index is returned.
        """
        try:
            return self.getGameConfig(game, "teams")[index]
        except IndexError:
            return str(index)
    
    def setACLsForGameChannel(self, mumble_server, game_cid, game):
        """
        Sets the appropriate ACLs for a game channel for the given cid.
        """
        # Shorthands
        ACL = self.murmur.ACL
        EAT = self.murmur.PermissionEnter | self.murmur.PermissionTraverse # Enter And Traverse
        W = self.murmur.PermissionWhisper # Whisper
        S = self.murmur.PermissionSpeak # Speak
        
        groupname = '~' + self.cfg().source.groupprefix + game
        
        mumble_server.setACL(game_cid,
                          [ACL(applyHere = True, # Deny everything
                               applySubs = True,
                               userid = -1,
                               group = 'all',
                               deny = EAT | W | S),
                           ACL(applyHere = True, # Allow enter and traverse to players
                               applySubs = False,
                               userid = -1,
                               group = groupname,
                               allow = EAT)],
                           [], True)
    

    def setACLsForServerChannel(self, mumble_server, server_cid, game, server):
        """
        Sets the appropriate ACLs for a server channel for the given cid.
        """
        # Shorthands
        ACL = self.murmur.ACL
        EAT = self.murmur.PermissionEnter | self.murmur.PermissionTraverse # Enter And Traverse
        W = self.murmur.PermissionWhisper # Whisper
        S = self.murmur.PermissionSpeak # Speak
        
        groupname = '~' + self.cfg().source.groupprefix + game + "_" + server
        
        mumble_server.setACL(server_cid,
                          [ACL(applyHere = True, # Allow enter and traverse to players
                               applySubs = False,
                               userid = -1,
                               group = groupname,
                               allow = EAT)],
                           [], True)
        

    def setACLsForTeamChannel(self, mumble_server, team_cid, game, server, team):
        """
        Sets the appropriate ACLs for a team channel for the given cid.
        """
        # Shorthands
        ACL = self.murmur.ACL
        EAT = self.murmur.PermissionEnter | self.murmur.PermissionTraverse # Enter And Traverse
        W = self.murmur.PermissionWhisper # Whisper
        S = self.murmur.PermissionSpeak # Speak
        
        groupname = '~' + self.cfg().source.groupprefix + game + "_" + server + "_" + str(team)
        
        mumble_server.setACL(team_cid,
                          [ACL(applyHere = True, # Allow enter and traverse to players
                               applySubs = False,
                               userid = -1,
                               group = groupname,
                               allow = EAT | W | S)],
                           [], True)

    def getOrCreateGameChannelFor(self, mumble_server, game, server, sid, cfg, log, namevars):
        """
        Helper function for getting or creating only the game channel. Returns
        the cid of the exisitng or created game channel.
        """
        sid = mumble_server.id()
        game_cid = self.db.cidFor(sid, game)
        if game_cid == None:
            game_channel_name = self.db.nameFor(sid, game,
                                                default = (self.getGameName(game) % namevars))
            
            log.debug("(%d) Creating game channel '%s' below %d", sid, game_channel_name, cfg.source.basechannelid)
            game_cid = mumble_server.addChannel(game_channel_name, cfg.source.basechannelid)
            self.db.registerChannel(sid, game_cid, game) # Make sure we don't have orphaned server channels around
            self.db.unregisterChannel(sid, game, server)
            
            if self.getGameConfig(game, "restrict"):
                log.debug("(%d) Setting ACL's for new game channel (cid %d)", sid, game_cid)
                self.setACLsForGameChannel(mumble_server, game_cid, game)
            
            log.debug("(%d) Game channel created and registered (cid %d)", sid, game_cid)
        return game_cid


    def getOrCreateServerChannelFor(self, mumble_server, game, server, team, sid, log, namevars, game_cid):
        """
        Helper function for getting or creating only the server channel. The game
        channel must already exist. Returns the cid of the existing or created
        server channel.
        """
        server_cid = self.db.cidFor(sid, game, server)
        if server_cid == None:
            server_channel_name = self.db.nameFor(sid, game, server,
                                                  default = self.getServerName(game) % namevars)
            
            log.debug("(%d) Creating server channel '%s' below %d", sid, server_channel_name, game_cid)
            server_cid = mumble_server.addChannel(server_channel_name, game_cid)
            self.db.registerChannel(sid, server_cid, game, server)
            self.db.unregisterChannel(sid, game, server, team) # Make sure we don't have orphaned team channels around
            
            if self.getGameConfig(game, "restrict"):
                log.debug("(%d) Setting ACL's for new server channel (cid %d)", sid, server_cid)
                self.setACLsForServerChannel(mumble_server, server_cid, game, server)
            
            log.debug("(%d) Server channel created and registered (cid %d)", sid, server_cid)
        return server_cid


    def getOrCreateTeamChannelFor(self, mumble_server, game, server, team, sid, log, server_cid):
        """
        Helper function for getting or creating only the team channel. Game and
        server channel must already exist. Returns the cid of the existing or
        created team channel.
        """
        
        team_cid = self.db.cidFor(sid, game, server, team)
        if team_cid == None:
            team_channel_name = self.db.nameFor(sid, game, server, team,
                                                default = self.getTeamName(game, team))
            
            log.debug("(%d) Creating team channel '%s' below %d", sid, team_channel_name, server_cid)
            team_cid = mumble_server.addChannel(team_channel_name, server_cid)
            self.db.registerChannel(sid, team_cid, game, server, team)
            
            if self.getGameConfig(game, "restrict"):
                log.debug("(%d) Setting ACL's for new team channel (cid %d)", sid, team_cid)
                self.setACLsForTeamChannel(mumble_server, team_cid, game, server, team)
            
            log.debug("(%d) Team channel created and registered (cid %d)", sid, team_cid)
        return team_cid

    def getOrCreateChannelFor(self, mumble_server, game, server, team):
        """
        Checks whether a requested team channel already exists. If not
        all missing parts of the channel structure are created. Returns
        the cid of the existing or created team channel.
        """
        sid = mumble_server.id()
        cfg = self.cfg()
        log = self.log()
        
        namevars = {'game' : game,
                    'server' : server}
        
        game_cid = self.getOrCreateGameChannelFor(mumble_server, game, server, sid, cfg, log, namevars)
        server_cid = self.getOrCreateServerChannelFor(mumble_server, game, server, team, sid, log, namevars, game_cid)
        team_cid = self.getOrCreateTeamChannelFor(mumble_server, game, server, team, sid, log, server_cid)
        
        return team_cid
    
    def moveUserToCid(self, server, state, cid):
        """
        Low level helper for moving a user to a channel known by its ID
        """
        self.dlog(server.id(), state, "Moving from channel %d to %d", state.channel, cid)
        state.channel = cid
        server.setState(state)
        
    def getOrCreateTargetChannelFor(self, mumble_server, user):
        """
        Returns the cid of the target channel for this user. If needed
        missing channels will be created.
        """
        return self.getOrCreateChannelFor(mumble_server,
                                          user.game,
                                          user.server,
                                          user.identity["team"])
        
    def moveUser(self, mumble_server, user, target_cid = None):
        """
        Move user according to current game state.
        
        This function performs all tasks of the move including creating
        channels if needed or deleting unused ones when appropriate.
        If a target_cid is given it is assumed that the channel
        structure is already present.
        """
        state = user.state
        game = user.game
        server = user.server
        team = user.identity["team"]
        sid = mumble_server.id()
        
        source_cid = state.channel
        
        if target_cid == None:
            target_cid = self.getOrCreateChannelFor(mumble_server, game, server, team)
        
        if source_cid != target_cid:
            self.moveUserToCid(mumble_server, state, target_cid)
            user.state.channel = target_cid
            self.users.addOrUpdate(sid, state.session, user)
            
            return True
        
        return False
    
    def deleteIfUnused(self, mumble_server, cid):
        """
        Takes the cid of a server or team channel and checks if all
        related channels (siblings and server) are unused. If true
        the channel is unused and will be deleted.
        
        Note: Assumes tree structure
        """
        
        sid = mumble_server.id()
        log = self.log()
        
        result = self.db.channelForCid(sid, cid)
        if not result:
            return False
        
        _, _, cur_game, cur_server, cur_team = result
        assert(cur_game)
        
        if not cur_server:
            # Don't handle game channels
            log.debug("(%d) Delete if unused on game channel %d, ignoring", sid, cid)
            return False
        
        server_channel_cid = None
        relevant = self.db.channelsFor(sid, cur_game, cur_server)
        
        for _, cur_cid, _, _, cur_team in relevant:
            if cur_team == self.db.NO_TEAM:
                server_channel_cid = cur_cid
                
            if self.users.usingChannel(sid, cur_cid):
                log.debug("(%d) Delete if unused: Channel %d in use", sid, cur_cid)
                return False # Used
        
        assert(server_channel_cid != None)
        
        # Unused. Delete server and children
        log.debug("(%s) Channel %d unused. Will be deleted.", sid, server_channel_cid)
        mumble_server.removeChannel(server_channel_cid)
        return True

    def isValidGameType(self, game):
        return self.cfg().source.gameregex.match(game) != None
    
    def isValidServer(self, game, server):
        return self.getGameConfig(game, "serverregex").match(server) != None
    
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
            
            if not self.isValidGameType(game) or not self.isValidServer(game, server):
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
            d = {}
            for k, v in [var.split(':', 1) for var in identity.split(';')]:
                d[k] = int(v)
            
            # Make sure mandatory values are present
            if not "team" in d: return None
            
            return d 
        except (AttributeError, ValueError):
            return None
           
    def getGameConfig(self, game, variable):
        """
        Return the game specific value for the given variable if it exists. Otherwise the generic value
        """
        
        sectionname = "game:" + game
        cfg = self.cfg()

        if sectionname not in cfg:
            return cfg.generic[variable]
        
        return cfg[sectionname][variable]
        
    def dlog(self, sid, state, what, *argc):
        """ Debug log output helper for user state related things """
        self.log().debug("(%d) (%d|%d) " + what, sid, state.session, state.userid, *argc)
        
    def handle(self, server, new_state):
        """
        Takes the updated state of the user and collects all
        other required data to perform a state transition for
        this user.
        """
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
        self.dlog(sid, new_state, "Context: %s -> '%s' / '%s'", repr(new_state.context), game, game_server)
        self.dlog(sid, new_state, "Identity: %s -> '%s'", repr(new_state.identity), identity)
        
        updated_user = User(new_state, identity, game, game_server)
        
        self.dlog(sid, new_state, "Starting transition")
        self.userTransition(server, old_user, updated_user)
        self.dlog(sid, new_state, "Transition complete")
    
    #
    #--- Server callback functions
    #
    
    def userDisconnected(self, server, state, context=None):
        """
        Handle disconnect to be able to delete unused channels
        and remove user from internal accounting.
        """
        sid = server.id()
        session = state.session
        
        self.userTransition(server, self.users.get(sid, session), None)
         
    def userStateChanged(self, server, state, context=None):
        """
        Default state change for user. Could be something uninteresting for
        the plugin like mute/unmute but or something relevant like the context
        string change triggered by starting to play.
        """
        self.handle(server, state)
        
    def userConnected(self, server, state, context=None):
        """
        First time we see the state for a user. userStateChanged behavior
        applies.
        """
        self.handle(server, state)
        
    def channelRemoved(self, server, state, context=None):
        """
        Updates internal accounting for channels controlled by the plugin.
        """
        cid = state.id
        sid = server.id()
        
        self.log().debug("(%d) Channel %d removed.", sid, cid)
        self.db.dropChannel(sid, cid)

    def channelStateChanged(self, server, state, context=None):
        """
        Updates channel name mappings when needed.
        """
        cid = state.id
        sid = server.id()
        name = state.name
        channel = self.db.channelForCid(sid, cid)
        if channel:
            _, _, game, server, team = channel
            self.db.mapName(name, sid, game, server, team)
            self.log().debug("(%d) Name mapping for channel %d updated to '%s'", sid, cid, name)
            
    def userTextMessage(self, server, user, message, current=None): pass
    def channelCreated(self, server, state, context=None): pass

    
    #
    #--- Meta callback functions
    #

    def started(self, server, context=None):
        self.log().debug("Started")
        
    def stopped(self, server, context=None):
        self.log().debug("Stopped")
