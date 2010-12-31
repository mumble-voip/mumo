#!/usr/bin/env python
# -*- coding: utf-8

# Copyright (C) 2010 Stefan Hacker <dd0t@users.sourceforge.net>
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
# bf2.py
# This module manages ACL/channel movements based on battlefield 2
# gamestate reported by Mumble positional audio plugins
#

from mumo_module import MumoModule

import re
try:
    import json
except ImportError: # Fallback for python < 2.6
    import simplejson as json

class bf2(MumoModule):
    default_config = {'bf2':(
                             ('gamecount', int, 1),
                             ),
                      lambda x: re.match('g\d+', x):(
                             ('name', str, ''),
                             ('mumble_server', int, 1),
                             ('ipport_filter', re.compile, re.compile('.*')),
                             
                             ('base', int, 0),
                             ('left', int, -1),
                             
                             ('blufor', int, -1),
                             ('blufor_commander', int, -1),
                             ('blufor_no_squad', int, -1),
                             ('blufor_alpha_squad', int, -1),
                             ('blufor_alpha_squad_leader', int, -1),
                             ('blufor_bravo_squad', int, -1),
                             ('blufor_bravo_squad_leader', int, -1),
                             ('blufor_charlie_squad', int, -1),
                             ('blufor_charlie_squad_leader', int, -1),
                             ('blufor_delta_squad', int, -1),
                             ('blufor_delta_squad_leader', int, -1),
                             ('blufor_echo_squad', int, -1),
                             ('blufor_echo_squad_leader', int, -1),
                             ('blufor_foxtrot_squad', int, -1),
                             ('blufor_foxtrot_squad_leader', int, -1),
                             ('blufor_golf_squad', int, -1),
                             ('blufor_golf_squad_leader', int, -1),
                             ('blufor_hotel_squad', int, -1),
                             ('blufor_hotel_squad_leader', int, -1),
                             ('blufor_india_squad', int, -1),
                             ('blufor_india_squad_leader', int, -1),
                             
                             ('opfor', int, -1),
                             ('opfor_commander', int, -1),
                             ('opfor_no_squad', int, -1),
                             ('opfor_alpha_squad', int, -1),
                             ('opfor_alpha_squad_leader', int, -1),
                             ('opfor_bravo_squad', int, -1),
                             ('opfor_bravo_squad_leader', int, -1),
                             ('opfor_charlie_squad', int, -1),
                             ('opfor_charlie_squad_leader', int, -1),
                             ('opfor_delta_squad', int, -1),
                             ('opfor_delta_squad_leader', int, -1),
                             ('opfor_echo_squad', int, -1),
                             ('opfor_echo_squad_leader', int, -1),
                             ('opfor_foxtrot_squad', int, -1),
                             ('opfor_foxtrot_squad_leader', int, -1),
                             ('opfor_golf_squad', int, -1),
                             ('opfor_golf_squad_leader', int, -1),
                             ('opfor_hotel_squad', int, -1),
                             ('opfor_hotel_squad_leader', int, -1),
                             ('opfor_india_squad', int, -1),
                             ('opfor_india_squad_leader', int, -1)
                             ),
                    }
    
    id_to_squad_name = ["no", "alpha", "bravo", "charlie", "delta", "echo", "foxtrot", "golf", "hotel", "india"]
    
    def __init__(self, name, manager, configuration = None):
        MumoModule.__init__(self, name, manager, configuration)
        self.murmur = manager.getMurmurModule()

    def connected(self):
        cfg = self.cfg()
        manager = self.manager()
        log = self.log()
        log.debug("Register for Server callbacks")
        
        servers = set()
        for i in range(cfg.bf2.gamecount):
            try:
                servers.add(cfg["g%d" % i].mumble_server)
            except KeyError:
                log.error("Invalid configuration. Game configuration for 'g%d' not found.", i)
                return
        
        self.sessions = {} # {serverid:{sessionid:laststate}}
        manager.subscribeServerCallbacks(self, servers)
        manager.subscribeMetaCallbacks(self, servers)
    
    def disconnected(self): pass
    
    #
    #--- Module specific state handling code
    #
    def update_state(self, server, oldstate, newstate):
        log = self.log()
        sid = server.id()
        
        session = newstate.session
        newoldchannel = newstate.channel
        
        try:
            opc = oldstate.parsedcontext
            ogcfgname = opc["gamename"]
            ogcfg = opc["gamecfg"]
            og = ogcfg.name
            opi = oldstate.parsedidentity
        except (AttributeError, KeyError):
            og = None
            
            opi = {}
            opc = {}
            
        if oldstate and oldstate.is_linked:
            oli = True
        else:
            oli = False
        
        try:
            npc = newstate.parsedcontext
            ngcfgname = npc["gamename"]
            ngcfg = npc["gamecfg"]
            ng = ngcfg.name
            npi = newstate.parsedidentity
        except (AttributeError, KeyError):
            ng = None
            
            npi = {}
            npc = {}
            nli = False
        
        if newstate and newstate.is_linked:
            nli = True
        else:
            nli = False
        
        if not oli and nli:
            log.debug("User '%s' (%d|%d) on server %d now linked", newstate.name, newstate.session, newstate.userid, sid)
            server.addUserToGroup(0, session, "bf2_linked")
            
        if opi and opc:
            log.debug("Removing user '%s' (%d|%d) on server %d from groups of game %s", newstate.name, newstate.session, newstate.userid, sid, og or ogcfgname)
            server.removeUserFromGroup(ogcfg["base"], session, "bf2_%s_game" % (og or ogcfgname))
            
            squadname = self.id_to_squad_name[opi["squad"]]
            server.removeUserFromGroup(ogcfg[opi["team"]], session, "bf2_commander")
            server.removeUserFromGroup(ogcfg[opi["team"]], session, "bf2_squad_leader")
            server.removeUserFromGroup(ogcfg[opi["team"]], session, "bf2_%s_squad_leader" % squadname)
            server.removeUserFromGroup(ogcfg[opi["team"]], session, "bf2_%s_squad" % squadname)
            server.removeUserFromGroup(ogcfg[opi["team"]], session, "bf2_team")
            channame = "left"
            newstate.channel = ogcfg["left"]
            
        if npc and npi:
            log.debug("Updating user '%s' (%d|%d) on server %d in game %s: %s", newstate.name, newstate.session, newstate.userid, sid, ng or ngcfgname, str(npi))
            
            squadname = self.id_to_squad_name[npi["squad"]]
            
            # Add to game group
            location = "base"
            group = "bf2_%s_game" % (ng or ngcfgname)
            server.addUserToGroup(ngcfg[location], session, group)
            log.debug("Added '%s' @ %s to group %s in %s", newstate.name, ng or ngcfgname, group, location)
            
            # Then add to team group
            location = npi["team"]
            group = "bf2_team"
            server.addUserToGroup(ngcfg[location], session, group)
            log.debug("Added '%s' @ %s to group %s in %s", newstate.name, ng or ngcfgname, group, location)
            
            # Then add to squad group
            group = "bf2_%s_squad" % squadname
            server.addUserToGroup(ngcfg[location], session, group)
            log.debug("Added '%s' @ %s to group %s in %s", newstate.name, ng or ngcfgname, group, location)
            
            channame = "%s_%s_squad" % (npi["team"], self.id_to_squad_name[npi["squad"]])
            newstate.channel = ngcfg[channame]
            
            if npi["squad_leader"]:
                # In case the leader flag is set add to leader group
                group = "bf2_%s_squad_leader" % squadname
                server.addUserToGroup(ngcfg[location], session, group)
                log.debug("Added '%s' @ %s to group %s in %s", newstate.name, ng or ngcfgname, group, location)
                
                group = "bf2_squad_leader"
                server.addUserToGroup(ngcfg[location], session, group)
                log.debug("Added '%s' @ %s to group %s in %s", newstate.name, ng or ngcfgname, group, location)
                
                # Override previous moves
                channame = "%s_%s_squad_leader" % (npi["team"], self.id_to_squad_name[npi["squad"]])
                newstate.channel = ngcfg[channame]
            
            if npi["commander"]:
                group = "bf2_commander"
                server.addUserToGroup(ngcfg[location], session, group)
                log.debug("Added '%s' @ %s to group %s in %s", newstate.name, ng or ngcfgname, group, location)
                
                # Override previous moves
                channame = "%s_commander" % npi["team"]
                newstate.channel = ngcfg[channame]
                
        if oli and not nli:
            log.debug("User '%s' (%d|%d) on server %d no longer linked", newstate.name, newstate.session, newstate.userid, sid)
            server.removeUserFromGroup(0, session, "bf2_linked")
                
        if newstate.channel >= 0 and newoldchannel != newstate.channel:
            if ng == None:
                log.debug("Moving '%s' leaving %s to channel %s", newstate.name, og or ogcfgname, channame)
            else:
                log.debug("Moving '%s' @ %s to channel %s", newstate.name, ng or ngcfgname, channame)
                
            server.setState(newstate)
        
    def handle(self, server, state):
        def verify(mdict, key, vtype):
            if not isinstance(mdict[key], vtype):
                raise ValueError("'%s' of invalid type" % key)
            
        cfg = self.cfg()
        log = self.log()
        sid = server.id()

        # Add defaults for our variables to state
        state.parsedidentity = {}
        state.parsedcontext = {}
        state.is_linked = False
        
        if sid not in self.sessions: # Make sure there is a dict to store states in
            self.sessions[sid] = {}
        
        update = False
        if state.session in self.sessions[sid]:
            if state.identity != self.sessions[sid][state.session].identity or \
               state.context != self.sessions[sid][state.session].context:
                # identity or context changed => update
                update = True
            else: # id and context didn't change hence the old data must still be valid
                state.is_linked = self.sessions[sid][state.session].is_linked
                state.parsedcontext = self.sessions[sid][state.session].parsedcontext
                state.parsedidentity = self.sessions[sid][state.session].parsedidentity
        else:
            if state.identity or state.context:
                # New user with engaged plugin => update
                self.sessions[sid][state.session] = None
                update = True
                
        if not update:
            self.sessions[sid][state.session] = state
            return
            
        # The plugin will always prefix "Battlefield 2\0" to the context for the bf2 PA plugin
        # don't bother analyzing anything if it isn't there
        splitcontext = state.context.split('\0', 1)
        if splitcontext[0] == "Battlefield 2":
            state.is_linked = True
            if state.identity and len(splitcontext) == 1:
                #LEGACY: Assume broken Ice 3.2 which doesn't transmit context after \0
                splitcontext.append('{"ipport":""}') # Obviously this doesn't give full functionality but it doesn't crash either ;-)

        if state.is_linked and len(splitcontext) == 2 and state.identity: 
            try:
                context = json.loads(splitcontext[1])
                verify(context, "ipport", basestring)
                
                for i in range(cfg.bf2.gamecount):
                    # Try to find a matching game
                    gamename = "g%d" % i
                    gamecfg = getattr(cfg, gamename)
                    if gamecfg.mumble_server == server.id() and \
                        gamecfg.ipport_filter.match(context["ipport"]):
                        break
                    gamename = None
                
                if not gamename:
                    raise ValueError("No matching game found")
                
                context["gamecfg"] = gamecfg
                context["gamename"] = gamename
                state.parsedcontext = context

            except (ValueError, KeyError, AttributeError), e:
                log.debug("Invalid context for %s (%d|%d) on server %d: %s", state.name, state.session, state.userid, sid, repr(e))
        
            try:
                identity = json.loads(state.identity)
                verify(identity, "commander", bool)
                verify(identity, "squad_leader", bool)
                verify(identity, "squad", int)
                if identity["squad"] < 0 or identity["squad"] > 9:
                    raise ValueError("Invalid squad number")
                verify(identity, "team", basestring)
                if identity["team"] != "opfor" and identity["team"] != "blufor":
                    raise ValueError("Invalid team identified")
                #LEGACY: Ice 3.2 cannot handle unicode strings
                identity["team"] = str(identity["team"])
                
                state.parsedidentity = identity
                
            except (KeyError, ValueError), e:
                log.debug("Invalid identity for %s (%d|%d) on server %d: %s", state.name, state.session, state.userid, sid, repr(e))

        # Update state and remember it
        self.update_state(server, self.sessions[sid][state.session], state)
        self.sessions[sid][state.session] = state
    
    #
    #--- Server callback functions
    #
    
    def userDisconnected(self, server, state, context = None):
        try:
            sid = server.id()
            del self.sessions[sid][state.session]
        except KeyError: pass
         
    def userStateChanged(self, server, state, context = None):
        self.handle(server, state)
        
    def userConnected(self, server, state, context = None):
        self.handle(server, state)
    
    def channelCreated(self, server, state, context = None): pass
    def channelRemoved(self, server, state, context = None): pass
    def channelStateChanged(self, server, state, context = None): pass
    
    #
    #--- Meta callback functions
    #

    def started(self, server, context = None):
        self.sessions[server.id()] = {}
        
    def stopped(self, server, context = None):
        self.sessions[server.id()] = {}
