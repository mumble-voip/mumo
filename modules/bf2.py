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

from mumo_module import (x2bool,
                         MumoModule)

import re
from xml.etree import ElementTree
from xml.parsers.expat import ExpatError

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
                servers.add(getattr(cfg, "g%d" % i).mumble_server)
            except AttributeError:
                log.error("Invalid configuration. Game configuration for 'g%d' not found.", i)
                return
        
        self.sessions = {} # {sid:laststae}
        manager.subscribeServerCallbacks(self, servers)
        manager.subscribeMetaCallbacks(self, servers)
    
    def disconnected(self): pass
    
    #
    #--- Server callback functions
    #
    
    def update_state(self, server, oldstate, newstate):
        log = self.log()
        sid = server.id()
        
        session  = newstate.session
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
        
        if (opi != npi or opc != opi) and opi and opc:
            log.debug("Removing user '%s' (%d|%d) on server %d from groups of game %s", newstate.name, newstate.session, newstate.userid, sid, og or ogcfgname)
            server.removeUserFromGroup(ogcfg.base, session, "bf2%s_%s_commander" % (og, opi["team"]))
            server.removeUserFromGroup(ogcfg.base, session, "bf2%s_%s_%s_squad_leader" % (og, opi["team"], self.id_to_squad_name[opi["squad"]]))
            server.removeUserFromGroup(ogcfg.base, session, "bf2%s_%s_%s_squad" % (og, opi["team"], self.id_to_squad_name[opi["squad"]]))
            server.removeUserFromGroup(ogcfg.base, session, "bf2%s_%s" % (og, opi["team"]))
            
            channame = "left"
            newstate.channel = ogcfg.left
        
        if npc and npi:
            log.debug("Updating user '%s' (%d|%d) on server %d in game %s: %s", newstate.name, newstate.session, newstate.userid, sid, ng or ngcfgname, str(npi))
            
            # First add to team group
            group = "bf2%s_%s" % (ng, npi["team"])
            server.addUserToGroup(ngcfg.base, session, group)
            log.debug("Added '%s' @ %s to group %s", newstate.name, ng or ngcfgname, group)
            
            # Then add to squad group
            group = "bf2%s_%s_%s_squad" % (ng, npi["team"], self.id_to_squad_name[npi["squad"]])
            server.addUserToGroup(ngcfg.base, session, group)
            log.debug("Added '%s' @ %s to group %s", newstate.name, ng or ngcfgname, group)
            
            channame = "%s_%s_squad" % (npi["team"], self.id_to_squad_name[npi["squad"]])
            newstate.channel = getattr(ngcfg, channame)
            
            if npi["is_leader"]:
                # In case the leader flag is set add to leader group
                group = "bf2%s_%s_%s_squad_leader" % (ng, npi["team"], self.id_to_squad_name[npi["squad"]])
                server.addUserToGroup(ngcfg.base, session, group)
                log.debug("Added '%s' @ %s to group %s", newstate.name, ng or ngcfgname, group)
                
                # Override previous moves
                channame = "%s_%s_squad_leader" % (npi["team"], self.id_to_squad_name[npi["squad"]])
                newstate.channel = getattr(ngcfg, channame)


            if npi["is_commander"]:
                group = "bf2%s_%s_commander" % (ng, npi["team"])
                server.addUserToGroup(ngcfg.base, session, group)
                log.debug("Added '%s' @ %s to group %s", newstate.name, ng or ngcfgname, group)
                
                # Override previous moves
                channame = "%s_commander" % npi["team"]
                newstate.channel = getattr(ngcfg, channame)
                
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
        cfg = self.cfg()
        log = self.log()
        update = False
        
        state.is_linked = False
        
        if state.session in self.sessions:
            if state.identity != self.sessions[state.session].identity:
                update = True
            
            if state.context != self.sessions[state.session].context:
                update = True
        else:
            if state.identity or state.context:
                self.sessions[state.session] = None
                update = True
            else:
                self.sessions[state.session] = state
                return
            
        if update:
            if state.context.startswith("Battlefield 2\0"):
                state.is_linked = True
                
                try:
                    context = ElementTree.fromstring(state.context.split('\0', 1)[1])
                    
                    ipport = context.find("ipport").text
                    if ipport == None:
                        ipport = ''

                    for i in range(cfg.bf2.gamecount):
                        # Try to find a matching game
                        gamename = "g%d" % i
                        gamecfg = getattr(cfg, gamename)
                        if gamecfg.mumble_server == server.id() and \
                            gamecfg.ipport_filter.match(ipport):
                            break
                        gamename = None
                    
                    if not gamename:
                        raise ValueError("No matching game found")
                        
                    state.parsedcontext = {'ipport' : ipport,
                                           'gamecfg' : gamecfg,
                                           'gamename' : gamename}

                except (ExpatError, AttributeError, ValueError):
                    state.parsedcontext = {}
                
                try:
                    identity = ElementTree.fromstring(state.identity)
                    
                    is_commander = x2bool(identity.find("commander").text)
                    is_leader = x2bool(identity.find("squad_leader").text)
                    team = identity.find("team").text
                    if team != "opfor" and team != "blufor":
                        raise ValueError("Invalid team value '%s'" % team)
                        
                    squad = int(identity.find("squad").text)
                    if squad < 0 or squad > 9:
                        raise ValueError("Invalid squad value '%s'" % squad)

                    state.parsedidentity = {'team' : team,
                                           'squad' : squad,
                                           'is_leader' : is_leader,
                                           'is_commander' : is_commander}
                    
                except (ExpatError, AttributeError, ValueError):
                    state.parsedidentity = {}
                
            else:
                state.parsedidentity = {}
                state.parsedcontext = {}
                

            self.update_state(server, self.sessions[state.session], state)
            self.sessions[state.session] = state
    
    def userDisconnected(self, server, state, context = None):
        try:
            del self.sessions[state.session]
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

    def started(self, server, context = None): pass
    def stopped(self, server, context = None): pass
