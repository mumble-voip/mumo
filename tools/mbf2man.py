#!/usr/bin/env python3
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

import Ice
import IcePy

# Default settings

if __name__ == "__main__":
    parser = OptionParser()
    parser.add_option('-t', '--target',
                      help='Host to connect to', default="127.0.0.1")
    parser.add_option('-p', '--port',
                      help='Port to connect to', default="6502")
    parser.add_option('-b', '--base',
                      help='Channel id of the base channel', default='0')
    parser.add_option('-v', '--vserver',
                      help='Virtual server id', default='1')
    parser.add_option('-i', '--ice',
                      help='Path to slice file', default='Murmur.ice')
    parser.add_option('-s', '--secret',
                      help='Ice secret', default='')
    parser.add_option('-l', '--linkteams', action='store_true',
                      help='Link teams so opposing players can hear each other', default=False)
    parser.add_option('-n', '--name',
                      help='Treename', default='BF2')
    parser.add_option('-o', '--out', default='bf2.ini',
                      help='File to output configuration to')
    parser.add_option('-d', '--slicedir',
                      help='System slice directory used when getSliceDir is not available', default='/usr/share/slice')
    (option, args) = parser.parse_args()

    host = option.target
    slicedir = option.slicedir
    try:
        port = int(option.port)
    except ValueError:
        print("Port value '%s' is invalid" % option.port)
        sys.exit(1)

    try:
        basechan = int(option.base)
        if basechan < 0: raise ValueError
    except ValueError:
        print("Base channel value '%s' invalid" % option.base)
        sys.exit(1)

    try:
        sid = int(option.vserver)
        if sid < 1: raise ValueError
    except ValueError:
        print("Virtual server id value '%s' invalid" % option.vserver)
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
    print("Done")


    def lslice(slf):
        if not hasattr(Ice, "getSliceDir"):
            Ice.loadSlice('-I%s %s' % (slicedir, slf))
        else:
            Ice.loadSlice('', ['-I' + Ice.getSliceDir(), slf])


    try:
        print("Trying to retrieve slice dynamically from server...", end=' ')
        op = IcePy.Operation('getSlice', Ice.OperationMode.Idempotent, Ice.OperationMode.Idempotent, True, (), (), (),
                             IcePy._t_string, ())
        if hasattr(Ice, "getSliceDir"):
            slice = op.invoke(prx, ((), None))
        else:
            slice = op.invoke(prx, (), None)
        (dynslicefiledesc, dynslicefilepath) = tempfile.mkstemp(suffix='.ice')
        dynslicefile = os.fdopen(dynslicefiledesc, 'w')
        dynslicefile.write(slice)
        dynslicefile.flush()
        lslice(dynslicefilepath)
        dynslicefile.close()
        os.remove(dynslicefilepath)
        print("Success")
    except Exception as e:
        print("Failed")
        print(str(e))
        slicefile = option.ice
        print("Load slice (%s)..." % slicefile, end=' ')
        lslice(slicefile)
        print("Done")

    print("Import dynamically compiled murmur class...", end=' ')
    import Murmur # pylint: disable=E0401 # pyright: ignore

    print("Done")
    print("Establish ice connection...", end=' ')

    if secret:
        print("[protected]...", end=' ')
        ice.getImplicitContext().put("secret", secret)

    murmur = Murmur.MetaPrx.checkedCast(prx)
    print("Done")

    print("Get server...", end=' ')
    server = murmur.getServer(sid)
    print("Done (%d)" % sid)

    ini = {'mumble_server': sid, 'name': name, 'ipport_filter': '.*'}

    print("Creating channel structure:")
    ACL = Murmur.ACL
    EAT = Murmur.PermissionEnter | Murmur.PermissionTraverse
    W = Murmur.PermissionWhisper
    S = Murmur.PermissionSpeak
    print(name)
    ini['left'] = basechan
    gamechan = server.addChannel(name, basechan)

    # Relevant function signatures
    # Murmur.ACL(self, applyHere=False, applySubs=False,
    #                   inherited=False, userid=0, group='', allow=0, deny=0)

    # server.setACL(self, channelid, acls, groups, inherit, _ctx=None)
    #
    server.setACL(gamechan,
                  [ACL(applyHere=True,
                       applySubs=True,
                       userid=-1,
                       group='all',
                       deny=EAT | W | S),
                   ACL(applyHere=True,
                       applySubs=True,
                       userid=-1,
                       group='~bf2_%s_game' % name,
                       allow=S),
                   ACL(applyHere=True,
                       applySubs=False,
                       userid=-1,
                       group='~bf2_%s_game' % name,
                       allow=EAT | W)],
                  [], True)

    gamechanstate = server.getChannelState(gamechan)

    teams = {
        "opfor": "Team 1",
        "blufor": "Team 2"
    }
    id_to_squad_name = {
        "no": "No Squad",
        "first": "Squad 1",
        "second": "Squad 2",
        "third": "Squad 3",
        "fourth": "Squad 4",
        "fifth": "Squad 5",
        "sixth": "Squad 6",
        "seventh": "Squad 7",
        "eighth": "Squad 8",
        "ninth": "Squad 9"
    }
    for team, team_name in list(teams.items()):
        print(name + "/" + team_name)
        cid = server.addChannel(team_name, gamechan)
        teamchanstate = server.getChannelState(cid)
        if option.linkteams:
            gamechanstate.links.append(cid)

        ini[team] = cid

        server.setACL(ini[team],
                      [ACL(applyHere=True,
                           applySubs=False,
                           userid=-1,
                           group='~bf2_team',
                           allow=EAT | W)],
                      [], True)

        print(name + "/" + team_name + "/Commander")
        cid = server.addChannel("Commander", ini[team])
        teamchanstate.links.append(cid)
        ini[team + "_commander"] = cid

        server.setACL(ini[team + "_commander"],
                      [ACL(applyHere=True,
                           applySubs=False,
                           userid=-1,
                           group='~bf2_commander',
                           allow=EAT | W),
                       ACL(applyHere=True,
                           applySubs=False,
                           userid=-1,
                           group='~bf2_squad_leader',
                           allow=W)],
                      [], True)

        state = server.getChannelState(ini[team + "_commander"])
        state.position = -1
        server.setChannelState(state)

        for squad, squad_name in list(id_to_squad_name.items()):
            print(name + "/" + team_name + "/" + squad_name)
            cid = server.addChannel(squad_name, ini[team])
            teamchanstate.links.append(cid)
            ini[team + "_" + squad + "_squad"] = cid

            ini[team + "_" + squad + "_squad_leader"] = ini[team + "_" + squad + "_squad"]
            server.setACL(ini[team + "_" + squad + "_squad"],
                          [ACL(applyHere=True,
                               applySubs=False,
                               userid=-1,
                               group='~bf2_%s_squad' % squad,
                               allow=EAT | W),
                           ACL(applyHere=True,
                               applySubs=False,
                               userid=-1,
                               group='~bf2_commander',
                               allow=EAT | W),
                           ACL(applyHere=True,
                               applySubs=False,
                               userid=-1,
                               group='~bf2_squad_leader',
                               allow=W)],
                          [], True)
        server.setChannelState(teamchanstate)
    server.setChannelState(gamechanstate)
    print("Channel structure created")

    print("Writing configuration to output file '%s'..." % option.out, end=' ')
    f = open(option.out, "w")
    print("; Configuration created by mbf2man\n", file=f)
    print("[bf2]\ngamecount = 1\n", file=f)
    print("[g0]", file=f)

    for key in sorted(ini):
        value = ini[key]
        print("%s = %s" % (key, value), file=f)

    f.close()
    print("Done")
