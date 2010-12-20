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

import Queue
from worker import Worker, local_thread, local_thread_blocking
from config import Config
import sys
import os

class FailedLoadModuleException(Exception):
    pass

class FailedLoadModuleConfigException(FailedLoadModuleException):
    pass

class FailedLoadModuleImportException(FailedLoadModuleException):
    pass

class FailedLoadModuleInitializationException(FailedLoadModuleException):
    pass

def debug_log(enable = True):
    def new_dec(fu):
        def new_fu(*args, **kwargs):
            self = args[0]
            log = self.log()
            skwargs = ','.join(['%s=%s' % (karg,repr(arg)) for karg, arg in kwargs])
            sargs = ','.join([str(arg) for arg in args[1:]]) + '' if not skwargs else (',' + str(skwargs))
                
            call = "%s(%s)" % (fu.__name__, sargs)
            log.debug(call)
            res = fu(*args, **kwargs)
            log.debug("%s -> %s", call, repr(res))
            return res
        return new_fu if enable else fu
    return new_dec

    

debug_me = True

class MumoManagerRemote(object):
    """
    Manager object handed to MumoModules. This module
    acts as a remote for the MumoModule with which it
    can register/unregister to/from callbacks as well
    as do other signaling to the master MumoManager.
    """
    
    SERVERS_ALL = [-1] ## Applies to all servers
    
    def __init__(self, master, name, queue):
        self.__master = master
        self.__name = name
        self.__queue = queue
    
    def getQueue(self):
        return self.__queue
    
    def subscribeMetaCallbacks(self, handler, servers = SERVERS_ALL):
        """
        Subscribe to meta callbacks. Subscribes the given handler to the following
        callbacks:
        
        >>> started(self, server, context = None)
        >>> stopped(self, server, context = None)
        
        @param servers: List of server IDs for which to subscribe. To subscribe to all
                        servers pass SERVERS_ALL.
        @param handler: Object on which to call the callback functions 
        """
        return self.__master.subscribeMetaCallbacks(self.__queue, handler, servers)
    
    def unsubscribeMetaCallbacks(self, handler, servers = SERVERS_ALL):
        """
        Unsubscribe from meta callbacks. Unsubscribes the given handler from callbacks
        for the given servers.
        
        @param servers: List of server IDs for which to unsubscribe. To unsubscribe from all
                        servers pass SERVERS_ALL.
        @param handler: Subscribed handler
        """
        return self.__master.unscubscribeMetaCallbacks(self.__queue, handler, servers)
    
    def subscribeServerCallbacks(self, handler, servers = SERVERS_ALL):
        """
        Subscribe to server callbacks. Subscribes the given handler to the following
        callbacks:
        
        >>> userConnected(self, state, context = None)        
        >>> userDisconnected(self, state, context = None)
        >>> userStateChanged(self, state, context = None)
        >>> channelCreated(self, state, context = None)
        >>> channelRemoved(self, state, context = None)
        >>> channelStateChanged(self, state, context = None)
        
        @param servers: List of server IDs for which to subscribe. To subscribe to all
                        servers pass SERVERS_ALL.
        @param handler: Object on which to call the callback functions 
        """
        return self.__master.subscribeServerCallbacks(self.__queue, handler, servers)
    
    def unsubscribeServerCallbacks(self, handler, servers = SERVERS_ALL):
        """
        Unsubscribe from server callbacks. Unsubscribes the given handler from callbacks
        for the given servers.
        
        @param servers: List of server IDs for which to unsubscribe. To unsubscribe from all
                        servers pass SERVERS_ALL.
        @param handler: Subscribed handler
        """
        return self.__master.unsubscribeServerCallbacks(self.__queue, handler, servers)
    
    def subscribeContextCallbacks(self, handler, servers = SERVERS_ALL):
        """
        Subscribe to context callbacks. Subscribes the given handler to the following
        callbacks:
        
        >>> contextAction(self, action, user, session, channelid, context = None)
        
        @param servers: List of server IDs for which to subscribe. To subscribe to all
                        servers pass SERVERS_ALL.
        @param handler: Object on which to call the callback functions 
        """
        return self.__master.subscribeContextCallbacks(self.__queue, handler, servers)
    
    def unsubscribeContextCallbacks(self, handler, servers = SERVERS_ALL):
        """
        Unsubscribe from context callbacks. Unsubscribes the given handler from callbacks
        for the given servers.
        
        @param servers: List of server IDs for which to unsubscribe. To unsubscribe from all
                        servers pass SERVERS_ALL.
        @param handler: Subscribed handler
        """
        return self.__master.unsubscribeContextCallbacks(self.__queue, handler, servers)
    
    def getMurmurModule(self):
        """
        Returns the Murmur module generated from the slice file
        """
        return self.__master.getMurmurModule()
    
    def getMeta(self):
        """
        Returns the connected servers meta module or None if it is not available
        """
        return self.__master.getMeta()

    
