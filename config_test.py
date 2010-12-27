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
from config import Config, x2bool, commaSeperatedIntegers, commaSeperatedStrings, commaSeperatedBool
from tempfile import mkstemp
import os
import re

def create_file(content = None):
    """
    Creates a temp file filled with 'content' and returns its path.
    The file has to be manually deleted later on
    """
    fd, path = mkstemp()
    f = os.fdopen(fd, "wb")
    if content:
        f.write(content)
    f.flush()
    f.close()
    return path

class ConfigTest(unittest.TestCase):
    cfg_content = """[world]
domination = True
somestr = Blabla
somenum = 10
testfallbacknum = asdas
[Server_10]
value = False
[Server_9]
[Server_2]
value = True
"""
    
    cfg_default = {'world':(('domination', x2bool, False),
                           ('somestr', str, "fail"),
                           ('somenum', int, 0),
                           ('somenumtest', int, 1)),
                    (lambda x: re.match("Server_\d+",x)):(('value', x2bool, True),),
                   'somethingelse':(('bla', str, "test"),)}

    def setUp(self):
        pass

    def tearDown(self):
        pass


    def testEmpty(self):
        path = create_file()
        try:
            cfg = Config(path, self.cfg_default)
            assert(cfg.world.domination == False)
            assert(cfg.world.somestr == "fail")
            assert(cfg.world.somenum == 0)
            self.assertRaises(AttributeError, getattr, cfg.world, "testfallbacknum")
            assert(cfg.somethingelse.bla == "test")
        finally:
            os.remove(path)
    
    def testX2bool(self):
        assert(x2bool(" true") == True)
        assert(x2bool("false") == False)
        assert(x2bool(" TrUe") == True)
        assert(x2bool("FaLsE ") == False)
        assert(x2bool("0 ") == False)
        assert(x2bool("1") == True)
        assert(x2bool(" 10") == False)
        assert(x2bool("notabool") == False)
        
    def testCommaSeperatedIntegers(self):
        assert(commaSeperatedIntegers(" 1,2 , 333 ") == [1,2,333])
        self.assertRaises(ValueError, commaSeperatedIntegers, "1,2,a")
    
    def testCommaSeperatedStrings(self):
        assert(commaSeperatedStrings("Bernd, the, bred !") == ["Bernd", "the", "bred !"])
    
    def testCommaSeperatedBool(self):
        assert(commaSeperatedBool("tRue ,false, 0, 0, 1,1, test") == [True, False, False, False, True, True, False])
        
    def testConfig(self):
        path = create_file(self.cfg_content)
        try:
            try:
                cfg = Config(path, self.cfg_default)
            except Exception, e:
                print e
            assert(cfg.world.domination == True)
            assert(cfg.world.somestr == "Blabla")
            assert(cfg.world.somenum == 10)
            self.assertRaises(AttributeError, getattr, cfg.world, "testfallbacknum")
            assert(cfg.somethingelse.bla == "test")
            assert(cfg.Server_10.value == False)
            assert(cfg.Server_2.value == True)
            assert(cfg.Server_9.value == True)
        finally:
            os.remove(path)
            
    def testLoadDefault(self):
        cfg = Config(default=self.cfg_default)
        assert(cfg.world.domination == False)
        assert(cfg.somethingelse.bla == "test")
        assert(cfg.world.somenum == 0)


if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()