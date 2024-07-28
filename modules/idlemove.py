#!/usr/bin/env python3
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

import re
from threading import Timer

from config import commaSeperatedIntegers, commaSeperatedBool, commaSeperatedStrings
from mumo_module import MumoModule


class idlemove(MumoModule):
    default_config = {'idlemove': (
        ('interval', float, 0.1),
        ('servers', commaSeperatedIntegers, []),
    ),
        lambda x: re.match(r'(all)|(server_\d+)', x): (
            ['threshold', commaSeperatedIntegers, [3600]],
            ('mute', commaSeperatedBool, [True]),
            ('deafen', commaSeperatedBool, [False]),
            ('channel', commaSeperatedIntegers, [1]),
            ('source_channel', commaSeperatedIntegers, [-1]),
            ('whitelist', commaSeperatedStrings, []),
            ('channel_whitelist', commaSeperatedIntegers, [])
        ),
    }

    def __init__(self, name, manager, configuration=None):
        MumoModule.__init__(self, name, manager, configuration)
        self.murmur = manager.getMurmurModule()
        self.watchdog = None

    def connected(self):
        self.affectedusers = {}  # {serverid:set(sessionids,...)}

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
                if server:
                    for user in server.getUsers().values():
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
            self.affectedusers[sid] = {}
            index = self.affectedusers[sid]

        # Ignore whitelisted users
        if user.name in scfg.whitelist:
            return

        over_threshold = False

        # Search all our stages top down for a violated treshold and pick the first
        for i in range(len(scfg.threshold) - 1, -1, -1):
            try:
                source_channel = scfg.source_channel[i]
            except IndexError:
                source_channel = -1

            try:
                afkThreshold = scfg.threshold[i]
                afkMute = scfg.mute[i]
                afkDeafen = scfg.deafen[i]
                afkChannel = scfg.channel[i]
            except IndexError:
                log.warning("Incomplete configuration for stage %d of server %i, ignored", i, server.id())
                continue

            if user.idlesecs > afkThreshold and user.channel not in scfg.channel_whitelist and (
                    source_channel == -1 or user.channel == source_channel or user.channel == afkChannel):

                over_threshold = True
                # Update if state changes needed
                if user.deaf != afkDeafen or user.mute != afkMute or 0 <= afkChannel != user.channel:
                    index[user.session] = user.channel
                    log.info(
                        '%ds > %ds: State transition for user %s (%d/%d) from mute %s -> %s / deaf %s -> %s | channel %d -> %d on server %d',
                        user.idlesecs, afkThreshold, user.name, user.session, user.userid,
                        user.mute, afkMute,
                        user.deaf, afkDeafen,
                        user.channel, afkChannel,
                        server.id())
                    user.deaf = afkDeafen
                    user.mute = afkMute
                    user.channel = afkChannel
                    server.setState(user)
                break

        if not over_threshold and user.session in self.affectedusers[sid]:
            isInAfkChannel = False
            for i in range(len(scfg.threshold) - 1, -1, -1):
                afkChannel = scfg.channel[i]
                if user.channel == afkChannel:
                    isInAfkChannel = True
                    break
            prevChannel = index.pop(user.session, None)
            log.info("Restore user %s (%d/%d) on server %d, channel %d -> %d", user.name, user.session, user.userid, server.id(), user.channel, prevChannel)
            user.deaf = False
            user.mute = False
            if prevChannel != None and isInAfkChannel:
                user.channel = prevChannel
            server.setState(user)

    #
    # --- Server callback functions
    #
    def userDisconnected(self, server, state, context=None):
        try:
            index = self.affectedusers[server.id()]
            if state.session in index:
                del index[state.session]
        except KeyError:
            pass

    def userStateChanged(self, server, state, context=None):
        self.UpdateUserAutoAway(server, state)

    def userConnected(self, server, state, context=None):
        pass  # Unused callbacks

    def userTextMessage(self, server, user, message, current=None):
        pass

    def channelCreated(self, server, state, context=None):
        pass

    def channelRemoved(self, server, state, context=None):
        pass

    def channelStateChanged(self, server, state, context=None):
        pass

    #
    # --- Meta callback functions
    #

    def started(self, server, context=None):
        sid = server.id()
        self.affectedusers[sid] = {}
        self.log().debug('Handling server %d', sid)

    def stopped(self, server, context=None):
        sid = server.id()
        self.affectedusers[sid] = {}
        self.log().debug('Server %d gone', sid)