class MumoManager(Worker):
    MAGIC_ALL = -1

    cfg_default = {'modules':(('mod_dir', str, "modules/"),
                              ('cfg_dir', str, "modules-enabled/"),
                              ('timeout', int, 2))}
    
    def __init__(self, murmur, cfg = Config(default = cfg_default)):
        Worker.__init__(self, "MumoManager")
        self.queues = {} # {queue:module}
        self.modules = {} # {name:module}
        self.imports = {} # {name:import}
        self.cfg = cfg
        
        self.murmur = murmur
        self.meta = None
        
        self.metaCallbacks = {} # {sid:{queue:[handler]}}
        self.serverCallbacks = {}
        self.contextCallbacks = {}
    
    def __add_to_dict(self, mdict, queue, handler, servers):
        for server in servers:
            if server in mdict:
                if queue in mdict[server]:
                    if not handler in mdict[server][queue]:
                        mdict[server][queue].append(handler)
                else:
                    mdict[server][queue] = [handler]
            else:
                mdict[server] = {queue:[handler]}
    
    def __rem_from_dict(self, mdict, queue, handler, servers):
        for server in servers:
            try:
                mdict[server][queue].remove(handler)
            except KeyError, ValueError:
                pass
            
    def __announce_to_dict(self, mdict, server, function, *args, **kwargs):
        """
        Call function on handlers for specific servers in one of our handler
        dictionaries.
        
        @param mdict Dictionary to announce to
        @param server Server to announce to, ALL is always implied
        @param function Function the handler should call
        @param args Arguments for the function
        @param kwargs Keyword arguments for the function
        """
        
        # Announce to all handlers of the given serverlist
        if server == self.MAGIC_ALL:
            servers = mdict.iterkeys()
        else:
            servers = [self.MAGIC_ALL, server]
            
        for server in servers:
            try:
                for queue, handlers in mdict[server].iteritems():
                    for handler in handlers:
                        self.__call_remote(queue, handler, function, *args, **kwargs)
            except KeyError:
                # No handler registered for that server
                pass
    
    def __call_remote(self, queue, handler, function, *args, **kwargs):
        try:
            func = getattr(handler, function) # Find out what to call on target
            queue.put((None, func, args, kwargs))
        except AttributeError, e:
            mod = self.queues.get(queue, None)
            myname = ""
            for name, mymod in self.modules.iteritems():
                if mod == mymod:
                    myname = name
            if myname:
                self.log().error("Handler class registered by module '%s' does not handle function '%s'. Call failed.", myname, function)
            else:
                self.log().exception(e)

    
    #
    #-- Module multiplexing functionality
    #
    
    @local_thread
    def announceConnected(self, meta = None):
        """
        Call connected handler on all handlers
        """
        self.meta = meta
        for queue, module in self.queues.iteritems():
            self.__call_remote(queue, module, "connected")
            
    @local_thread
    def announceDisconnected(self):
        """
        Call disconnected handler on all handlers
        """
        for queue, module in self.queues.iteritems():
            self.__call_remote(queue, module, "disconnected")

    @local_thread
    def announceMeta(self, server, function, *args, **kwargs):
        """
        Call a function on the meta handlers
        
        @param server Servers to announce to
        @param function Name of the function to call on the handler
        @param args List of arguments
        @param kwargs List of keyword arguments
        """
        self.__announce_to_dict(self.metaCallbacks, server, function, *args, **kwargs)
        
    @local_thread
    def announceServer(self, server, function, *args, **kwargs):
        """
        Call a function on the server handlers
        
        @param server Server to announce to
        @param function Name of the function to call on the handler
        @param args List of arguments
        @param kwargs List of keyword arguments
        """
        self.__announce_to_dict(self.serverCallbacks, server, function, *args, **kwargs)
        
    @local_thread
    def announceContext(self, server, function, *args, **kwargs):
        """
        Call a function on the context handlers
        
        @param server Server to announce to
        @param function Name of the function to call on the handler
        @param args List of arguments
        @param kwargs List of keyword arguments
        """
        self.__announce_to_dict(self.serverCallbacks, server, function, *args, **kwargs)
    #
    #--- Module self management functionality
    #
    
    @local_thread
    def subscribeMetaCallbacks(self, queue, handler, servers):
        """
        @param queue Target worker queue
        @see MumoManagerRemote
        """
        return self.__add_to_dict(self.metaCallbacks, queue, handler, servers)
    
    @local_thread
    def unsubscribeMetaCallbacks(self, queue, handler, servers):
        """
        @param queue Target worker queue
        @see MumoManagerRemote
        """
        return self.__rem_from_dict(self.metaCallbacks, queue, handler, servers)
    
    @local_thread
    def subscribeServerCallbacks(self, queue, handler, servers):
        """
        @param queue Target worker queue
        @see MumoManagerRemote
        """
        return self.__add_to_dict(self.serverCallbacks, queue, handler, servers)
    
    @local_thread
    def unsubscribeServerCallbacks(self, queue, handler, servers):
        """
        @param queue Target worker queue
        @see MumoManagerRemote
        """
        return self.__rem_from_dict(self.serverCallbacks, queue, handler, servers)
    
    @local_thread
    def subscribeContextCallbacks(self, queue, handler, servers):
        """
        @param queue Target worker queue
        @see MumoManagerRemote
        """
        return self.__add_to_dict(self.contextCallbacks, queue, handler, servers)
    
    @local_thread
    def unsubscribeContextCallbacks(self, queue, handler, servers):
        """
        @param queue Target worker queue
        @see MumoManagerRemote
        """
        return self.__rem_from_dict(self.contextCallbacks, queue, handler, servers)

    def getMurmurModule(self):
        """
        Returns the Murmur module generated from the slice file
        """
        return self.murmur
    
    def getMeta(self):
        """
        Returns the connected servers meta module or None if it is not available
        """
        return self.meta
    
    #--- Module load/start/stop/unload functionality
    #
    @local_thread_blocking
    @debug_log(debug_me)
    def loadModules(self, names = None):
        """
        Loads a list of modules from the mumo directory structure by name.
        
        @param names List of names of modules to load
        @return: List of modules loaded
        """
        loadedmodules = {}
        
        if not names:
            # If no names are given load all modules that have a configuration in the cfg_dir
            if not os.path.isdir(self.cfg.modules.cfg_dir):
                msg = "Module directory '%s' not found" % self.cfg.modules.mod_dir
                self.log().error(msg)
                raise FailedLoadModuleImportException(msg)
            
            names = []
            for f in os.listdir(self.cfg.modules.cfg_dir):
                if os.path.isfile(self.cfg.modules.cfg_dir + f):
                    base, ext = os.path.splitext(f)
                    if not ext or ext.lower() == ".ini" or ext.lower() == ".conf":
                        names.append(base)
            
        for name in names:
            try:
                modinst = self._loadModule_noblock(name)
                loadedmodules[name] =  modinst
            except FailedLoadModuleException:
                pass
        
        return loadedmodules
        
    @local_thread_blocking
    def loadModuleCls(self, name, modcls, module_cfg = None):
        return self._loadModuleCls_noblock(name, modcls, module_cfg)
        
    @debug_log(debug_me)
    def _loadModuleCls_noblock(self, name, modcls, module_cfg = None):
        log = self.log()

        if name in self.modules:
            log.error("Module '%s' already loaded", name)
            return
        
        modqueue = Queue.Queue()
        modmanager = MumoManagerRemote(self, name, modqueue)
        
        try:
            modinst = modcls(name, modmanager, module_cfg)
        except Exception, e:
            msg = "Module '%s' failed to initialize" % name
            log.error(msg)
            log.exception(e)
            raise FailedLoadModuleInitializationException(msg)
        
        # Remember it
        self.modules[name] = modinst
        self.queues[modqueue] = modinst
        
        return modinst
        
    @local_thread_blocking
    def loadModule(self, name):
        """
        Loads a single module either by name
        
        @param name Name of the module to load
        @return Module instance
        """
        self._loadModule_noblock(name)
        
    @debug_log(debug_me)
    def _loadModule_noblock(self, name): 
        # Make sure this module is not already loaded
        log = self.log()
        log.debug("loadModuleByName('%s')", name)
        
        if name in self.modules:
            log.warning("Tried to load already loaded module %s", name)
            return
        
        # Check whether there is a configuration file for this module
        confpath = self.cfg.modules.cfg_dir + name + '.ini'
        if not os.path.isfile(confpath):
            msg = "Module configuration file '%s' not found" % confpath
            log.error(msg)
            raise FailedLoadModuleConfigException(msg)
        
        # Make sure the module directory is in our python path and exists
        if not self.cfg.modules.mod_dir in sys.path:
            if not os.path.isdir(self.cfg.modules.mod_dir):
                msg = "Module directory '%s' not found" % self.cfg.modules.mod_dir
                log.error(msg)
                raise FailedLoadModuleImportException(msg)
            sys.path.insert(0, self.cfg.modules.mod_dir)
    
        # Import the module and instanciate it
        try:
            mod = __import__(name)
            self.imports[name] = mod
        except ImportError, e:
            msg = "Failed to import module '%s', reason: %s" % (name, str(e))
            log.error(msg)
            raise FailedLoadModuleImportException(msg)
        
        try:
            try:
                modcls = mod.mumo_module_class # First check if there's a magic mumo_module_class variable
                log.debug("Magic mumo_module_class found")
            except AttributeError:
                modcls = getattr(mod, name)
        except AttributeError:
            msg = "Module does not contain required class '%s'" % name
            log.error(msg)
            raise FailedLoadModuleInitializationException(msg)

        return self._loadModuleCls_noblock(name, modcls, confpath)
            
    @local_thread_blocking
    @debug_log(debug_me)
    def startModules(self, names = None):
        """
        Start a module by name
        
        @param names List of names of modules to start
        @return A dict of started module names and instances
        """
        log = self.log()
        startedmodules = {}
        
        if not names:
            # If no names are given start all models
            names = self.modules.iterkeys()
            
        for name in names:
            try:
                modinst = self.modules[name]
                if not modinst.is_alive():
                    modinst.start()
                    log.debug("Module '%s' started", name)
                else:
                    log.debug("Module '%s' already running", name)
                startedmodules[name] = modinst
            except KeyError:
                log.error("Could not start unknown module '%s'", name)
        
        return startedmodules
    
    @local_thread_blocking
    @debug_log(debug_me)
    def stopModules(self, names = None, force = False):
        """
        Stop a list of modules by name. Note that this only works
        for well behaved modules. At this point if a module is really going
        rampant you will have to restart mumo.
        
        @param names List of names of modules to unload
        @param force Unload the module asap dropping messages queued for it
        @return A dict of stopped module names and instances
        """
        log = self.log()
        stoppedmodules = {}
        
        if not names:
            # If no names are given start all models
            names = self.modules.iterkeys()
            
        for name in names:
            try:
                modinst = self.modules[name]
                stoppedmodules[name] = modinst
            except KeyError:
                log.warning("Asked to stop unknown module '%s'", name)
                continue
        
        if force:
            # We will have to drain the modules queues
            for queue, module in self.queues.iteritems():
                if module in self.modules:
                    try:
                        while queue.get_nowait(): pass
                    except Queue.Empty: pass

        for modinst in stoppedmodules.itervalues():
            if modinst.is_alive():
                modinst.stop()
                log.debug("Module '%s' is being stopped", name)
            else:
                log.debug("Module '%s' already stopped", name)
        
        for modinst in stoppedmodules.itervalues():
            modinst.join(timeout = self.cfg.modules.timeout)
        
        return stoppedmodules
    
    def stop(self, force = True):
        self.log().debug("Stopping")
        self.stopModules()
        Worker.stop(self, force)
