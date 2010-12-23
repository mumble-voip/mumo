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

#
# mbf2man.py
# This small programm is for creating a possible channel/acl structure for
# the mumo bf2 module as well as the corresponding bf2.ini configuration file.

import os
import sys
import tempfile
from optparse import OptionParser

# Default settings


import Ice
import IcePy


if __name__ == "__main__":
    parser = OptionParser()
    parser.add_option('-t', '--target',
                      help = 'Host to connect to', default = "127.0.0.1")
    parser.add_option('-p', '--port',
                      help = 'Port to connect to', default = "6502")
    parser.add_option('-b', '--base',
                      help = 'Channel id of the base channel', default = '0')
    parser.add_option('-v', '--vserver',
                      help = 'Virtual server id', default = '1')
    parser.add_option('-i', '--ice',
                      help = 'Path to slice file', default = 'Murmur.ice')
    parser.add_option('-s', '--secret',
                      help = 'Ice secret', default = '')
    parser.add_option('-n', '--name',
                      help = 'Treename')
    parser.add_option('-o', '--out', default = 'bf2.ini',
                      help = 'File to output configuration to')
    (option, args) = parser.parse_args()
    
    host = option.target
    try:
        port = int(option.port)
    except ValueError:
        print "Port value '%s' is invalid" % option.port
        sys.exit(1)
        
    try:
        basechan = int(option.base)
        if basechan < 0: raise ValueError
    except ValueError:
        print "Base channel value '%s' invalid" % option.base
        sys.exit(1)
        
    try:
        sid = int(option.vserver)
        if sid < 1: raise ValueError
    except ValueError:
        print "Virtual server id value '%s' invalid" % option.vserver
        sys.exit(1)
        
    name = option.name
        
    prxstr = "Meta:tcp -h %s -p %d -t 1000" % (host, port)
    secret = option.secret
                
    props = Ice.createProperties(sys.argv)
    props.setProperty("Ice.ImplicitContext", "Shared")
    idata = Ice.InitializationData()
    idata.properties = props
    
    ice = Ice.initialize(idata)
    prx = ice.stringToProxy(prxstr)
    print "Done"
    
    try:
        print "Trying to retrieve slice dynamically from server...",
        slice = IcePy.Operation('getSlice', Ice.OperationMode.Idempotent, Ice.OperationMode.Idempotent, True, (), (), (), IcePy._t_string, ()).invoke(prx, ((), None))
    
        (dynslicefiledesc, dynslicefilepath)  = tempfile.mkstemp(suffix = '.ice')
        dynslicefile = os.fdopen(dynslicefiledesc, 'w')
        dynslicefile.write(slice)
        dynslicefile.flush()
        Ice.loadSlice('', ['-I' + Ice.getSliceDir(), dynslicefilepath])
        dynslicefile.close()
        os.remove(dynslicefilepath)
        print "Success"
    except Exception, e:
        print "Failed"
        print str(e)
        slicefile = option.ice
        print "Load slice (%s)..." % slicefile,
        Ice.loadSlice('', ['-I' + Ice.getSliceDir(), slicefile])
        print "Done"
    
    print "Import dynamically compiled murmur class...",
    import Murmur
    print "Done"
    print "Establish ice connection...",
    
    if secret:
        print "[protected]...",
        ice.getImplicitContext().put("secret", secret)
    
    murmur = Murmur.MetaPrx.checkedCast(prx)
    print "Done"
    
    print "Get server...",
    server = murmur.getServer(sid)
    print "Done (%d)" % sid
    
    ini = {}
    ini['mumble_server'] = sid
    ini['name'] = name
    ini['ipport_filter'] = '.*'
    
    print "Creating channel structure:"
    ACL = Murmur.ACL
    EAT = Murmur.PermissionEnter | Murmur.PermissionTraverse
    print name
    ini['left'] = basechan
    gamechan = server.addChannel(name, basechan)
    
    
    # mice.Murmur.ACL(self, applyHere=False, applySubs=False,
    #                       inherited=False, userid=0, group='', allow=0, deny=0)
    
    # mice.s.setACL(self, channelid, acls, groups, inherit, _ctx=None)
    server.setACL(gamechan,
                  [ACL(applyHere = True,
                       applySubs = True,
                        userid = -1,
                       group = 'all',
                       deny = EAT),
                    ACL(applyHere = True,
                        applySubs = False,
                        userid = -1,
                        group = 'bf2_linked',
                        allow = EAT)],
                   [], True)
    

    teams = ["blufor", "opfor"]
    id_to_squad_name = ["no", "alpha", "bravo", "charlie", "delta", "echo", "foxtrot", "golf", "hotel", "india"]
    for team in teams:
        print name + "/" + team
        ini[team] = server.addChannel(team, gamechan)
        server.setACL(ini[team],
                      [ACL(applyHere = True,
                           applySubs = False,
                           userid = -1,
                           group = 'bf2%s_%s' % (name, team),
                           allow = EAT)],
                      [], True)
        
        print name + "/" + team + "_commander"
        ini[team + "_commander"] = server.addChannel("commander", ini[team])
        server.setACL(ini[team + "_commander"],
                      [ACL(applyHere = True,
                           applySubs = False,
                           userid = -1,
                           group = 'bf2%s_%s_commander' % (name, team),
                           allow = EAT)],
                      [], True)
        
        state = server.getChannelState(ini[team+"_commander"])
        state.position = -1
        server.setChannelState(state)
        
        ini[team + "_no_squad"] = ini[team]
        for squad in id_to_squad_name[1:]:
            print name + "/" + team + "/" + squad
            ini[team + "_" + squad + "_squad"] = server.addChannel(squad, ini[team])
            ini[team + "_" + squad + "_squad_leader"] = ini[team + "_" + squad + "_squad"]
            server.setACL(ini[team + "_" + squad + "_squad"],
                          [ACL(applyHere = True,
                               applySubs = False,
                               userid = -1,
                               group = 'bf2%s_%s_%s_squad' % (name, team, squad),
                               allow = EAT)],
                          [], True)
    
    print "Channel structure created"
    
    print "Writing configuration to output file '%s'..." % option.out,
    f = open(option.out, "w")
    print>>f, "; Configuration created by mbf2man\n"
    print>>f, "[bf2]\ngamecount = 1\n"
    print>>f, "[g0]"
    
    for key in sorted(ini):
        value = ini[key]
        print>>f, "%s = %s" % (key, value)
    
    f.close()
    print "Done"

