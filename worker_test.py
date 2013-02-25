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

import worker
from worker import Worker, local_thread, local_thread_blocking
from Queue import Queue
from logging.handlers import BufferingHandler
from logging import ERROR
import logging

from threading import Event
from time import sleep
    
class WorkerTest(unittest.TestCase):
    def setUp(self):
        
        def set_ev(fu):
            def new_fu(*args, **kwargs):
                s = args[0]
                s.event.set()
                s.val = (args, kwargs)
                return fu(*args, **kwargs)
            return new_fu
        
        class ATestWorker(Worker):
            def __init__(self, name, message_queue):
                Worker.__init__(self, name, message_queue)
                self.event = Event()
                self.val = None
                self.started = False
                self.stopped = False
            
            @local_thread
            @set_ev
            def echo(self, val):
                return val
            
            @local_thread_blocking
            @set_ev
            def echo_block(self, val):
                return val
            
            def onStart(self):
                self.started = True
                
            def onStop(self):
                self.stopped = True
                
            @local_thread
            def raise_(self, ex):
                raise ex
            
            @local_thread_blocking
            def raise_blocking(self, ex):
                raise ex
            
            @set_ev
            def call_me_by_name(self, arg1, arg2):
                return
            
            def call_me_by_name_blocking(self, arg1, arg2):
                return arg1, arg2
                
        
        self.buha = BufferingHandler(10000)
        
        q = Queue()
        self.q = q
        
        NAME = "Test"
        l = logging.getLogger(NAME)
        
        self.w = ATestWorker(NAME, q)
        self.assertEqual(self.w.log(), l)
        
        l.propagate = 0
        l.addHandler(self.buha)
        
        self.assertFalse(self.w.started)
        self.w.start()
        sleep(0.05)
        self.assertTrue(self.w.started)

    def testName(self):
        assert(self.w.name() == "Test")
        
    def testMessageQueue(self):
        assert(self.w.message_queue() == self.q)
        
    def testLocalThread(self):
        s = "Testing"
        self.w.event.clear()
        self.w.echo(s)
        self.w.event.wait(5)
        args, kwargs = self.w.val

        assert(args[1] == s)
        
    def testLocalThreadException(self):
        self.buha.flush()
        self.w.raise_(Exception())
        sleep(0.1) # hard delay
        assert(len(self.buha.buffer) != 0)
        assert(self.buha.buffer[0].levelno == ERROR)
    
    def testCallByName(self):
        self.w.event.clear()
        self.w.call_by_name(self.w, "call_me_by_name", "arg1", arg2="arg2")
        self.w.event.wait(5)
        args, kwargs = self.w.val
        
        assert(args[1] == "arg1")
        assert(kwargs["arg2"] == "arg2")
        
    def testLocalThreadBlocking(self):
        s = "Testing"
        assert(s == self.w.echo_block(s))
        
    def testLocalThreadExceptionBlocking(self):
        class TestException(Exception): pass
        self.assertRaises(TestException, self.w.raise_blocking, TestException())
        
    def testCallByNameBlocking(self):
        arg1, arg2 = self.w.call_by_name_blocking(self.w, "call_me_by_name_blocking", "arg1", arg2="arg2")

        assert(arg1 == "arg1")
        assert(arg2 == "arg2")

    def tearDown(self):
        assert(self.w.stopped == False)
        self.w.stop()
        self.w.join(5)
        assert(self.w.stopped == True)
        


if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()