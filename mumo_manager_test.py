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

import unittest
import Queue
from mumo_manager import MumoManager, MumoManagerRemote
from mumo_module import MumoModule


class MumoManagerTest(unittest.TestCase):
    def setUp(self):
        class MyModule(MumoModule):
            def __init__(self, name, manager, configuration = None):
                MumoModule.__init__(self, name, manager, configuration)
                self.was_called = False
                self.par1 = None
                self.par2 = None
                self.par3 = None
                
            def last_call(self):
                ret = (self.was_called, self.par1, self.par2, self.par3)
                self.was_called = False
                return ret
                
            def call_me(self, par1, par2 = None, par3 = None):
                self.was_called = True
                self.par1 = par1
                self.par2 = par2
                self.par3 = par3
                
        self.man = MumoManager()
        self.man.start()
        
        class conf(object):
            pass # Dummy class
        
        cfg = conf()
        cfg.test = 10
        
        self.mod = self.man.loadModuleCls("MyModule", MyModule, cfg)
        self.man.startModules()
        


    def tearDown(self):
        self.man.stopModules()
        self.man.stop()
        self.man.join(timeout=2)


    def testName(self):
        pass


if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()