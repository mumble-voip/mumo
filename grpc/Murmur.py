# -*- coding: utf-8

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

from recordclass import recordclass
import grpc
import MurmurRPC_pb2 as MurmurRPC

Void = MurmurRPC.Void()


User = recordclass('User', [
    'session',
    'userid',
    'mute',
    'deaf',
    'suppress',
    'prioritySpeaker',
    'selfMute',
    'selfDeaf',
    'recording',
    'channel',
    'name',
    'onlinesecs',
    'bytespresec',
    'version',
    'release',
    'os',
    'osversion',
    'identity',
    'context',
    'comment',
    'address',
    'tcponly',
    'idlesecs',
    'udpPing',
    'tcpPing'])


Channel = recordclass('Channel', [
    'id',
    'name',
    'parent',
    'links',
    'description',
    'temporary',
    'position'])


TextMessage = recordclass('TextMessage', [
    'sessions',
    'channels',
    'trees',
    'text'])


ACL = recordclass('ACL', [
    'applyHere',
    'applySubs',
    'inherited',
    'userid',
    'group',
    'allow',
    'deny'])


Ban = recordclass('Ban', [
    'address',
    'bits',
    'name',
    'hash',
    'reason',
    'start',
    'duration'])


Group = recordclass('Group', [
    'name',
    'inherited',
    'inherit',
    'inheritable',
    'add',
    'remove',
    'members'])


LogEntry = recordclass('LogEntry', [
    'timestamp',
    'txt'])


Tree = recordclass('Tree', [
    'c',
    'children',
    'users'])


class UserInfo:
    UserName, UserEmail, UserComment, UserHash, UserPassword, UserLastActive\
        = range(6)


ContextServer = 0x01
ContextChannel = 0x02
ContextUser = 0x04


PermissionWrite = 0x1
PermissionTraverse = 0x2
PermissionEnter = 0x4
PermissionSpeak = 0x8
PermissionMuteDeafen = 0x10
PermissionMove = 0x20
PermissionMakeChannel = 0x40
PermissionLinkChannel = 0x80
PermissionWhisper = 0x100
PermissionTextMessage = 0x200
PermissionMakeTempChannel = 0x400
PermissionKick = 0x10000
PermissionBan = 0x20000
PermissionRegister = 0x40000
PermissionRegisterSelf = 0x80000


def toIce(obj):
    if obj is None:
        return None
    if isinstance(obj, MurmurRPC.User):
        return User(
                session=obj.session,
                userid=obj.id,
                mute=obj.mute,
                deaf=obj.deaf,
                suppress=obj.suppress,
                prioritySpeaker=obj.priority_speaker,
                selfMute=obj.self_mute,
                selfDeaf=obj.self_deaf,
                recording=obj.recording,
                channel=obj.channel.id,
                name=obj.name,
                onlinesecs=obj.online_secs,
                bytespresec=obj.bytes_per_sec,
                version=obj.version.version,
                release=obj.version.release,
                os=obj.version.os,
                osversion=obj.version.os_version,
                identity=obj.plugin_identity,
                context=obj.plugin_context,
                comment=obj.comment,
                address=obj.address,
                tcponly=obj.tcp_only,
                idlesecs=obj.idle_secs,
                udpPing=obj.udp_ping_msecs,
                tcpPing=obj.tcp_ping_msecs)
    if isinstance(obj, MurmurRPC.Channel):
        return Channel(
                id=obj.id,
                name=obj.name,
                parent=obj.parent.id,
                links=[c.id for c in obj.links],
                description=obj.description,
                temporary=obj.temporary,
                position=obj.position)
    if isinstance(obj, MurmurRPC.TextMessage):
        return TextMessage(
                sessions=[u.session for u in obj.users],
                channels=[c.id for c in obj.channels],
                trees=[c.id for c in obj.trees],
                text=obj.text)
    if isinstance(obj, MurmurRPC.DatabaseUser):
        return {
                UserInfo.UserName: obj.name,
                UserInfo.UserEmail: obj.email,
                UserInfo.UserComment: obj.comment,
                UserInfo.UserHash: obj.hash,
                # password is never sent (only used when updating)
                UserInfo.UserLastActive: obj.last_active,
                }
    if isinstance(obj, MurmurRPC.ACL.List):
        acls = [toIce(acl) for acl in obj.acls]
        groups = [toIce(group) for group in obj.groups]
        return (acls, groups, obj.inherit)
    if isinstance(obj, MurmurRPC.ACL.Group):
        return Group(
                name=obj.name,
                inherited=obj.inherited,
                inherit=obj.inherit,
                inheritable=obj.inheritable,
                add=[u.id for u in obj.users_add],
                remove=[u.id for u in obj.users_remove],
                members=[u.id for u in obj.users])
    if isinstance(obj, MurmurRPC.ACL):
        return ACL(
                applyHere=obj.apply_here,
                applySubs=obj.apply_subs,
                inherited=obj.inherited,
                userid=obj.user.id if obj.HasField('user') else -1,
                group=obj.group.name if obj.HasField('group') else '',
                allow=obj.allow,
                deny=obj.deny)
    if isinstance(obj, MurmurRPC.Tree):
        return Tree(
                c=toIce(obj.channel),
                children=[toIce(child) for child in obj.children],
                users=[toIce(user) for user in obj.users])
    if isinstance(obj, MurmurRPC.Ban):
        return Ban(
                address=tuple(ord(c) for c in obj.address),
                bits=obj.bits,
                name=obj.name,
                hash=obj.hash,
                reason=obj.reason,
                start=obj.start,
                duration=obj.duration_secs)
    if isinstance(obj, MurmurRPC.Log):
        return LogEntry(
                timestamp=obj.timestamp,
                txt=obj.text)
    raise TypeError(str(type(obj)))


