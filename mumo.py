#!/usr/bin/env python2
# -*- coding: utf-8

# Copyright (C) 2010-2013 Stefan Hacker <dd0t@users.sourceforge.net>
# Copyright (C) 2018 Jonas Herzig <me@johni0702.de>
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

import os
import sys
import logging
import tempfile
import time
from collections import defaultdict
from config import (Config,
                    x2bool,
                    commaSeperatedIntegers)

from worker     import Worker, local_thread, local_thread_blocking
from threading  import Thread, Timer
from optparse   import OptionParser
from logging    import (debug,
                        info,
                        warning,
                        error,
                        critical,
                        exception,
                        getLogger)
from mumo_manager import MumoManager

#
#--- Default configuration values
#
cfgfile = 'mumo.ini'
default = MumoManager.cfg_default.copy()
default.update({'ice':(('host', str, '127.0.0.1'),
                      ('port', int, 6502),
                      ('slice', str, ''),
                      ('secret', str, ''),
                      ('slicedirs', str, '/usr/share/slice;/usr/share/Ice/slice'),
                      ('watchdog', int, 30),
                      ('callback_host', str, '127.0.0.1'),
                      ('callback_port', int, -1)),

                'grpc':(('active', bool, False),
                      ('host', str, '127.0.0.1'),
                      ('port', int, 50051)),

               'iceraw':None,
               'murmur':(('servers', commaSeperatedIntegers, []),),
               'system':(('pidfile', str, 'mumo.pid'),),
               'log':(('level', int, logging.DEBUG),
                      ('file', str, 'mumo.log'))})

def load_slice(slice):
    #
    #--- Loads a given slicefile, used by dynload_slice and fsload_slice
    #    This function works around a number of differences between Ice python
    #    versions and distributions when it comes to slice include directories.
    #
    import Ice
    fallback_slicedirs = ["-I" + sdir for sdir in cfg.ice.slicedirs.split(';')]

    if not hasattr(Ice, "getSliceDir"):
        Ice.loadSlice('-I%s %s' % (" ".join(fallback_slicedirs), slice))
    else:
        slicedir = Ice.getSliceDir()
        if not slicedir:
            slicedirs = fallback_slicedirs
        else:
            slicedirs = ['-I' + slicedir]

        Ice.loadSlice('', slicedirs + [slice])

def dynload_slice(prx):
    #
    #--- Dynamically retrieves the slice file from the target server
    #
    import Ice
    import IcePy
    info("Loading slice from server")
    try:
        # Check IcePy version as this internal function changes between version.
        # In case it breaks with future versions use slice2py and search for
        # "IcePy.Operation('getSlice'," for updates in the generated bindings.
        op = None
        if IcePy.intVersion() < 30500L:
            # Old 3.4 signature with 9 parameters
            op = IcePy.Operation('getSlice', Ice.OperationMode.Idempotent, Ice.OperationMode.Idempotent, True, (), (), (), IcePy._t_string, ())

        else:
            # New 3.5 signature with 10 parameters.
            op = IcePy.Operation('getSlice', Ice.OperationMode.Idempotent, Ice.OperationMode.Idempotent, True, None, (), (), (), ((), IcePy._t_string, False, 0), ())

        slice = op.invoke(prx, ((), None))
        (dynslicefiledesc, dynslicefilepath)  = tempfile.mkstemp(suffix = '.ice')
        dynslicefile = os.fdopen(dynslicefiledesc, 'w')
        dynslicefile.write(slice)
        dynslicefile.flush()
        load_slice(dynslicefilepath)
        dynslicefile.close()
        os.remove(dynslicefilepath)
    except Exception, e:
        error("Retrieving slice from server failed")
        exception(e)
        raise


def fsload_slice(slice):
    #
    #--- Load slice from file system
    #
    debug("Loading slice from filesystem: %s" % slice)
    load_slice(slice)

