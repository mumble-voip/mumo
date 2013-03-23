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
        self._reset()
    
    def id(self):
        return self.sid
    
    def _lastChannelID(self):
        return self.uid
        
    def addChannel(self, name, parent):
        self.uid += 1
        assert(not self.uid in self.channels)
        self.channels[self.uid] = {'name' : name,
                                   'parent' : parent,
                                   'groups' : {},
                                   'acls' : [] }
        return self.uid
    
    def addUserToGroup(self, cid, session, group):
        c = self._getChan(cid)
        
        if session in c['groups']:
            c['groups'][session].add(group)
        else:
            c['groups'][session] = set([group])
    
    def _getChan(self, cid):
        if not cid in self.channels:
            raise InvalidChannelExceptionMock()
        
        return self.channels[cid]
        
    def getChannelState(self, cid):
        self._getChan(cid)
        
        return {'fake': True}
    
    def setState(self, state):
        self.user_state.append(state)
        
    def setACL(self, cid, acls, groups, inherit):
        c = self._getChan(cid)
        c['acls'] = acls
    
    def _reset(self):
        self.uid = 1000
        self.channels = {} # See addChannel
        self.user_state = []

class ACLMock(object):
    def __init__(self, applyHere, applySubs, userid, group, deny = 0, allow = 0):
        self.applyHere = applyHere
        self.applySubs = applySubs
        self.userid = userid
        self.group = group
        self.deny = deny
        self.allow = allow
        

class MurmurMock(object):
    InvalidChannelException = InvalidChannelExceptionMock
    ACL = ACLMock
    PermissionEnter = 1
    PermissionTraverse = 2
    PermissionWhisper = 4
    PermissionSpeak = 8
    
    def _reset(self): pass
    
    def __init__(self):
        pass


class MockACLHelper(object):
    E = MurmurMock.PermissionEnter
    T = MurmurMock.PermissionTraverse
    W = MurmurMock.PermissionWhisper
    S = MurmurMock.PermissionSpeak
    
    EAT = E | T
    ALL = E|T|W|S

ACLS = MockACLHelper


class MetaMock():
    def __init__(self):
        #TODO: Create range of server (or even cretae them on demand)
        self.servers = {1:ServerMock(1),
                        5:ServerMock(5),
                        10:ServerMock(10)}
        self.s = self.servers[1] # Shorthand
        
    def getServer(self, sid):
        return self.servers.get(sid, None)

    def _reset(self):
        for server in self.servers.itervalues():
            server._reset()

class ManagerMock():
    SERVERS_ALL = [-1]
    
    def __init__(self):
        self.q = Queue.Queue()
        self.m = MurmurMock()
        self.meta = MetaMock()
        
    def getQueue(self):
        return self.q
    
    def getMurmurModule(self):
        return self.m
    
    def getMeta(self):
        return self.meta
    
    def subscribeServerCallbacks(self, callback, servers):
        self.serverCB = {'callback' : callback, 'servers' : servers}
        
    def subscribeMetaCallbacks(self, callback, servers):
        self.metaCB = {'callback' : callback, 'servers' : servers}
     
