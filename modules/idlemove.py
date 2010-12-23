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
# idlemove.py
#
# Module for moving/muting/deafening idle players after
# a certain amount of time and moving them back once
# they interact again.
#

from mumo_module import (x2bool,
                         commaSeperatedIntegers,
                         MumoModule,
                         Config)

from threading import Timer
import re




class idlemove(MumoModule):
    default_config = {'idlemove':(
                             ('interval', float, 0.1),
                             ('servers', commaSeperatedIntegers, []),
                             ),
                      'all':(
                             ('threshold', int, 3600),
                             ('mute', x2bool, True),
                             ('deafen', x2bool, False),
                             ('channel', int, 1)
                             ),
                      lambda x: re.match('server_\d+', x):(
                             ('threshold', int, 3600),
                             ('mute', x2bool, True),
                             ('deafen', x2bool, False),
                             ('channel', int, 1),
                             ('restore', x2bool, True)
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
            
        update = False
        if not user in index and user.idlesecs > scfg.threshold:
            if scfg.deafen \
                and not (user.suppress or user.selfMute or user.mute) \
                and not (user.selfDeaf or user.deaf):
                log.info('Mute and deafen user %s (%d / %d) on server %d', user.name, user.session, user.userid, sid)
                user.deaf = True
                update = True
            elif scfg.mute and not (user.suppress or user.selfMute or user.mute):
                log.info('Mute user %s (%d / %d) on server %d', user.name, user.session, user.userid, sid)
                user.mute = True
                update = True
            
            if scfg.channel >= 0 and user.channel != scfg.channel:
                log.info('Move user %s (%d / %d) on server %d', user.name, user.session, user.userid, sid)
                user.channel = scfg.channel
                update = True
                
            if update:
                index.add(user.session)
                
        elif user.session in index and user.idlesecs < scfg.threshold:
            index.remove(user.session)
            if scfg.deafen:
                log.info('Unmute and undeafen user %s (%d / %d) on server %d', user.name, user.session, user.userid, sid)
                user.mute = False
                user.deaf = False
                update = True
            elif scfg.mute:
                log.info('Unmute user %s (%d / %d) on server %d', user.name, user.session, user.userid, sid)
                user.mute = False
                update = True
        
        if update:
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
    