def do_ice_main_program():
    #
    #--- Moderator implementation
    #    All of this has to go in here so we can correctly daemonize the tool
    #    without loosing the file descriptors opened by the Ice module

    import Ice
    import IcePy

    debug('Initializing Ice')
    initdata = Ice.InitializationData()
    initdata.properties = Ice.createProperties([], initdata.properties)
    for prop, val in cfg.iceraw:
        initdata.properties.setProperty(prop, val)

    initdata.properties.setProperty('Ice.ImplicitContext', 'Shared')
    initdata.properties.setProperty('Ice.Default.EncodingVersion', '1.0')
    initdata.logger = CustomLogger()

    ice = Ice.initialize(initdata)
    prxstr = 'Meta:tcp -h %s -p %d' % (cfg.ice.host, cfg.ice.port)
    prx = ice.stringToProxy(prxstr)

    if not cfg.ice.slice:
        dynload_slice(prx)
    else:
        fsload_slice(cfg.ice.slice)

    import Murmur

    class mumoIceApp(Ice.Application):
        def __init__(self, manager):
            Ice.Application.__init__(self)
            self.manager = manager

        def run(self, args):
            self.shutdownOnInterrupt()

            if not self.initializeIceConnection():
                return 1

            if cfg.ice.watchdog > 0:
                self.metaUptime = -1
                self.checkConnection()

            # Serve till we are stopped
            self.communicator().waitForShutdown()
            self.watchdog.cancel()

            if self.interrupted():
                warning('Caught interrupt, shutting down')

            return 0

        def initializeIceConnection(self):
            """
            Establishes the two-way Ice connection and adds MuMo to the
            configured servers
            """
            ice = self.communicator()

            if cfg.ice.secret:
                debug('Using shared ice secret')
                ice.getImplicitContext().put("secret", cfg.ice.secret)
            else:
                warning('Consider using an ice secret to improve security')

            info('Connecting to Ice server (%s:%d)', cfg.ice.host, cfg.ice.port)
            base = ice.stringToProxy(prxstr)
            self.meta = Murmur.MetaPrx.uncheckedCast(base)

            if cfg.ice.callback_port > 0:
                cbp = ' -p %d' % cfg.ice.callback_port
            else:
                cbp = ''

            adapter = ice.createObjectAdapterWithEndpoints('Callback.Client', 'tcp -h %s%s' % (cfg.ice.callback_host, cbp))
            adapter.activate()
            self.adapter = adapter
            self.manager.setClientAdapter(adapter)

            metacbprx = adapter.addWithUUID(metaCallback(self))
            self.metacb = Murmur.MetaCallbackPrx.uncheckedCast(metacbprx)

            return self.attachCallbacks()

        def attachCallbacks(self):
            """
            Attaches all callbacks
            """

            # Ice.ConnectionRefusedException
            debug('Attaching callbacks')
            try:
                info('Attaching meta callback')
                self.meta.addCallback(self.metacb)

                for server in self.meta.getBootedServers():
                    sid = server.id()
                    if not cfg.murmur.servers or sid in cfg.murmur.servers:
                        info('Setting callbacks for virtual server %d', sid)
                        servercbprx = self.adapter.addWithUUID(serverCallback(self.manager, server, sid))
                        servercb = Murmur.ServerCallbackPrx.uncheckedCast(servercbprx)
                        server.addCallback(servercb)

            except (Murmur.InvalidSecretException, Ice.UnknownUserException, Ice.ConnectionRefusedException), e:
                if isinstance(e, Ice.ConnectionRefusedException):
                    error('Server refused connection')
                elif isinstance(e, Murmur.InvalidSecretException) or \
                     isinstance(e, Ice.UnknownUserException) and (e.unknown == 'Murmur::InvalidSecretException'):
                    error('Invalid ice secret')
                else:
                    # We do not actually want to handle this one, re-raise it
                    raise e

                self.connected = False
                self.manager.announceDisconnected()
                return False

            self.connected = True
            self.manager.announceConnected(self.meta)
            return True

        def checkConnection(self):
            """
            Tries to retrieve the server uptime to determine wheter the server is
            still responsive or has restarted in the meantime
            """
            #debug('Watchdog run')
            try:
                uptime = self.meta.getUptime()
                if self.metaUptime > 0:
                    # Check if the server didn't restart since we last checked, we assume
                    # since the last time we ran this check the watchdog interval +/- 5s
                    # have passed. This should be replaced by implementing a Keepalive in
                    # Murmur.
                    if not ((uptime - 5) <= (self.metaUptime + cfg.ice.watchdog) <= (uptime + 5)):
                        # Seems like the server restarted, re-attach the callbacks
                        self.attachCallbacks()

                self.metaUptime = uptime
            except Ice.Exception, e:
                error('Connection to server lost, will try to reestablish callbacks in next watchdog run (%ds)', cfg.ice.watchdog)
                debug(str(e))
                self.attachCallbacks()

            # Renew the timer
            self.watchdog = Timer(cfg.ice.watchdog, self.checkConnection)
            self.watchdog.start()

    def checkSecret(func):
        """
        Decorator that checks whether the server transmitted the right secret
        if a secret is supposed to be used.
        """
        if not cfg.ice.secret:
            return func

        def newfunc(*args, **kws):
            if 'current' in kws:
                current = kws["current"]
            else:
                current = args[-1]

            if not current or 'secret' not in current.ctx or current.ctx['secret'] != cfg.ice.secret:
                error('Server transmitted invalid secret. Possible injection attempt.')
                raise Murmur.InvalidSecretException()

            return func(*args, **kws)

        return newfunc

    def fortifyIceFu(retval=None, exceptions=(Ice.Exception,)):
        """
        Decorator that catches exceptions,logs them and returns a safe retval
        value. This helps to prevent getting stuck in
        critical code paths. Only exceptions that are instances of classes
        given in the exceptions list are not caught.

        The default is to catch all non-Ice exceptions.
        """
        def newdec(func):
            def newfunc(*args, **kws):
                try:
                    return func(*args, **kws)
                except Exception, e:
                    catch = True
                    for ex in exceptions:
                        if isinstance(e, ex):
                            catch = False
                            break

                    if catch:
                        critical('Unexpected exception caught')
                        exception(e)
                        return retval
                    raise

            return newfunc
        return newdec

    class metaCallback(Murmur.MetaCallback):
        def __init__(self, app):
            Murmur.MetaCallback.__init__(self)
            self.app = app

        @fortifyIceFu()
        @checkSecret
        def started(self, server, current=None):
            """
            This function is called when a virtual server is started
            and makes sure the callbacks get attached if needed.
            """
            sid = server.id()
            if not cfg.murmur.servers or sid in cfg.murmur.servers:
                info('Setting callbacks for virtual server %d', server.id())
                try:
                    servercbprx = self.app.adapter.addWithUUID(serverCallback(self.app.manager, server, sid))
                    servercb = Murmur.ServerCallbackPrx.uncheckedCast(servercbprx)
                    server.addCallback(servercb)

                # Apparently this server was restarted without us noticing
                except (Murmur.InvalidSecretException, Ice.UnknownUserException), e:
                    if hasattr(e, "unknown") and e.unknown != "Murmur::InvalidSecretException":
                        # Special handling for Murmur 1.2.2 servers with invalid slice files
                        raise e

                    error('Invalid ice secret')
                    return
            else:
                debug('Virtual server %d got started', sid)

            self.app.manager.announceMeta(sid, "started", server, current)

        @fortifyIceFu()
        @checkSecret
        def stopped(self, server, current=None):
            """
            This function is called when a virtual server is stopped
            """
            if self.app.connected:
                # Only try to output the server id if we think we are still connected to prevent
                # flooding of our thread pool
                try:
                    sid = server.id()
                    if not cfg.murmur.servers or sid in cfg.murmur.servers:
                        info('Watched virtual server %d got stopped', sid)
                    else:
                        debug('Virtual server %d got stopped', sid)
                    self.app.manager.announceMeta(sid, "stopped", server, current)
                    return
                except Ice.ConnectionRefusedException:
                    self.app.connected = False
                    self.app.manager.announceDisconnected()

            debug('Server shutdown stopped a virtual server')


    def forwardServer(fu):
        def new_fu(self, *args, **kwargs):
            self.manager.announceServer(self.sid, fu.__name__, self.server, *args, **kwargs)
        return new_fu

    class serverCallback(Murmur.ServerCallback):
        def __init__(self, manager, server, sid):
            Murmur.ServerCallback.__init__(self)
            self.manager = manager
            self.sid = sid
            self.server = server

            # Hack to prevent every call to server.id() from the client callbacks
            # from having to go over Ice
            def id_replacement():
                return self.sid

            server.id = id_replacement

        @checkSecret
        @forwardServer
        def userStateChanged(self, u, current=None): pass
        @checkSecret
        @forwardServer
        def userDisconnected(self, u, current=None): pass
        @checkSecret
        @forwardServer
        def userConnected(self, u, current=None): pass
        @checkSecret
        @forwardServer
        def channelCreated(self, c, current=None): pass
        @checkSecret
        @forwardServer
        def channelRemoved(self, c, current=None): pass
        @checkSecret
        @forwardServer
        def channelStateChanged(self, c, current=None): pass
        @checkSecret
        @forwardServer
        def userTextMessage(self, u, m, current=None) : pass

    class customContextCallback(Murmur.ServerContextCallback):
        def __init__(self, contextActionCallback, *ctx):
            Murmur.ServerContextCallback.__init__(self)
            self.cb = contextActionCallback
            self.ctx = ctx

        @checkSecret
        def contextAction(self, *args, **argv):
            # (action, user, target_session, target_chanid, current=None)
            self.cb(*(self.ctx + args), **argv)

    class CustomLogger(Ice.Logger):
        """
        Logger implementation to pipe Ice log messages into
        our own log
        """

        def __init__(self):
            Ice.Logger.__init__(self)
            self._log = getLogger('Ice')

        def _print(self, message):
            self._log.info(message)

        def trace(self, category, message):
            self._log.debug('Trace %s: %s', category, message)

        def warning(self, message):
            self._log.warning(message)

        def error(self, message):
            self._log.error(message)

    #
    #--- Start of moderator
    #
    info('Starting mumble moderator')
    debug('Initializing manager')
    manager = MumoManager(Murmur, customContextCallback)
    manager.start()
    manager.loadModules()
    manager.startModules()

    debug("Initializing mumoIceApp")
    app = mumoIceApp(manager)
    state = app.main(sys.argv[:1], initData=initdata)

    manager.stopModules()
    manager.stop()
    info('Shutdown complete')
    return state

