#!/usr/bin/env python2
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

from threading import Thread
from Queue import Queue, Empty
from logging import getLogger

def local_thread(fu):
    """
    Decorator which makes a function execute in the local worker thread
    Return values are discarded
    """
    def new_fu(*args, **kwargs):
        self = args[0]
        self.message_queue().put((None, fu, args, kwargs))
    return new_fu

def local_thread_blocking(fu, timeout = None):
    """
    Decorator which makes a function execute in the local worker thread
    The function will block until return values are available or timeout
    seconds passed.
    
    @param timeout Timeout in seconds 
    """
    def new_fu(*args, **kwargs):
        self = args[0]
        out = Queue()
        self.message_queue().put((out, fu, args, kwargs))
        ret, ex =  out.get(True, timeout)
        if ex:
            raise ex
        
        return ret
    
    return new_fu


class Worker(Thread):
    def __init__(self, name, message_queue = None):
        """
        Implementation of a basic Queue based Worker thread.
        
        @param name Name of the thread to run the worker in
        @param message_queue Message queue on which to receive commands  
        """
        
        Thread.__init__(self, name = name)
        self.daemon = True
        self.__in = message_queue if message_queue != None else Queue()
        self.__log = getLogger(name)
        self.__name = name
    
    #--- Accessors
    def log(self):
        return self.__log
    
    def name(self):
        return self.__name
    
    def message_queue(self):
        return self.__in

    #--- Overridable convience stuff
    def onStart(self):
        """
        Override this function to perform actions on worker startup
        """
        pass
    
    def onStop(self):
        """
        Override this function to perform actions on worker shutdown
        """
        pass
    #--- Thread / Control
    def run(self):
        self.log().debug("Enter message loop")
        self.onStart()
        while True:
            msg = self.__in.get()
            if msg == None:
                break
            
            (out, fu, args, kwargs) = msg
            try:
                res = fu(*args, **kwargs)
                ex = None
            except Exception, e:
                self.log().exception(e)
                res = None
                ex = e
            finally:
                if not out is None:
                    out.put((res, ex))
                    
        self.onStop()
        self.log().debug("Leave message loop")
        
    def stop(self, force = True):
        if force:
            try:
                while True:
                    self.__in.get_nowait()
            except Empty:
                pass
        
        self.__in.put(None)
    
    #--- Helpers
    
    @local_thread
    def call_by_name(self, handler, function_name, *args, **kwargs):
        return getattr(handler, function_name)(*args, **kwargs)
    
    @local_thread_blocking
    def call_by_name_blocking(self, handler, function_name, *args, **kwargs):
        return getattr(handler, function_name)(*args, **kwargs)
