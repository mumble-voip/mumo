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
# test.py
# The test module has heavy debug output was solely
# written for testing the basic framework as well as
# debugging purposes. Usually you don't want
# to use this.
#

from mumo_module import (x2bool,
                         MumoModule,
                         logModFu)
    
class test(MumoModule):
    default_config = {'testing':(('tvar', int , 1),
                                 ('novar', str, 'no bernd'))}
    
    def __init__(self, name, manager, configuration = None):
        MumoModule.__init__(self, name, manager, configuration)
        log = self.log()
        cfg = self.cfg()
        log.debug("tvar: %s", cfg.testing.tvar)
        log.debug("novar: %s", cfg.testing.novar)
    
    @logModFu
    def connected(self):
        manager = self.manager()
        log = self.log()
        log.debug("Ice connected, register for everything out there")
        manager.subscribeMetaCallbacks(self)
        manager.subscribeServerCallbacks(self, manager.SERVERS_ALL)
        manager.subscribeContextCallbacks(self, manager.SERVERS_ALL)
    
    @logModFu
    def disconnected(self):
        self.log().debug("Ice disconnected")
    #
    #--- Meta callback functions
    #
    
    @logModFu
    def started(self, server, context = None):
        pass
    
    @logModFu
    def stopped(self, server, context = None):
        pass
    
    #
    #--- Server callback functions
    #
    @logModFu
    def userConnected(self, server, state, context = None):
        pass
    
    @logModFu
    def userDisconnected(self, server, state, context = None):
        pass
    
    @logModFu
    def userStateChanged(self, server, state, context = None):
        pass
    
    @logModFu
    def channelCreated(self, server, state, context = None):
        pass
    
    @logModFu
    def channelRemoved(self, server, state, context = None):
        pass
    
    @logModFu
    def channelStateChanged(self, server, state, context = None):
        pass
    
    #
    #--- Server context callback functions
    #
    @logModFu
    def contextAction(self, server, action, user, session, channelid, context = None):
        pass