def grpc_connect(host, port):
    """
    Utility function for using/testing the gRPC-Ice bridge from the REPL.
    Callbacks are not supported when using this function.

    >>> from mumo import grpc_connect
    >>> meta = grpc_connect('10.137.7.1', 50051)
    >>> meta.getUptime()
    146789L
    """
    import grpc
    import MurmurRPC_pb2_grpc

    channel = grpc.insecure_channel('%s:%d' % (host, port))
    stub = MurmurRPC_pb2_grpc.V1Stub(channel)

    sys.path.append(os.path.dirname(os.path.abspath(__file__)) + '/grpc')
    import Murmur

    return Murmur.Meta(None, stub)

def do_grpc_main_program():
    debug('Initializing gRPC')

    import grpc
    import MurmurRPC_pb2
    import MurmurRPC_pb2_grpc
    Void = MurmurRPC_pb2.Void()

    info('Connecting to gRPC server (%s:%d)', cfg.grpc.host, cfg.grpc.port)
    channel = grpc.insecure_channel('%s:%d' % (cfg.grpc.host, cfg.grpc.port))
    stub = MurmurRPC_pb2_grpc.V1Stub(channel)

    sys.path.append(os.path.dirname(os.path.abspath(__file__)) + '/grpc')
    import Murmur

    class serverListener(Thread):
        """
        Reads from a server event stream and forwards events to the app.
        Note that self.callbacks is owned by the app worker thread and
        must not be accessed from the outside.
        """
        def __init__(self, app, sid):
            Thread.__init__(self, name='gRPC server event reader %d' % sid)
            self.daemon = True
            self.app = app
            self.sid = sid
            self.callbacks = []
            self.shutdown = False
            self.stream = None

        def run(self):
            try:
                server = MurmurRPC_pb2.Server(id=self.sid)
                self.stream = stub.ServerEvents(server)
                if self.shutdown:
                    self.stream.cancel()
                    return
                for event in self.stream:
                    self.app.onServerEvent(self, event)
            except grpc.RpcError:
                if not self.shutdown:
                    raise
            finally:
                debug('exiting server listener %d' % self.sid)

        def stop(self):
            debug('stopping server listener %d' % self.sid)
            self.shutdown = True
            if self.stream:
                self.stream.cancel()

    class contextListener(Thread):
        """
        Reads from a context event stream and forwards events to the app.
        """
        def __init__(self, app, sid, action):
            Thread.__init__(self, name='gRPC context event reader %d/"%s"'
                                       % (sid, action))
            self.app = app
            self.sid = sid
            self.action = action
            self.shutdown = False
            self.stream = None

        def run(self):
            contextAction = MurmurRPC_pb2.ContextAction(
                    server=MurmurRPC_pb2.Server(id=self.sid),
                    action=self.action)
            try:
                self.stream = stub.ContextActionEvents(contextAction)
                if self.shutdown:
                    self.stream.cancel()
                    return
                for event in self.stream:
                    self.app.onContextEvent(self, event)
            except grpc.RpcError:
                if not self.shutdown:
                    raise
            finally:
                debug('exiting context listener %d/"%s"'
                      % (self.sid, self.action))

        def stop(self):
            debug('stopping context listener %d/"%s"'
                  % (self.sid, self.action))
            self.shutdown = True
            if self.stream:
                self.stream.cancel()

    class mumoGrpcApp(Worker):
        def __init__(self, manager):
            Worker.__init__(self, 'mumo gRPC app')
            self.manager = manager
            self.shutdown = False
            self.stream = None
            self.connected = False
            self.metaCallbacks = [metaCallback(self)]
            # Dict[sid, listener]
            self.serverListeners = {}
            # Dict[sid, Dict[session, Dict[action, callback]]]
            self.contextCallbacks = defaultdict(lambda: defaultdict(dict))
            # Dict[sid, Dict[action, listener]]
            self.contextListeners = defaultdict(dict)

            self.meta = Murmur.Meta(self, stub)
            self.adapter = Murmur.ClientAdapter()
            self.manager.setClientAdapter(self.adapter)

            self.stream = stub.Events(Void)

            for server in self.meta.getBootedServers():
                self.ensureListeningOnServer(server)

        def start(self):
            """
            Starts the meta event listener and the app worker thread.
            """
            thread = Thread(name="gRPC meta event listener",
                            target=self.mainLoop)
            thread.daemon = True
            thread.start()
            Worker.start(self)

        @local_thread_blocking
        def stop(self):
            debug('stopping meta listener / main loop')
            self.shutdown = True
            if self.stream:
                self.stream.cancel()
            self._cleanupListeners()
            Worker.stop(self)

        def _cleanupListeners(self):
            """
            Cleans up all listeners that are invalid after the connection
            has been lost.
            The meta listener is already invalidated when this method
            is called because it is the one that detects the disconnects.
            """
            for listener in self.serverListeners.values():
                listener.stop()
            self.serverListeners.clear()
            for listener in sum([actionMap.values()
                                 for actionMap
                                 in self.contextListeners.values()], []):
                listener.stop()
            self.contextListeners.clear()
            self.contextCallbacks.clear()

        def mainLoop(self):
            while True:
                self.connected = True
                self.manager.announceConnected(self.meta)
                if self.shutdown:
                    self.stream.cancel()
                    break
                try:
                    for event in self.stream:
                        if event.type == event.Type.Value('ServerStarted'):
                            for cb in self.metaCallbacks:
                                cb.started(event.server.id)
                        elif event.type == event.Type.Value('ServerStopped'):
                            for cb in self.metaCallbacks:
                                cb.stopped(event.server.id)
                except grpc.RpcError, e:
                    self.connected = False
                    self.manager.announceDisconnected()
                    if self.shutdown:
                        break
                    if e.code() in [grpc.StatusCode.UNAVAILABLE,
                                    grpc.StatusCode.INTERNAL,
                                    grpc.StatusCode.UNKNOWN]:
                        exception(e)
                        self._cleanupListeners()
                        # try to reconnect
                        while not self.shutdown:
                            try:
                                stub.GetUptime(Void)
                                break
                            except grpc.RpcError, e:
                                exception(e)
                                time.sleep(10)
                        self.stream = stub.Events(Void)
                        for server in self.meta.getBootedServers():
                            self.ensureListeningOnServer(server)
                        continue
                    raise
            debug('exiting meta listener / main loop')

        def ensureListeningOnServer(self, server):
            """
            Ensures that a server event listener for the specified server
            is running.
            If this is not the case and the server is enabled in the config,
            starts a new one.
            """
            sid = server.id()

            if sid in self.serverListeners: return
            if cfg.murmur.servers and sid in cfg.murmur.servers: return

            info('Setting callbacks for virtual server %d', sid)

            listener = serverListener(self, sid)
            self.serverListeners[sid] = listener
            listener.start()

            callback = serverCallback(self, self.manager, server, sid)
            listener.callbacks.append(callback)

        @local_thread
        def onServerEvent(self, listener, event):
            if listener.shutdown: return
            callbacks = listener.callbacks
            user = Murmur.toIce(event.user)
            channel = Murmur.toIce(event.channel)
            message = Murmur.toIce(event.message)
            if event.type == event.Type.Value('UserConnected'):
                for cb in callbacks: cb.userConnected(user)
            elif event.type == event.Type.Value('UserDisconnected'):
                for cb in callbacks: cb.userDisconnected(user)
            elif event.type == event.Type.Value('UserStateChanged'):
                for cb in callbacks: cb.userStateChanged(user)
            elif event.type == event.Type.Value('UserTextMessage'):
                for cb in callbacks: cb.userTextMessage(user, message)
            elif event.type == event.Type.Value('ChannelCreated'):
                for cb in callbacks: cb.channelCreated(channel)
            elif event.type == event.Type.Value('ChannelRemoved'):
                for cb in callbacks: cb.channelRemoved(channel)
            elif event.type == event.Type.Value('ChannelStateChanged'):
                for cb in callbacks: cb.channelStateChanged(channel)

        @local_thread
        def onContextEvent(self, listener, event):
            if listener.shutdown: return

            sid = listener.sid
            action = listener.action
            session = event.actor.session

            if sid not in self.contextCallbacks: return
            if session not in self.contextCallbacks[sid]: return
            if action not in self.contextCallbacks[sid][session]: return
            cb = self.contextCallbacks[sid][session][action]

            if event.actor is None: return
            user = Murmur.Server(self, stub, sid).getState(session)

            try:
                cb.contextAction(action, user,
                                 event.user.session if event.user else 0,
                                 event.channel.id if event.channel else -1)
            except:
                exception('Exception in context action callback:')
                self.removeContextCallback(sid, cb)

        @local_thread_blocking
        def addContextCallback(self, contextAction, cb):
            stub.ContextActionAdd(contextAction)

            session = contextAction.user.session
            sid = contextAction.server.id
            action = contextAction.action

            if action not in self.contextListeners[sid]:
                listener = contextListener(self, sid, action)
                listener.start()
                self.contextListeners[sid][action] = listener
            else:
                listener = self.contextListeners[sid][action]

            self.contextCallbacks[sid][session][action] = cb

        @local_thread_blocking
        def removeContextCallback(self, sid, cb):
            actions = []
            for session, actionMap in self.contextCallbacks[sid].iteritems():
                for action, lcb in actionMap.iteritems():
                    if lcb == cb:
                        actions.append(action)

            for action in actions:
                if action not in self.contextListeners[sid]:
                    continue

                self.contextListeners[sid][action].stop()
                del self.contextListeners[sid][action]

                try:
                    stub.ContextActionRemove(MurmurRPC_pb2.ContextAction(
                        server=MurmurRPC_pb2.Server(id=sid),
                        action=action))
                except grpc.RpcError:
                    pass

                for session, actionMap in self.contextCallbacks[sid].iteritems():
                    if action in actionMap:
                        del actionMap[action]

        @local_thread_blocking
        def onServerStop(self, sid):
            for listener in self.contextListeners[sid].values():
                listener.stop()
            del self.contextListeners[sid]
            del self.contextCallbacks[sid]

            self.app.serverListeners[sid].stop()
            del self.app.serverListeners[sid]

        @local_thread_blocking
        def onUserDisconnect(self, sid, session):
            actions = set(self.contextCallbacks[sid][session])
            del self.contextCallbacks[sid][session]

            stillInUse = set().intersection(
                    *map(set, self.contextCallbacks[sid].values()))

            for action in actions - stillInUse:
                if action in self.contextListeners[sid]:
                    self.contextListeners[sid][action].stop()
                    del self.contextListeners[sid][action]

    def fortifyGrpcFu(retval=None, exceptions=(grpc.RpcError,)):
        """
        Decorator that catches exceptions,logs them and returns a safe retval
        value. This helps to prevent getting stuck in
        critical code paths. Only exceptions that are instances of classes
        given in the exceptions list are not caught.

        The default is to catch all non-gRPC exceptions.
        """
        def newdec(func):
            def newfunc(*args, **kws):
                try:
                    return func(*args, **kws)
                except Exception, e:
                    catch = True
                    for ex in exceptions:
                        if isinstance(e, ex):
                            catch = False
                            break

                    if catch:
                        critical('Unexpected exception caught')
                        exception(e)
                        return retval
                    raise

            return newfunc
        return newdec

    class metaCallback(Murmur.MetaCallback):
        def __init__(self, app):
            Murmur.MetaCallback.__init__(self)
            self.app = app

        @fortifyGrpcFu()
        def started(self, server, current=None):
            """
            This function is called when a virtual server is started
            and makes sure the callbacks get attached if needed.
            """
            self.app.ensureListeningOnServer(server)

            sid = server.id()
            self.app.manager.announceMeta(sid, "started", server, current)

        @fortifyGrpcFu()
        def stopped(self, server, current=None):
            """
            This function is called when a virtual server is stopped
            """
            if self.app.connected:
                # Only try to output the server id if we think we are still
                # connected to prevent flooding of our thread pool
                sid = server.id()
                if sid in self.app.serverListeners:
                    info('Watched virtual server %d got stopped', sid)
                    self.app.onServerStop(sid)
                else:
                    debug('Virtual server %d got stopped', sid)
                self.app.manager.announceMeta(sid, "stopped", server, current)
                return

            debug('Server shutdown stopped a virtual server')

    def forwardServer(fu):
        def new_fu(self, *args, **kwargs):
            self.manager.announceServer(self.sid, fu.__name__, self.server,
                                        *args, **kwargs)
            fu(self, *args, **kwargs)
        return new_fu

    class serverCallback(Murmur.ServerCallback):
        def __init__(self, app, manager, server, sid):
            Murmur.ServerCallback.__init__(self)
            self.app = app
            self.manager = manager
            self.sid = sid
            self.server = server

        @forwardServer
        def userDisconnected(self, u, current=None):
            self.app.onUserDisconnect(self.sid, u.session)

        @forwardServer
        def userStateChanged(self, u, current=None): pass

        @forwardServer
        def userConnected(self, u, current=None): pass

        @forwardServer
        def channelCreated(self, c, current=None): pass

        @forwardServer
        def channelRemoved(self, c, current=None): pass

        @forwardServer
        def channelStateChanged(self, c, current=None): pass

        @forwardServer
        def userTextMessage(self, u, m, current=None): pass

    class customContextCallback(Murmur.ServerContextCallback):
        def __init__(self, contextActionCallback, *ctx):
            Murmur.ServerContextCallback.__init__(self)
            self.cb = contextActionCallback
            self.ctx = ctx

        def contextAction(self, *args, **argv):
            # (action, user, target_session, target_chanid, current=None)
            self.cb(*(self.ctx + args), **argv)

    #
    # --- Start of moderator
    #
    info('Starting mumble moderator')
    debug('Initializing manager')
    manager = MumoManager(Murmur, customContextCallback)
    manager.start()
    manager.loadModules()
    manager.startModules()

    debug("Initializing mumoGrpcApp")
    app = mumoGrpcApp(manager)
    app.start()

    while True:
        try:
            time.sleep(1)
        except KeyboardInterrupt:
            warning('Caught interrupt, shutting down')
            break

    manager.stopModules()
    manager.stop()
    app.stop()
    info('Shutdown complete')
    return True

