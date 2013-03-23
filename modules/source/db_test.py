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
import sqlite3

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

        
        expected = [(sid, bcid, game, self.db.NO_SERVER, self.db.NO_TEAM),
                    (sid, scid, game, server, self.db.NO_TEAM),
                    (sid, tcid, game, server, team),
                    (sid+1, tcid, game, server, team)]
        
        self.assertEqual(self.db.registeredChannels(), expected)
           
    def testIsRegisteredChannel(self):
        self.db.reset()
        sid = 1; cid = 0; game = "tf"
        self.db.registerChannel(sid, cid, game)
        
        self.assertTrue(self.db.isRegisteredChannel(sid, cid))
        self.assertFalse(self.db.isRegisteredChannel(sid+1, cid))
        self.assertFalse(self.db.isRegisteredChannel(sid, cid+1))
        
        self.db.unregisterChannel(sid, game)
        
        self.assertFalse(self.db.isRegisteredChannel(sid, cid))
        
    def testChannelFor(self):
        self.db.reset()
        sid = 1; cid = 0; game = "tf"; server = "serv"; team = 0
        self.db.registerChannel(sid, cid, game)
        self.db.registerChannel(sid, cid+1, game, server)
        self.db.registerChannel(sid, cid+2, game, server, team)
        
        res = self.db.channelFor(sid, game, server, team)
        self.assertEqual(res, (sid, cid + 2, game, server, team))
        
        res = self.db.channelFor(sid, game, server)
        self.assertEqual(res, (sid, cid + 1, game, server, self.db.NO_TEAM))
        
        res = self.db.channelFor(sid, game)
        self.assertEqual(res, (sid, cid, game, self.db.NO_SERVER, self.db.NO_TEAM))
        
        res = self.db.channelFor(sid, game, server, team+5)
        self.assertEqual(res, None)
        
    def testChannelForCid(self):
        self.db.reset()
        sid = 1; cid = 0; game = "tf"; server = "serv"; team = 0
        self.db.registerChannel(sid, cid, game)
        self.db.registerChannel(sid, cid+1, game, server)
        self.db.registerChannel(sid, cid+2, game, server, team)
        
        res = self.db.channelForCid(sid, cid)
        self.assertEqual(res, (sid, cid, game, self.db.NO_SERVER, self.db.NO_TEAM))
        
        
        res = self.db.channelForCid(sid, cid + 1)
        self.assertEqual(res, (sid, cid + 1, game, server, self.db.NO_TEAM))
        
        
        res = self.db.channelForCid(sid, cid + 2)
        self.assertEqual(res, (sid, cid + 2, game, server, team))
        
        
        res = self.db.channelForCid(sid, cid + 3)
        self.assertEqual(res, None)
        
    def testChannelsFor(self):
        self.db.reset()
        sid = 1; cid = 0; game = "tf"; server = "serv"; team = 0
        self.db.registerChannel(sid, cid, game)
        self.db.registerChannel(sid, cid+1, game, server)
        self.db.registerChannel(sid, cid+2, game, server, team)
        
        chans = ((sid, cid+2, game, server, team),
                 (sid, cid+1, game, server, self.db.NO_TEAM),
                 (sid, cid, game, self.db.NO_SERVER, self.db.NO_TEAM))
        
        res = self.db.channelsFor(sid, game, server, team)
        self.assertItemsEqual(res, chans[0:1])
        
        res = self.db.channelsFor(sid, game, server)
        self.assertItemsEqual(res, chans[0:2])
        
        res = self.db.channelsFor(sid, game)
        self.assertItemsEqual(res, chans)
        
        res = self.db.channelsFor(sid+1, game)
        self.assertItemsEqual(res, [])
    
    def testChannelTableConstraints(self):
        self.db.reset()
        
        # cid constraint
        sid = 1; cid = 0; game = "tf"; server = "serv"; team = 0
        self.db.registerChannel(sid, cid, game)
        self.assertRaises(sqlite3.IntegrityError, self.db.registerChannel, sid, cid, "cstrike")

        # combination constraint
        self.assertRaises(sqlite3.IntegrityError, self.db.registerChannel, sid, cid+1000, game)
        
        self.db.registerChannel(sid, cid+1, game, server)
        self.assertRaises(sqlite3.IntegrityError, self.db.registerChannel, sid, cid+100, game, server)
        
        self.db.registerChannel(sid, cid+2, game, server, team)
        self.assertRaises(sqlite3.IntegrityError, self.db.registerChannel, sid, cid+200, game, server, team)
    
    def testChannelNameMappingTableConstraints(self):
        self.db.reset()
        
        sid = 1; game = "tf"
        
        # mapName performs an INSERT OR REPLACE which relies on the UNIQUE constraint
        self.db.mapName("SomeTestName", sid, game)
        self.db.mapName("SomeOtherName", sid, game)
        self.assertEqual(self.db.nameFor(sid, game), "SomeOtherName")
        
    def testNameMapping(self):
        self.db.reset()
        
        sid = 1; game = "tf"; server = "[12313]";team = 2
        self.assertEqual(self.db.nameFor(sid, game, default = "test"), "test")
        
        self.db.mapName("Game", sid, game)
        self.db.mapName("Game Server", sid, game, server)
        self.db.mapName("Game Server Team", sid, game, server, team)
        self.db.mapName("Game Server Team 2", sid + 1, game, server, team)
        self.db.mapName("Game Server Team 2", sid, "cstrike", server, team)
        
        self.assertEqual(self.db.nameFor(sid, game), "Game")
        self.assertEqual(self.db.nameFor(sid, game, server), "Game Server")
        self.assertEqual(self.db.nameFor(sid, game, server, team), "Game Server Team")
        
if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()