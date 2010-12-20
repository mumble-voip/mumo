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

import sys
import Ice
import logging
from config import Config, x2bool

from threading  import Timer
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
                      ('slice', str, 'Murmur.ice'),
                      ('secret', str, ''),
                      ('watchdog', int, 30)),
                      
               'iceraw':None,
               'murmur':(('servers', lambda x:map(int, x.split(',')), []),),
               'log':(('level', int, logging.DEBUG),
                      ('file', str, 'mumo.log'))})

def do_main_program():
    #
    #--- Moderator implementation
    #    All of this has to go in here so we can correctly daemonize the tool
    #    without loosing the file descriptors opened by the Ice module
    Ice.loadSlice('', ['-I' + Ice.getSliceDir(), cfg.ice.slice])
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
            Establishes the two-way Ice connection and adds the authenticator to the
            configured servers
            """
            ice = self.communicator()
            
            if cfg.ice.secret:
                debug('Using shared ice secret')
                ice.getImplicitContext().put("secret", cfg.ice.secret)
            else:
                warning('Consider using an ice secret to improve security')
    
            info('Connecting to Ice server (%s:%d)', cfg.ice.host, cfg.ice.port)
            base = ice.stringToProxy('Meta:tcp -h %s -p %d' % (cfg.ice.host, cfg.ice.port))
            self.meta = Murmur.MetaPrx.uncheckedCast(base)
        
            adapter = ice.createObjectAdapterWithEndpoints('Callback.Client', 'tcp -h %s' % cfg.ice.host)
            adapter.activate()
            self.adapter = adapter
            
            metacbprx = adapter.addWithUUID(metaCallback(self))
            self.metacb = Murmur.MetaCallbackPrx.uncheckedCast(metacbprx)
            
            return self.attachCallbacks()
        
        def attachCallbacks(self):
            """
            Attaches all callbacks for meta and authenticators
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
                        servercbprx = self.adapter.addWithUUID(serverCallback(self.manager, sid))
                        servercb = Murmur.ServerCallbackPrx.uncheckedCast(servercbprx)
                        server.addCallback(servercb)
                        
#                        contextcbprx = self.adapter.addWithUUID(contextCallback(self.manager, sid))
#                        contextcb = Murmur.ServerCallbackPrx.uncheckedCast(contextcbprx)
#                        server.addContextCallback(contextcb)
                        
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
            self.manager.announceConnected()
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
        value. This helps preventing the authenticator getting stuck in
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
            and makes sure an authenticator gets attached if needed.
            """
            sid = server.id()
            if not cfg.murmur.servers or sid in cfg.murmur.servers:
                info('Setting authenticator for virtual server %d', server.id())
                try:
                    servercbprx = self.app.adapter.addWithUUID(serverCallback(self.app.manager, sid))
                    servercb = Murmur.ServerCallbackPrx.uncheckedCast(servercbprx)
                    server.addCallback(servercb)
                    
#                    contextcbprx = self.adapter.addWithUUID(contextCallback(self.app.manager, sid))
#                    contextcb = Murmur.ServerCallbackPrx.uncheckedCast(contextcbprx)
#                    server.addContextCallback(contextcb)
                # Apparently this server was restarted without us noticing
                except (Murmur.InvalidSecretException, Ice.UnknownUserException), e:
                    if hasattr(e, "unknown") and e.unknown != "Murmur::InvalidSecretException":
                        # Special handling for Murmur 1.2.2 servers with invalid slice files
                        raise e
                    
                    error('Invalid ice secret')
                    return
            else:
                debug('Virtual server %d got started', sid)
            
            self.app.manager.announceMeta([sid], "started", server, current)
    
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
                    self.app.manager.announceMeta([sid], "stopped", server, current)
                    return
                except Ice.ConnectionRefusedException:
                    self.app.connected = False
                    self.app.manager.announceDisconnected()
            
            debug('Server shutdown stopped a virtual server')
            
    
    def forwardServer(fu):
        def new_fu(*args, **kwargs):
            self = args[0]
            self.manager.announceServer([self.sid], fu.__name__, *args, **kwargs)
        return new_fu

    class serverCallback(Murmur.ServerCallback):
        def __init__(self, manager, sid):
            Murmur.ServerCallback.__init__(self)
            self.manager = manager
            self.sid = sid
        
        @forwardServer
        def userStateChanged(self, u, current=None): pass
        @forwardServer
        def userDisconnected(self, u, current=None): pass
        @forwardServer
        def userConnected(self, u, current=None): pass
        @forwardServer
        def channelCreated(self, c, current=None): pass 
        @forwardServer
        def channelRemoved(self, c, current=None): pass
        @forwardServer
        def channelStateChanged(self, c, current=None): pass
    
    class contextCallback(Murmur.ServerContextCallback):
        def __init__(self, manager, sid):
            Murmur.ServerContextCallback.__init__(self)
            self.manager = manager
            self.sid = sid
        
        def contextAction(self, action, p, session, chanid, current=None):
            self.manager.announceContext([self.sid], "contextAction", action, p, session, chanid, current)

    #
    #--- Start of moderator
    #
    info('Starting mumble moderator')
    debug('Initializing manager')
    manager = MumoManager()
    manager.start()
    manager.loadModules()
    manager.startModules()
    
    debug('Initializing Ice')
    initdata = Ice.InitializationData()
    initdata.properties = Ice.createProperties([], initdata.properties)
    for prop, val in cfg.iceraw:
        initdata.properties.setProperty(prop, val)
        
    initdata.properties.setProperty('Ice.ImplicitContext', 'Shared')
    initdata.logger = CustomLogger()
    
    app = mumoIceApp(manager)
    state = app.main(sys.argv[:1], initData=initdata)
    
    manager.stopModules()
    manager.stop()
    info('Shutdown complete')
    
class CustomLogger(Ice.Logger):
    """
    Logger implementation to pipe Ice log messages into
    out own log
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
    except ImportError:
        if option.force_daemon:
            print >> sys.stderr, 'Fatal error, could not daemonize process due to missing "daemon" library, ' \
            'please install the missing dependency and restart the authenticator'
            sys.exit(1)
        do_main_program()
    else:
        context = daemon.DaemonContext(working_directory=sys.path[0],
                                       stderr=logfile)
        context.__enter__()
        try:
            do_main_program()
        finally:
            context.__exit__(None, None, None)
