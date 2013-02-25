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
import Queue
import config
import re
import logging
import source

class InvalidChannelExceptionMock(Exception):
    pass

class StateMock():
    def __init__(self, cid = 0, session = 0, userid = -1):
        self.channel = cid
        self.session = session
        self.userid = userid
        
class ServerMock():
    def __init__(self, sid):
        self.sid = sid
        self.reset()
    
    def id(self):
        return self.sid
    
    def lastChannelID(self):
        return self.uid
        
    def addChannel(self, name, parent):
        self.name.append(name)
        self.parent.append(parent)
        
        self.uid += 1
        return self.uid

        
    def getChannelState(self, cid):
        if not cid in self.channel:
            raise InvalidChannelExceptionMock()
        return {'fake':True}
    
    def setState(self, state):
        self.user_state.append(state)
        
    def reset(self):
        self.uid = 1000
        self.name = []
        self.parent = []
        self.user_state = []
        
class MurmurMock():
    InvalidChannelException = InvalidChannelExceptionMock
    def __init__(self):
        self.s = ServerMock(1)
        
    def getServer(self, sid):
        assert(sid == self.s.id())
        return self.s
    
    def reset(self):
        self.s.reset()

class ManagerMock():
    SERVERS_ALL = [-1]
    
    def __init__(self):
        self.q = Queue.Queue()
        self.m = MurmurMock()
        
    def getQueue(self):
        return self.q
    
    def getMurmurModule(self):
        return self.m
    
    def subscribeServerCallbacks(self, callback, servers):
        self.serverCB = {'callback' : callback, 'servers' : servers}
        
    def subscribeMetaCallbacks(self, callback, servers):
        self.metaCB = {'callback' : callback, 'servers' : servers}
     