class UnsupportedByGRPC(Exception):
    pass


class MurmurException(Exception):
    pass


class ServerBootedException(MurmurException):
    pass


class InvalidCallbackException(MurmurException):
    pass


class Meta:
    def __init__(self, app, stub):
        self._app = app
        self._stub = stub

    def getServer(self, serverId):
        server = Server(self._app, self._stub, serverId)
        try:
            server._get()
        except grpc.RpcError, e:
            if e.code() == grpc.StatusCode.NOT_FOUND:
                return None
            raise
        return server

    def newServer(self):
        result = self._stub.ServerCreate(Void)
        return Server(self._app, self._stub, result.id)

    def _getServers(self, onlyRunning):
        return [Server(self._app, self._stub, s.id)
                for s
                in self._stub.ServerQuery(MurmurRPC.Server.Query()).servers
                if s.running or not onlyRunning]

    def getBootedServers(self):
        return self._getServers(True)

    def getAllServers(self):
        return self._getServers(False)

    def getDefaultConfig(self):
        return dict(self._stub.ConfigGetDefault(Void).fields)

    def getVersion(self):
        version = self._stub.GetVersion(Void)
        major = (version.version >> 16) & 0xffff
        minor = (version.version >> 8) & 0xff
        patch = (version.version >> 0) & 0xff
        text = version.release
        return (major, minor, patch, text)

    def addCallback(self, cb):
        self._app.metaCallbacks.append(cb)

    def removeCallback(self, cb):
        self._app.metaCallbacks.remove(cb)

    def getUptime(self):
        return self._stub.GetUptime(Void).secs

    def getSlice(self):
        raise UnsupportedByGRPC()

    def getSliceChecksums(self):
        raise UnsupportedByGRPC()


class MetaCallback:
    def __init__(self): pass

    def started(self, server): pass

    def stopped(self, server): pass


def throws_server_booted_exception(func):
    def new_func(self, *args, **kwargs):
        try:
            return func(self, *args, **kwargs)
        except grpc.RpcError, e:
            if e.code() == grpc.StatusCode.NOT_FOUND and \
                    e.details() == 'invalid server':
                raise ServerBootedException()
            raise
    return new_func


