#!/usr/bin/env python
# -*- coding: utf-8

# Copyright (C) 2015 Stefan Hacker <dd0t@users.sourceforge.net>
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
# samplecontext.py
# This module demonstrates how to add additional
# entries to a user's context menu.
#

from mumo_module import (commaSeperatedIntegers,
                         MumoModule)
import cgi

class samplecontext(MumoModule):
    default_config = {'samplecontext':(
                                ('servers', commaSeperatedIntegers, []),
                                ),
                    }
    
    def __init__(self, name, manager, configuration = None):
        MumoModule.__init__(self, name, manager, configuration)
        self.murmur = manager.getMurmurModule()
        self.action_poke_user = manager.getUniqueAction()
        self.action_info = manager.getUniqueAction()
        self.action_remove = manager.getUniqueAction()

    def connected(self):
        manager = self.manager()
        log = self.log()
        log.debug("Register for Server callbacks")
        
        servers = self.cfg().samplecontext.servers
        if not servers:
            servers = manager.SERVERS_ALL
            
        manager.subscribeServerCallbacks(self, servers)
    
    def disconnected(self): pass

    #
    #--- Server callback functions
    #
    
    def __on_poke_user(self, server, action, user, target):
        assert action == self.action_poke_user
        self.log().info(user.name + " poked " + target.name)
        server.sendMessage(target.session, cgi.escape(user.name) + " poked you")

    def __on_info(self, server, action, user, target):
        assert action == self.action_info
        self.log().info(user.name + " wants info on " + str(target));
        server.sendMessage(user.session,
                "<small><pre>" + cgi.escape(str(target)) + "</pre></small>")

    def __on_remove_this(self, server, action, user, target):
        # This will remove the entry identified by "action" from
        # _all_ users on the server.
        self.log().info(user.name + " triggered removal")
        self.manager().removeContextMenuEntry(server, action)

    def userConnected(self, server, user, context = None):
        # Adding the entries here means if mumo starts up after users
        # already connected they won't have the new entries before they
        # reconnect. You can also use the "connected" callback to
        # add the entries to already connected user. For simplicity
        # this is not done here.

        self.log().info("Adding menu entries for " + user.name)

        manager = self.manager()
        manager.addContextMenuEntry(
                server, # Server of user
                user, # User which should receive the new entry
                self.action_poke_user, # Identifier for the action
                "Poke", # Text in the client
                self.__on_poke_user, # Callback called when user uses the entry
                self.murmur.ContextUser # We only want to show this entry on users
        )

        manager.addContextMenuEntry(
                server,
                user,
                self.action_info,
                "Info",
                self.__on_info,
                self.murmur.ContextUser | self.murmur.ContextChannel # Show for users and channels
        )

        manager.addContextMenuEntry(
                server,
                user,
                self.action_remove,
                "Remove this entry from everyone",
                self.__on_remove_this,
                self.murmur.ContextUser | self.murmur.ContextChannel | self.murmur.ContextServer
        )

    def userDisconnected(self, server, state, context = None): pass
    def userStateChanged(self, server, state, context = None): pass
    def userTextMessage(self, server, user, message, current=None): pass
    def channelCreated(self, server, state, context = None): pass
    def channelRemoved(self, server, state, context = None): pass
    def channelStateChanged(self, server, state, context = None): pass

