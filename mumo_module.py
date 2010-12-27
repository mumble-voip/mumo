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

from config import (Config,
                    x2bool,
                    commaSeperatedIntegers,
                    commaSeperatedStrings,
                    commaSeperatedBool)

from worker import Worker

class MumoModule(Worker):
    default_config = {}
    
    def __init__(self, name, manager, configuration = None):
        Worker.__init__(self, name, manager.getQueue())
        self.__manager = manager
        
        if isinstance(configuration, basestring):
            # If we are passed a string expect a config file there
            if configuration:
                self.__cfg = Config(configuration, self.default_config)
            elif self.default_config:
                self.__cfg = Config(default = self.default_config)
            else:
                self.__cfg = None
        else:
            # If we aren't passed a string it will be a config object or None
            self.__cfg = configuration
            
        self.log().info("Initialized")

    #--- Accessors
    def manager(self):
        return self.__manager
    
    def cfg(self):
        return self.__cfg
    
    #--- Module control
    
    
    def onStart(self):
        self.log().info("Start")
    
    def onStop(self):
        self.log().info("Stop")
    
    #--- Events
    
    def connected(self):
        # Called once the Ice connection to the murmur server
        # is established.
        # 
        # All event registration should happen here 
        
        pass
    
    def disconnected(self):
        # Called once a loss of Ice connectivity is detected.
        #
        
        pass
    
    
def logModFu(fu):
    def new_fu(self, *args, **kwargs):
        log = self.log()
        argss = '' if len(args)==0 else ',' + ','.join(['"%s"' % str(arg) for arg in args])
        kwargss = '' if len(kwargs)==0 else ','.join('%s="%s"' % (kw, str(arg)) for kw, arg in kwargs.iteritems())
        log.debug("%s(%s%s%s)", fu.__name__, str(self), argss, kwargss)
        return fu(self, *args, **kwargs)
    return new_fu