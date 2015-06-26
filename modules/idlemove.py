#!/usr/bin/env python
# -*- coding: utf-8

# Copyright (C) 2010-2011 Stefan Hacker <dd0t@users.sourceforge.net>
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
# idlemove.py
#
# Module for moving/muting/deafening idle players after
# a certain amount of time and unmuting/undeafening them
# once they become active again
#

from mumo_module import (commaSeperatedIntegers,
                         commaSeperatedBool,
                         commaSeperatedStrings,
                         MumoModule)

from threading import Timer
import re




class idlemove(MumoModule):
    default_config = {'idlemove':(
                             ('interval', float, 0.1),
                             ('servers', commaSeperatedIntegers, []),
                             ),
                      lambda x: re.match('(all)|(server_\d+)', x):(
                             ('threshold', commaSeperatedIntegers, [3600]),
                             ('mute', commaSeperatedBool, [True]),
                             ('deafen', commaSeperatedBool, [False]),
                             ('channel', commaSeperatedIntegers, [1]),
                             ('source_channel', commaSeperatedIntegers, [-1]),
                             ('whitelist', commaSeperatedStrings, [])
                             ),
                    }
    
    def __init__(self, name, manager, configuration=None):
        MumoModule.__init__(self, name, manager, configuration)
        self.murmur = manager.getMurmurModule()
        self.watchdog = None

    def connected(self):
        self.affectedusers = {} # {serverid:set(sessionids,...)}

        manager = self.manager()
        log = self.log()
        log.debug("Register for Meta & Server callbacks")
        
        cfg = self.cfg()
        servers = cfg.idlemove.servers
        if not servers:
            servers = manager.SERVERS_ALL

        manager.subscribeServerCallbacks(self, servers)
        manager.subscribeMetaCallbacks(self, servers)
        
        if not self.watchdog:
            self.watchdog = Timer(cfg.idlemove.interval, self.handleIdleMove)
            self.watchdog.start()
    
    def disconnected(self):
        self.affectedusers = {}
        if self.watchdog:
            self.watchdog.stop()
            self.watchdog = None

    def handleIdleMove(self):
        cfg = self.cfg()
        try:
            meta = self.manager().getMeta()
            
            if not cfg.idlemove.servers:
                servers = meta.getBootedServers()
            else:
                servers = [meta.getServer(server) for server in cfg.idlemove.servers]
            
            for server in servers:
                if not server: continue
                
                if server:
                    for user in server.getUsers().itervalues():
                            self.UpdateUserAutoAway(server, user)
        finally:
            # Renew the timer
            self.watchdog = Timer(cfg.idlemove.interval, self.handleIdleMove)
            self.watchdog.start()
                        
    def UpdateUserAutoAway(self, server, user):
        log = self.log()
        sid = server.id()
        
        try:
            scfg = getattr(self.cfg(), 'server_%d' % sid)
        except AttributeError:
            scfg = self.cfg().all
        
        try:
            index = self.affectedusers[sid]
        except KeyError:
            self.affectedusers[sid] = set()
            index = self.affectedusers[sid]
        
        # Check if the user is whitelisted
        if user.name in scfg.whitelist:
            return

        # Remember values so we can see changes later
        threshold = None
        mute = user.mute
        deafen = user.deaf
        channel = user.channel
        
        update = False
        over_threshold = False
        
        # Search all our stages top down for a violated treshold and pick the first
        for i in range(len(scfg.threshold) - 1, -1, -1):
            try:
                source_channel = scfg.source_channel[i]
            except IndexError:
                source_channel = -1
                
            try:
                threshold = scfg.threshold[i]
                mute = scfg.mute[i]
                deafen = scfg.deafen[i]
                channel = scfg.channel[i]
            except IndexError:
                log.warning("Incomplete configuration for stage %d of server %i, ignored", i, server.id())
                continue

            if user.idlesecs > threshold and\
                (source_channel == -1 or\
                 user.channel == source_channel or\
                 user.channel == channel):
                
                over_threshold = True
                # Update if state changes needed
                if user.deaf != deafen:
                    update = True
                if user.mute != mute:
                    update = True
                if channel >= 0 and user.channel != channel:
                    update = True
                    
                if update:
                    index.add(user.session)
                    log.info('%ds > %ds: State transition for user %s (%d/%d) from mute %s -> %s / deaf %s -> %s | channel %d -> %d on server %d',
                             user.idlesecs, threshold, user.name, user.session, user.userid, user.mute, mute, user.deaf, deafen,
                             user.channel, channel, server.id())
                break
        
        if not over_threshold and user.session in self.affectedusers[sid]:
            deafen = False
            mute = False
            channel = user.channel
            index.remove(user.session)
            log.info("Restore user %s (%d/%d) on server %d", user.name, user.session, user.userid, server.id())
            update = True
            
        if update:
            user.deaf = deafen
            user.mute = mute
            user.channel = channel
            server.setState(user)
            
    #
    #--- Server callback functions
    #
    def userDisconnected(self, server, state, context=None):
        try:
            index = self.affectedusers[server.id()]
            if state.session in index:
                index.remove(state.session)
        except KeyError:
            pass
            
    def userStateChanged(self, server, state, context=None):
        self.UpdateUserAutoAway(server, state)
        
    def userConnected(self, server, state, context=None): pass # Unused callbacks
    def userTextMessage(self, server, user, message, current=None): pass
    def channelCreated(self, server, state, context=None): pass
    def channelRemoved(self, server, state, context=None): pass
    def channelStateChanged(self, server, state, context=None): pass

    #
    #--- Meta callback functions
    #
    
    def started(self, server, context = None):
        sid = server.id()
        self.affectedusers[sid] = set()
        self.log().debug('Handling server %d', sid)
    
    def stopped(self, server, context = None):
        sid = server.id()
        self.affectedusers[sid] = set()
        self.log().debug('Server %d gone', sid)