class Test(unittest.TestCase):

    def setUp(self):
        self.mm = ManagerMock();
        self.mserv = self.mm.m.getServer(1)
        
        
        testconfig = config.Config(None, source.source.default_config)
        testconfig.source.database = ":memory:"
        
        # As it is hard to create the read only config structure from
        # hand use a spare one to steal from
        spare = config.Config(None, source.source.default_config)
        testconfig.__dict__['game:tf'] = spare.generic
        testconfig.__dict__['game:tf'].name = "Team Fortress 2"
        testconfig.__dict__['game:tf'].teams = ["Lobby", "Spectator", "Blue", "Red"]
        testconfig.__dict__['game:tf'].serverregex = re.compile("^\[A-1:123\]$")
        testconfig.__dict__['game:tf'].servername = "Test %(game)s %(server)s"
        
        self.s = source.source("source", self.mm, testconfig)
        self.mm.s = self.s
        
        # Since we don't want to run threaded if we don't have to
        # emulate startup to the derived class function
        self.s.onStart()
        self.s.connected()
        
        # Critical test assumption
        self.assertEqual(self.mm.metaCB['callback'], self.s)
        self.assertEqual(self.mm.serverCB['callback'], self.s)
    
    def resetDB(self):
        self.s.db.db.execute("DELETE FROM source");
        
    def resetState(self):
        self.resetDB()
        self.mm.m.reset()
        
    def tearDown(self):
        self.s.disconnected()
        self.s.onStop()

    def testDefaultConfig(self):
        self.resetState()
        
        mm = ManagerMock()
        INVALIDFORCEDEFAULT = ""
        s = source.source("source", mm, INVALIDFORCEDEFAULT)
        self.assertNotEqual(s.cfg(), None)
    
    def testConfiguration(self):
        self.resetState()
        
        # Ensure the default configuration makes sense
        self.assertEqual(self.mm.serverCB['servers'], self.mm.SERVERS_ALL)
        self.assertEqual(self.mm.metaCB['servers'], self.mm.SERVERS_ALL)
        
        self.assertEqual(self.s.cfg().source.basechannelid, 0)
        self.assertEqual(self.s.cfg().generic.name, "%(game)s")

        self.assertEqual(self.s.gameCfg("wugu", "name"), "%(game)s")
        self.assertEqual(self.s.gameCfg("tf", "name"), "Team Fortress 2")

    def testIdentityParser(self):
        self.resetState()
        
        expected = {"universe" : 1,
                    "account_type" : 2,
                    "id" : 3,
                    "instance" : 4,
                    "team" : 5}
        
        got = self.s.parseSourceIdentity("universe:1;account_type:2;id:00000003;instance:4;team:5")
        self.assertDictEqual(expected, got)
        
        got = self.s.parseSourceIdentity("universe:1;account_type:2;id:00000003;instance:4;")
        self.assertEqual(got, None, "Required team variable missing")
    
        self.assertEqual(self.s.parseSourceIdentity(None), None)
        self.assertEqual(self.s.parseSourceIdentity(""), None)
        self.assertEqual(self.s.parseSourceIdentity("whatever:4;dskjfskjdfkjsfkjsfkj"), None)
        
    def testContextParser(self):
        self.resetState()
        
        none = (None, None)
        self.assertEqual(self.s.parseSourceContext(None), none)
        self.assertEqual(self.s.parseSourceContext(""), none)
        self.assertEqual(self.s.parseSourceContext("whatever:4;skjdakjkjwqdkjqkj"), none)
        
        expected = ("dod", "[A-1:2807761920(3281)]")
        actual = self.s.parseSourceContext("Source engine: dod\x00[A-1:2807761920(3281)]\x00")
        self.assertEqual(expected, actual)
        
        expected = ("dod", "[0:1]")
        actual = self.s.parseSourceContext("Source engine: dod\x00[0:1]\x00")
        self.assertEqual(expected, actual)

        expected = ("cstrike", "[0:1]")
        actual = self.s.parseSourceContext("Source engine: cstrike\x00[0:1]\x00")
        self.assertEqual(expected, actual)
                
        actual = self.s.parseSourceContext("Source engine: fake\x00[A-1:2807761920(3281)]\x00")
        self.assertEqual(none, actual)
        
        actual = self.s.parseSourceContext("Source engine: cstrike\x0098vcv98re98ver98ver98v\x00")
        self.assertEqual(none, actual)
        
        # Check alternate serverregex
        expected = ("tf", "[A-1:123]")
        actual = self.s.parseSourceContext("Source engine: tf\x00[A-1:123]\x00")
        self.assertEqual(expected, actual)
        
        actual = self.s.parseSourceContext("Source engine: tf\x00[A-1:2807761920(3281)]\x00")
        self.assertEqual(none, actual)
        
    def testGetOrCreateChannelFor(self):
        mumble_server = self.mserv
        
        prev = mumble_server.lastChannelID()
        game = "tf"; server = "[A-1:123]"; team = 3 
        cid = self.s.getOrCreateChannelFor(mumble_server, game, server, team)
        
        self.assertEqual(3, cid - prev)
        
        self.assertEqual(mumble_server.parent[0], 0)
        self.assertEqual(mumble_server.parent[1], prev + 1)
        self.assertEqual(mumble_server.parent[2], prev + 2)
        
        self.assertEqual(mumble_server.name[0], "Team Fortress 2")
        self.assertEqual(mumble_server.name[1], "Test tf [A-1:123]")
        self.assertEqual(mumble_server.name[2], "Red")
        
        sid = mumble_server.id()
        
        self.assertEqual(self.s.db.cidFor(sid, game), prev + 1);
        self.assertEqual(self.s.db.cidFor(sid, game, server), prev + 2);
        self.assertEqual(self.s.db.cidFor(sid, game, server, team), prev + 3);
        
        gotcid = self.s.getOrCreateChannelFor(mumble_server, game, server, team)
        self.assertEqual(cid, gotcid)
        
        #print self.s.db.db.execute("SELECT * FROM source").fetchall()
    
    def testGetGameName(self):
        self.resetState()
        
        self.assertEqual(self.s.getGameName("tf"), "Team Fortress 2")
        self.assertEqual(self.s.getGameName("invalid"), "%(game)s");
    
    def testGetServerName(self):
        self.resetState()
        
        self.assertEqual(self.s.getServerName("tf"), "Test %(game)s %(server)s")
        self.assertEqual(self.s.getServerName("invalid"), "%(server)s");
        
    def testGetTeamName(self):
        self.resetState()
        
        self.assertEqual(self.s.getTeamName("tf", 2), "Blue")
        self.assertEqual(self.s.getTeamName("tf", 100), "100") #oob
        
        self.assertEqual(self.s.getTeamName("invalid", 2), "Team one")
        self.assertEqual(self.s.getTeamName("invalid", 100), "100") #oob
      
    def testValidGameType(self):
        self.resetState()
        
        self.assertTrue(self.s.validGameType("dod"))
        self.assertTrue(self.s.validGameType("cstrike"))
        self.assertTrue(self.s.validGameType("tf"))
        
        self.assertFalse(self.s.validGameType("dodx"))
        self.assertFalse(self.s.validGameType("xdod"))
        self.assertFalse(self.s.validGameType(""))
    
    def testValidServer(self):
        self.resetState()
        
        self.assertTrue(self.s.validServer("dod", "[A-1:2807761920(3281)]"))
        
        self.assertFalse(self.s.validServer("dod", "A-1:2807761920(3281)]"))
        self.assertFalse(self.s.validServer("dod", "[A-1:2807761920(3281)"))
        self.assertFalse(self.s.validServer("dod", "[A-1:2807761920(3281)&]"))
        
        self.assertTrue(self.s.validServer("tf", "[A-1:123]"))
        
        self.assertFalse(self.s.validServer("tf", "x[A-1:123]"))
        self.assertFalse(self.s.validServer("tf", "[A-1:123]x"))
        
    def testMoveUser(self):
        self.resetState()
        
        mumble_server = self.mserv
        user_state = StateMock()
        prev = self.mserv.lastChannelID()
        
        TEAM_BLUE = 2
        TEAM_RED = 3
    
        BASE_SID = 0
        GAME_SID = prev + 1
        SERVER_SID = prev + 2
        TEAM_RED_SID = prev + 3
        TEAM_BLUE_SID = prev + 4
        
        self.s.moveUser(self.mserv, user_state, "tf", "[A-1:123]", TEAM_BLUE)
        
        self.assertEqual(mumble_server.parent[0], BASE_SID)
        self.assertEqual(mumble_server.parent[1], GAME_SID)
        self.assertEqual(mumble_server.parent[2], SERVER_SID)
        
        self.assertEqual(mumble_server.name[0], "Team Fortress 2")
        self.assertEqual(mumble_server.name[1], "Test tf [A-1:123]")
        self.assertEqual(mumble_server.name[2], "Blue")
        self.assertEqual(len(mumble_server.name), 3)
        
        self.assertEqual(user_state.channel, TEAM_RED_SID)
        self.assertEqual(mumble_server.user_state[0], user_state)

        self.s.moveUser(self.mserv, user_state, "tf", "[A-1:123]", TEAM_RED)
        
        self.assertEqual(mumble_server.parent[3], SERVER_SID)
        self.assertEqual(mumble_server.name[3], "Red")
        self.assertEqual(len(mumble_server.parent), 4)
        
        self.assertEqual(user_state.channel, TEAM_BLUE_SID)
        self.assertEqual(mumble_server.user_state[0], user_state)
        
        
if __name__ == "__main__":
    #logging.basicConfig(level = logging.DEBUG)
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()