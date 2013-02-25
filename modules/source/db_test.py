#!/usr/bin/env python
# -*- coding: utf-8

# Copyright (C) 2013 Stefan Hacker <dd0t@users.sourceforge.net>
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
from db import SourceDB

class SourceDBTest(unittest.TestCase):
    def setUp(self):
        self.db = SourceDB()

    def tearDown(self):
        self.db.close()


    def testOk(self):
        self.db.reset()
        
        self.assertTrue(self.db.isOk())
        
    def testSingleChannel(self):
        self.db.reset()
        
        sid = 5; cid = 10; game = "tf2"; server = "abc[]def"; team = "1"
        self.assertTrue(self.db.registerChannel(sid, cid, game, server, team))
        self.assertEqual(self.db.cidFor(sid, game, server, team), cid)
        self.db.unregisterChannel(sid, game, server, team)
        self.assertEqual(self.db.cidFor(sid, game, server, team), None)
        
    def testChannelTree(self):
        self.db.reset()
        
        sid = 5; game = "tf2"; server = "abc[]def"; team = 0
        bcid = 10; scid = 11; tcid = 12
        
        self.assertTrue(self.db.registerChannel(sid, 1, "canary", server, team))
        
        # Delete whole tree
        
        self.assertTrue(self.db.registerChannel(sid, bcid, game))
        self.assertTrue(self.db.registerChannel(sid, scid, game, server))
        self.assertTrue(self.db.registerChannel(sid, tcid, game, server, team))
        
        self.assertEqual(self.db.cidFor(sid, game), bcid)
        self.assertEqual(self.db.cidFor(sid, game, server), scid)
        self.assertEqual(self.db.cidFor(sid, game, server, team), tcid)
        self.assertEqual(self.db.cidFor(sid+1, game, server, team), None)
        
        self.db.unregisterChannel(sid, game)
        
        self.assertEqual(self.db.cidFor(sid, game, server, team), None)
        self.assertEqual(self.db.cidFor(sid, game, server), None)
        self.assertEqual(self.db.cidFor(sid, game), None)

        # Delete server channel
        
        self.assertTrue(self.db.registerChannel(sid, bcid, game))
        self.assertTrue(self.db.registerChannel(sid, scid, game, server))
        self.assertTrue(self.db.registerChannel(sid, tcid, game, server, team))
        
        self.db.unregisterChannel(sid, game, server)

        self.assertEqual(self.db.cidFor(sid, game), bcid)
        self.assertEqual(self.db.cidFor(sid, game, server), None)
        self.assertEqual(self.db.cidFor(sid, game, server, team), None)
                
        self.db.unregisterChannel(sid, game)
        
        # Delete team channel

        self.assertTrue(self.db.registerChannel(sid, bcid, game))
        self.assertTrue(self.db.registerChannel(sid, scid, game, server))
        self.assertTrue(self.db.registerChannel(sid, tcid, game, server, team))
        
        self.db.unregisterChannel(sid, game, server, team)
        
        self.assertEqual(self.db.cidFor(sid, game), bcid)
        self.assertEqual(self.db.cidFor(sid, game, server), scid)
        self.assertEqual(self.db.cidFor(sid, game, server, team), None)
        
        self.db.unregisterChannel(sid, game)
        
        # Check canary
        self.assertEqual(self.db.cidFor(sid, "canary", server, team), 1)
        self.db.unregisterChannel(sid, "canary", server, team)
        
    def testDropChannel(self):
        self.db.reset()
        
        sid = 1; cid = 5; game = "tf"
        self.db.registerChannel(sid, cid, game)
        self.db.dropChannel(sid + 1, cid)
        self.assertEqual(self.db.cidFor(sid, game), cid)
        self.db.dropChannel(sid, cid)
        self.assertEqual(self.db.cidFor(sid, game), None)
        
    def testRegisteredChannels(self):
        self.db.reset()
        
        sid = 5; game = "tf2"; server = "abc[]def"; team = 1
        bcid = 10; scid = 11; tcid = 12;
        
        self.db.registerChannel(sid, bcid, game)
        self.db.registerChannel(sid, scid, game, server)
        self.db.registerChannel(sid+1, tcid, game, server, team)
        self.db.registerChannel(sid, tcid, game, server, team)

        
        expected = [(sid, bcid, game, None, None),
                    (sid, scid, game, server, None),
                    (sid, tcid, game, server, team),
                    (sid+1, tcid, game, server, team)]
        
        self.assertEqual(self.db.registeredChannels(), expected)
           
if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()