#
#--- Start of program
#
if __name__ == '__main__':
    # Parse commandline options
    parser = OptionParser()
    parser.add_option('-i', '--ini',
                      help='load configuration from INI', default=cfgfile)
    parser.add_option('-v', '--verbose', action='store_true', dest='verbose',
                      help='verbose output [default]', default=True)
    parser.add_option('-q', '--quiet', action='store_false', dest='verbose',
                      help='only error output')
    parser.add_option('-d', '--daemon', action='store_true', dest='force_daemon',
                      help='run as daemon', default=False)
    parser.add_option('-a', '--app', action='store_true', dest='force_app',
                      help='do not run as daemon', default=False)
    (option, args) = parser.parse_args()

    if option.force_daemon and option.force_app:
        parser.print_help()
        sys.exit(1)

    # Load configuration
    try:
        cfg = Config(option.ini, default)
    except Exception, e:
        print >> sys.stderr, 'Fatal error, could not load config file from "%s"' % cfgfile
        print >> sys.stderr, e
        sys.exit(1)

    # Initialise logger
    if cfg.log.file:
        try:
            logfile = open(cfg.log.file, 'a')
        except IOError, e:
            #print>>sys.stderr, str(e)
            print >> sys.stderr, 'Fatal error, could not open logfile "%s"' % cfg.log.file
            sys.exit(1)
    else:
        logfile = logging.sys.stderr


    if option.verbose:
        level = cfg.log.level
    else:
        level = logging.ERROR

    logging.basicConfig(level=level,
                        format='%(asctime)s %(levelname)s %(name)s %(message)s',
                        stream=logfile)

    # As the default try to run as daemon. Silently degrade to running as a normal application if this fails
    # unless the user explicitly defined what he expected with the -a / -d parameter.
    try:
        if option.force_app:
            raise ImportError # Pretend that we couldn't import the daemon lib
        import daemon
        try:
            from daemon.pidfile import TimeoutPIDLockFile
        except ImportError: # Version < 1.6
            from daemon.pidlockfile import TimeoutPIDLockFile
    except ImportError:
        if option.force_daemon:
            print >> sys.stderr, 'Fatal error, could not daemonize process due to missing "daemon" library, ' \
            'please install the missing dependency and restart the application'
            sys.exit(1)
        if cfg.grpc.active:
            ret = do_grpc_main_program()
        else:
            ret = do_ice_main_program()
    else:
        pidfile = TimeoutPIDLockFile(cfg.system.pidfile, 5)
        if pidfile.is_locked():
            try:
                os.kill(pidfile.read_pid(), 0)
                print >> sys.stderr, 'Mumo already running as %s' % pidfile.read_pid()
                sys.exit(1)
            except OSError:
                print >> sys.stderr, 'Found stale mumo pid file but no process, breaking lock'
                pidfile.break_lock()

        context = daemon.DaemonContext(working_directory=sys.path[0],
                                       stderr=logfile,
                                       pidfile=pidfile)
        context.__enter__()
        try:
            if cfg.grpc.active:
                ret = do_grpc_main_program()
            else:
                ret = do_ice_main_program()
        finally:
            context.__exit__(None, None, None)
    sys.exit(ret)
