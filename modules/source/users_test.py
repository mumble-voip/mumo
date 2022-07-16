#!/usr/bin/env python3
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

from .users import User, UserRegistry


class Test(unittest.TestCase):

    def getSomeUsers(self, n=5):
        sid = []
        session = []
        user = []
        for i in range(n):
            s = str(i)
            sid.append(i)
            session.append(i)
            user.append(User("state" + s, "identity" + s, "game" + s, "server" + s))

        return sid, session, user

    def testRegistryCRUDOps(self):
        r = UserRegistry()

        sid, session, user = self.getSomeUsers()

        # Create & Read
        self.assertTrue(r.add(sid[0], session[0], user[0]))
        self.assertFalse(r.add(sid[0], session[0], user[0]))
        self.assertEqual(r.get(sid[0], session[0]), user[0])

        self.assertTrue(r.addOrUpdate(sid[1], session[1], user[1]))
        self.assertEqual(r.get(sid[1], session[1]), user[1])

        # Update
        self.assertTrue(r.addOrUpdate(sid[0], session[0], user[2]))
        self.assertEqual(r.get(sid[0], session[0]), user[2])

        # Delete
        self.assertTrue(r.remove(sid[1], session[1]))
        self.assertFalse(r.remove(sid[1], session[1]))
        self.assertEqual(r.get(sid[1], session[1]), None)

        self.assertTrue(r.remove(sid[0], session[0]))
        self.assertFalse(r.remove(sid[0], session[0]))
        self.assertEqual(r.get(sid[0], session[0]), None)

    def testUser(self):
        u = User("State", {'team': 2}, "tf", "Someserver")
        self.assertTrue(u.valid())
        self.assertFalse(User("State").valid())


if __name__ == "__main__":
    # import sys;sys.argv = ['', 'Test.testName']
    unittest.main()
