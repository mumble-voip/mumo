#!/usr/bin/env python
# -*- coding: utf-8

# Copyright (C) 2011 Stefan Hacker <dd0t@users.sourceforge.net>
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
# seen.py
# This module allows asking the server for the last time it saw a specific player
#

from mumo_module import (commaSeperatedIntegers,
                         MumoModule)

from datetime import timedelta

class seen(MumoModule):
    default_config = {'seen':(
                                ('servers', commaSeperatedIntegers, []),
                                ('keyword', str, '!seen')
                                )
                    }
    
    def __init__(self, name, manager, configuration = None):
        MumoModule.__init__(self, name, manager, configuration)
        self.murmur = manager.getMurmurModule()
        self.keyword = self.cfg().seen.keyword

    def connected(self):
        manager = self.manager()
        log = self.log()
        log.debug("Register for Server callbacks")
        
        servers = self.cfg().seen.servers
        if not servers:
            servers = manager.SERVERS_ALL
            
        manager.subscribeServerCallbacks(self, servers)
    
    def disconnected(self): pass
    
    def sendMessage(self, server, user, message, msg):
        if message.channels:
            server.sendMessageChannel(user.channel, False, msg)
        else:
            server.sendMessage(user.session, msg)
            server.sendMessage(message.sessions[0], msg)
    #
    #--- Server callback functions
    #
    
    def userTextMessage(self, server, user, message, current=None):
        if message.text.startswith(self.keyword) and \
            (len(message.sessions) == 1 or
              (len(message.channels) == 1 and \
              message.channels[0] == user.channel)):
            
            tuname = message.text[len(self.keyword):].strip()
            self.log().debug("User %s (%d|%d) on server %d asking for '%s'",
                             user.name, user.session, user.userid, server.id(), tuname)

            # Check for self referencing
            if tuname == user.name:
                msg = "User '%s' knows how to spell his name" % tuname
                self.sendMessage(server, user, message, msg)
                return
            
            # Check online users
            for cuser in server.getUsers().itervalues():
                if tuname == cuser.name:
                    msg = "User '%s' is currently online, has been idle for %s" % (tuname,
                                                                                           timedelta(seconds=cuser.idlesecs))
                    self.sendMessage(server, user, message, msg)
                    return
                
            # Check registrations
            for cuid, cuname in server.getRegisteredUsers(tuname).iteritems():
                if cuname == tuname:
                    ureg = server.getRegistration(cuid)
                    if ureg:
                        msg = "User '%s' was last seen %s UTC" % (tuname,
                                                                    ureg[self.murmur.UserInfo.UserLastActive])
                        
                        self.sendMessage(server, user, message, msg)
                        return
              
            msg = "I don't know who user '%s' is" % tuname
            self.sendMessage(server, user, message, msg)

            
    
    def userConnected(self, server, state, context = None): pass
    def userDisconnected(self, server, state, context = None): pass
    def userStateChanged(self, server, state, context = None): pass
    
    def channelCreated(self, server, state, context = None): pass
    def channelRemoved(self, server, state, context = None): pass
    def channelStateChanged(self, server, state, context = None): pass