class Test(unittest.TestCase):

    def setUp(self):
        self.mm = ManagerMock();
        self.mserv = self.mm.meta.getServer(1)
        
        
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
        self.mm.m._reset()
        self.mm.meta._reset()
        
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

        self.assertEqual(self.s.getGameConfig("wugu", "name"), "%(game)s")
        self.assertEqual(self.s.getGameConfig("tf", "name"), "Team Fortress 2")

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
        
    def checkACLThings(self, acls, things):
        self.assertEqual(len(things), len(acls))
        
        i = 0
        for thing in things:
            acl = acls[i]
            for attr, val in thing.iteritems():
                self.assertEqual(getattr(acl, attr), val)
            i += 1
    
    def testGetOrCreateChannelFor(self):
        mumble_server = self.mserv
        
        prev = mumble_server._lastChannelID()
        game = "tf"; server = "[A-1:123]"; team = 3 
        cid = self.s.getOrCreateChannelFor(mumble_server, game, server, team)
        
        self.assertEqual(3, cid - prev)
        
        c = mumble_server.channels
        
        self.assertEqual(c[prev + 1]["parent"], 0)
        self.assertEqual(c[prev + 2]["parent"], prev + 1)
        self.assertEqual(c[prev + 3]["parent"], prev + 2)
        
        self.assertEqual(c[prev + 1]["name"], "Team Fortress 2")
        self.assertEqual(c[prev + 2]["name"], "Test tf [A-1:123]")
        self.assertEqual(c[prev + 3]["name"], "Red")
        
        sid = mumble_server.id()
        
        self.assertEqual(self.s.db.cidFor(sid, game), prev + 1);
        self.assertEqual(self.s.db.cidFor(sid, game, server), prev + 2);
        self.assertEqual(self.s.db.cidFor(sid, game, server, team), prev + 3);
        
        gotcid = self.s.getOrCreateChannelFor(mumble_server, game, server, team)
        self.assertEqual(cid, gotcid)
        
        c = mumble_server.channels
        
        self.checkACLThings(c[prev + 3]['acls'], [{'group' : '~source_tf_[A-1:123]_3'}])
        self.checkACLThings(c[prev + 2]['acls'], [{'group' : '~source_tf_[A-1:123]'}])
        self.checkACLThings(c[prev + 1]['acls'], [{},
                                                  {'group' : '~source_tf'}])
        
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
        
        self.assertTrue(self.s.isValidGameType("dod"))
        self.assertTrue(self.s.isValidGameType("cstrike"))
        self.assertTrue(self.s.isValidGameType("tf"))
        
        self.assertFalse(self.s.isValidGameType("dodx"))
        self.assertFalse(self.s.isValidGameType("xdod"))
        self.assertFalse(self.s.isValidGameType(""))
    
    def testValidServer(self):
        self.resetState()
        
        self.assertTrue(self.s.isValidServer("dod", "[A-1:2807761920(3281)]"))
        
        self.assertFalse(self.s.isValidServer("dod", "A-1:2807761920(3281)]"))
        self.assertFalse(self.s.isValidServer("dod", "[A-1:2807761920(3281)"))
        self.assertFalse(self.s.isValidServer("dod", "[A-1:2807761920(3281)&]"))
        
        self.assertTrue(self.s.isValidServer("tf", "[A-1:123]"))
        
        self.assertFalse(self.s.isValidServer("tf", "x[A-1:123]"))
        self.assertFalse(self.s.isValidServer("tf", "[A-1:123]x"))
        
    def testMoveUser(self):
        self.resetState()
        
        mumble_server = self.mserv
        user_state = StateMock()
        prev = self.mserv._lastChannelID()
        
        TEAM_BLUE = 2
        TEAM_RED = 3
    
        BASE_SID = 0
        GAME_SID = prev + 1
        SERVER_SID = prev + 2
        TEAM_RED_SID = prev + 3
        TEAM_BLUE_SID = prev + 4
        
        user = source.User(user_state, {'team':TEAM_BLUE}, "tf", "[A-1:123]")
        self.s.moveUser(self.mserv, user)
        c = mumble_server.channels
        self.assertEqual(c[prev + 1]["parent"], BASE_SID)
        self.assertEqual(c[prev + 2]["parent"], GAME_SID)
        self.assertEqual(c[prev + 3]["parent"], SERVER_SID)
        
        self.assertEqual(c[prev + 1]["name"], "Team Fortress 2")
        self.assertEqual(c[prev + 2]["name"], "Test tf [A-1:123]")
        self.assertEqual(c[prev + 3]["name"], "Blue")
        self.assertEqual(len(c), 3)
        
        self.assertEqual(user_state.channel, TEAM_RED_SID)
        self.assertEqual(mumble_server.user_state[0], user_state)

        user.identity['team'] = TEAM_RED
        self.s.moveUser(self.mserv, user)
        
        self.assertEqual(c[prev + 4]["parent"], SERVER_SID)
        self.assertEqual(c[prev + 4]["name"], "Red")
        self.assertEqual(len(c), 4)
        
        self.assertEqual(user_state.channel, TEAM_BLUE_SID)
        self.assertEqual(mumble_server.user_state[0], user_state)
        
    def testValidateChannelDB(self):
        self.resetState()
        
        self.s.db.registerChannel(5, 6, "7")
        self.s.db.registerChannel(5, 7, "7", "8")
        self.s.db.registerChannel(5, 8, "7", "8", 9)
        self.s.db.registerChannel(6, 9, "8", "9", 10)
        self.s.db.registerChannel(5, 10, "7", "123", 9)
        
        game = 'cstrike'; server = '[A123:123]'; team = 1
        self.s.getOrCreateChannelFor(self.mserv, game, server, team)
        self.s.validateChannelDB()
        self.assertEqual(len(self.s.db.registeredChannels()), 3)
        
        
        
        
    def testSetACLsForGameChannel(self):
        self.resetState()
        
        mumble_server = self.mserv
        cid = mumble_server.addChannel("test", 1); game = "dod"
        
        self.s.setACLsForGameChannel(mumble_server, cid, game)
        acls = mumble_server.channels[cid]['acls']
        
        self.checkACLThings(acls, [{'applyHere' : True,
                                    'applySubs' : True,
                                    'userid' : -1,
                                    'group' : 'all',
                                    'deny' : ACLS.ALL,
                                    'allow' : 0},
                                   
                                   {'applyHere' : True,
                                    'applySubs' : False,
                                    'userid' : -1,
                                    'group' : '~source_dod',
                                    'deny' : 0,
                                    'allow' : ACLS.EAT}])
        
        
    def testSetACLsForServerChannel(self):
        self.resetState()

        mumble_server = self.mserv
        cid = mumble_server.addChannel("test", 1); game = "tf"; server = "[A-1:SomeServer]"
        self.s.setACLsForServerChannel(mumble_server, cid, game, server)
        acls = mumble_server.channels[cid]['acls']
        
        self.checkACLThings(acls, [{'applyHere' : True,
                                    'applySubs' : False,
                                    'userid' : -1,
                                    'group' : '~source_tf_[A-1:SomeServer]',
                                    'deny' : 0,
                                    'allow' : ACLS.EAT}])
        
        
    def testSetACLsForTeamChannel(self):
        self.resetState()
        
        mumble_server = self.mserv
        cid = mumble_server.addChannel("test", 1); game = "tf"; server = "[A-1:SomeServer]"; team = 2
        
        self.s.setACLsForTeamChannel(mumble_server, cid, game, server, team)
        acls = mumble_server.channels[cid]['acls']
        
        self.checkACLThings(acls, [{'applyHere' : True,
                                    'applySubs' : False,
                                    'userid' : -1,
                                    'group' : '~source_tf_[A-1:SomeServer]_2',
                                    'deny' : 0,
                                    'allow' : ACLS.ALL}])
        
    def testAddToGroups(self):
        self.resetState()
        
        mumble_server = self.mserv
        prev = mumble_server._lastChannelID()
        
        session = 10; game = 'cstrike'; server = '[A-1:12345]'; team = 1
        self.s.getOrCreateChannelFor(mumble_server, game, server, team)
        
        # Test
        self.s.addToGroups(mumble_server, session, game, server, team)
        
        groups = mumble_server.channels[prev + 1]['groups'][session]
        self.assertIn("source_cstrike", groups)
        self.assertIn("source_cstrike_[A-1:12345]", groups)
        self.assertIn("source_cstrike_[A-1:12345]_1", groups)
        
        
if __name__ == "__main__":
    #logging.basicConfig(level = logging.DEBUG)
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()