class Server:
    def __init__(self, app, stub, sid):
        self._app = app
        self._stub = stub
        self._sid = sid

    def _ice(self):
        return MurmurRPC.Server(id=self._sid)

    def _get(self):
        return self._stub.ServerGet(self._ice())

    def isRunning(self):
        return self._get().running

    @throws_server_booted_exception
    def start(self):
        self._stub.ServerStart(self._ice())

    @throws_server_booted_exception
    def stop(self):
        self._stub.ServerStop(self._ice())

    @throws_server_booted_exception
    def delete(self):
        self._stub.ServerRemove(self._ice())

    def id(self):
        return self._sid

    @throws_server_booted_exception
    def addCallback(self, cb):
        self._app.serverListeners[self._sid].callbacks.append(cb)

    @throws_server_booted_exception
    def removeCallback(self, cb):
        self._app.serverListeners[self._sid].callbacks.append(cb)

    @throws_server_booted_exception
    def setAuthenticator(self):
        raise NotImplementedError()  # TODO

    def getConf(self, key):
        return self._stub.ConfigGetField(MurmurRPC.Config.Field(
            server=self._ice(),
            key=key)).value

    def getAllConf(self):
        return dict(self._stub.ConfigGet(self._ice()).fields)

    def setConf(self, key, value):
        return self._stub.ConfigSetField(MurmurRPC.Config.Field(
            server=self._ice(),
            key=key,
            value=value))

    def setSuperuserPassword(self, pw):
        self.updateRegistration(0, {UserInfo.UserPassword: pw})

    def getLog(self, first, last):
        return [toIce(e) for e in self._stub.LogQuery(MurmurRPC.Log.Query(
            server=self._ice(),
            min=first,
            max=last)).entries]

    def getLogLen(self):
        return self._stub.LogQuery(MurmurRPC.Log.Query(
            server=self._ice())).total

    @throws_server_booted_exception
    def getUsers(self):
        query = MurmurRPC.User.Query(server=self._ice())
        users = self._stub.UserQuery(query).users
        return {user.session: toIce(user) for user in users}

    @throws_server_booted_exception
    def getChannels(self):
        query = MurmurRPC.Channel.Query(server=self._ice())
        channels = self._stub.ChannelQuery(query).channels
        return {c.id: toIce(c) for c in channels}

    @throws_server_booted_exception
    def getCertificateList(self, session):
        raise NotImplementedError()  # TODO

    @throws_server_booted_exception
    def getTree(self):
        query = MurmurRPC.Tree.Query(server=self._ice())
        return toIce(self._stub.TreeQuery(query))

    @throws_server_booted_exception
    def getBans(self):
        return [toIce(ban) for ban in self._stub.BansGet(MurmurRPC.Ban.Query(
            server=self._ice())).bans]

    @throws_server_booted_exception
    def setBans(self, banList):
        self._stub.BansSet(MurmurRPC.Ban.List(
            server=self._ice(),
            bans=[MurmurRPC.Ban(
                address=bytes(bytearray(ban.address)),
                bits=ban.bits,
                name=ban.name,
                hash=ban.hash,
                reason=ban.reason,
                start=ban.start,
                duration_secs=ban.duration) for ban in banList]))

    @throws_server_booted_exception
    def kickUser(self, session, reason):
        self._stub.UserKick(MurmurRPC.User.Kick(
            server=self._ice(),
            user=MurmurRPC.User(session=session),
            reason=reason))

    @throws_server_booted_exception
    def getState(self, session):
        return toIce(self._stub.UserGet(MurmurRPC.User(
            server=self._ice(),
            session=session)))

    @throws_server_booted_exception
    def setState(self, state):
        self._stub.UserUpdate(MurmurRPC.User(
            server=self._ice(),
            session=state.session,
            name=state.name,
            mute=state.mute,
            deaf=state.deaf,
            suppress=state.suppress,
            priority_speaker=state.prioritySpeaker,
            channel=MurmurRPC.Channel(id=state.channel),
            comment=state.comment))

    @throws_server_booted_exception
    def sendMessage(self, session, text):
        self._stub.TextMessageSend(MurmurRPC.TextMessage(
            server=self._ice(),
            users=[MurmurRPC.User(session=session)],
            text=text))

    @throws_server_booted_exception
    def hasPermission(self, session, channelId, perm):
        return (self.effectivePermissions(session, channelId) & perm) != 0

    @throws_server_booted_exception
    def effectivePermissions(self, session, channelId):
        return self._stub.ACLGetEffectivePermissions(MurmurRPC.ACL.Query(
            server=self._ice(),
            user=MurmurRPC.User(session=session),
            channel=MurmurRPC.Channel(id=channelId))).allow

    def addContextCallback(self, session, action, text, cb, ctx):
        contextAction = MurmurRPC.ContextAction(
                server=self._ice(),
                action=action,
                text=text,
                user=MurmurRPC.User(session=session),
                context=ctx)

        self._app.addContextCallback(contextAction, cb)

    @throws_server_booted_exception
    def removeContextCallback(self, cb):
        self._app.removeContextCallback(self._sid, cb)

    @throws_server_booted_exception
    def getChannelState(self, channelId):
        return toIce(self._stub.ChannelGet(MurmurRPC.Channel(
            server=self._ice(),
            id=channelId)))

    @throws_server_booted_exception
    def setChannelState(self, state):
        self._stub.ChannelUpdate(MurmurRPC.Channel(
            server=self._ice(),
            id=state.id,
            name=state.name,
            parent=MurmurRPC.Channel(id=state.parent),
            links=[MurmurRPC.Channel(id=cid) for cid in state.links],
            description=state.description,
            temporary=state.temporary,
            position=state.position))

    @throws_server_booted_exception
    def removeChannel(self, channelId):
        self._stub.ChannelRemove(MurmurRPC.Channel(
            server=self._ice(),
            id=channelId))

    @throws_server_booted_exception
    def addChannel(self, name, parent):
        return self._stub.ChannelAdd(MurmurRPC.Channel(
            server=self._ice(),
            name=name,
            parent=MurmurRPC.Channel(id=parent))).id

    @throws_server_booted_exception
    def sendMessageChannel(self, channelId, tree, text):
        if tree:
            message = MurmurRPC.TextMessage(
                    server=self._ice(),
                    channels=[MurmurRPC.Channel(id=channelId)],
                    text=text)
        else:
            message = MurmurRPC.TextMessage(
                    server=self._ice(),
                    trees=[MurmurRPC.Channel(id=channelId)],
                    text=text)
        self._stub.TextMessageSend(message)

    @throws_server_booted_exception
    def getACL(self, channelId):
        return toIce(self._stub.ACLGet(MurmurRPC.Channel(
            id=channelId,
            server=self._ice())))

    @throws_server_booted_exception
    def setACL(self, channelId, acls, groups, inherit):
        self._stub.ACLSet(MurmurRPC.ACL.List(
            server=self._ice(),
            channel=MurmurRPC.Channel(id=channelId),
            acls=[MurmurRPC.ACL(
                apply_here=acl.applyHere,
                apply_subs=acl.applySubs,
                inherited=acl.inherited,
                user=MurmurRPC.DatabaseUser(id=acl.userid)
                if acl.userid != -1 else None,
                group=MurmurRPC.Group(name=acl.group) if acl.group else None,
                allow=acl.allow,
                deny=acl.deny) for acl in acls],
            groups=[MurmurRPC.ACL.Group(
                name=group.name,
                inherited=group.inherited,
                inherit=group.inherit,
                inheritable=group.inheritable,
                users_add=[MurmurRPC.DatabaseUser(id=user)
                           for user in group.add],
                users_remove=[MurmurRPC.DatabaseUser(id=user)
                              for user in group.remove],
                users=[MurmurRPC.DatabaseUser(id=user)
                       for user in group.members]) for group in groups]))

    @throws_server_booted_exception
    def addUserToGroup(self, channelId, session, group):
        self._stub.ACLAddTemporaryGroup(MurmurRPC.ACL.TemporaryGroup(
            server=self._ice(),
            channel=MurmurRPC.Channel(id=channelId),
            user=MurmurRPC.User(session=session),
            name=group))

    @throws_server_booted_exception
    def removeUserFromGroup(self, channelId, session, group):
        self._stub.ACLRemoveTemporaryGroup(MurmurRPC.ACL.TemporaryGroup(
            server=self._ice(),
            channel=MurmurRPC.Channel(id=channelId),
            user=MurmurRPC.User(session=session),
            name=group))

    @throws_server_booted_exception
    def redirectWhisperGroup(self, session, source, target):
        whisperGroup = MurmurRPC.RedirectWhisperGroup(
                server=self._ice(),
                user=MurmurRPC.User(session=session),
                source=MurmurRPC.ACL.Group(name=source),
                target=MurmurRPC.ACL.Group(name=target) if target else None)
        if not target:
            self._stub.RedirectWhisperGroupRemove(whisperGroup)
        else:
            self._stub.RedirectWhisperGroupAdd(whisperGroup)

    @throws_server_booted_exception
    def getUserNames(self, ids):
        def getUserName(userId):
            try:
                return self._stub.DatabaseUserGet(MurmurRPC.DatabaseUser(
                    server=self._ice(),
                    id=userId)).name
            except grpc.RpcError, e:
                if e.code() == grpc.StatusCode.INVALID_ARGUMENT and \
                        e.details() == 'invalid user':
                    return ''
                raise
        return [getUserName(userId) for userId in ids]

    @throws_server_booted_exception
    def getUserIds(self, names):
        # There seems to be really no good way to implement this with gRPC
        users = {v: k for k, v in self.getRegisteredUsers('').iteritems()}
        return [users.get(name, -1) for name in names]

    def _userInfoMap(self, userId, info):
        return MurmurRPC.DatabaseUser(
                server=self._ice(),
                id=userId,
                name=info.get(UserInfo.UserName),
                email=info.get(UserInfo.UserEmail),
                comment=info.get(UserInfo.UserComment),
                hash=info.get(UserInfo.UserHash),
                password=info.get(UserInfo.UserPassword),
                last_active=info.get(UserInfo.UserLastActive))

    @throws_server_booted_exception
    def registerUser(self, info):
        result = self._stub.DatabaseUserRegister(self._userInfoMap(None, info))
        return result.id

    @throws_server_booted_exception
    def unregisterUser(self, userId):
        self._stub.DatabaseUserDeregister(self._userInfoMap(userId, dict()))

    @throws_server_booted_exception
    def updateRegistration(self, userId, info):
        self._stub.DatabaseUserUpdate(self._userInfoMap(userId, info))

    @throws_server_booted_exception
    def getRegistration(self, userId):
        return toIce(self._stub.DatabaseUserGet(MurmurRPC.DatabaseUser(
            server=self._ice(),
            id=userId)))

    @throws_server_booted_exception
    def getRegisteredUsers(self, filterStr):
        query = MurmurRPC.DatabaseUser.Query(
                server=self._ice(),
                filter=filterStr)
        users = self._stub.DatabaseUserQuery(query).users
        return {user.id: user.name for user in users}

    @throws_server_booted_exception
    def verifyPassword(self, name, pw):
        try:
            self._stub.DatabaseUserVerify(MurmurRPC.DatabaseUser.Verify(
                server=self._ice(),
                name=name,
                password=pw)).id
        except grpc.RpcError, e:
            if e.code() == grpc.StatusCode.NOT_FOUND:
                return -2
            if e.code() == grpc.StatusCode.INVALID_ARGUMENT:
                return -1

    @throws_server_booted_exception
    def getTexture(self, userId):
        return self._stub.DatabaseUserGet(MurmurRPC.DatabaseUser(
            server=self._ice(),
            id=userId)).texture

    @throws_server_booted_exception
    def setTexture(self, userId, tex):
        self._stub.DatabaseUserUpdate(MurmurRPC.DatabaseUser(
            server=self._ice(),
            id=userId,
            texture=tex))

    @throws_server_booted_exception
    def getUptime(self):
        return self._get().uptime.secs


class ServerAuthenticator:
    def __init__(self): pass


class ServerCallback:
    def __init__(self): pass


class ServerContextCallback:
    def __init__(self): pass


class ServerUpdatingAuthenticator:
    def __init__(self): pass


class ClientAdapter:
    def addWithUUID(self, cb):
        return cb


class MetaCallbackPrx:
    @staticmethod
    def uncheckedCast(cbprx): return cbprx


class ServerContextCallbackPrx:
    @staticmethod
    def uncheckedCast(cbprx): return cbprx
