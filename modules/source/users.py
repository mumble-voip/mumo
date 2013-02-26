#!/usr/bin/env python
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

class User(object):
    """
    User to hold state as well as parsed data fields in a
    sane fashion.
    """
    def __init__(self, state, identity=None, game=None, server=None):
        self.state = state
        self.identity = identity or {}
        self.server = server
        self.game = game
        
    def valid(self):
        """ True if valid data is available for all fields """
        return self.state and self.identity and self.server and self.game
    
    def hasContextOrIdentityChanged(self, otherstate):
        """ Checks whether the given state diverges from this users's """
        return self.state.context != otherstate.context or \
               self.state.identity != otherstate.identity 
               
    def updateState(self, state):
        """ Updates the state of this user """
        self.state = state
        
    def updateData(self, identity, game, server):
        """ Updates the data fields for this user """
        self.identity = identity
        self.game = game
        self.server = server
        
class UserRegistry(object):
    """
    Registry to store User objects for given servers
    and sessions.
    """
    
    def __init__(self):
        self.users = {} # {session:user, ...}
    
    def get(self, sid, session):
        """ Return user or None from registry """
        try:
            return self.users[sid][session]
        except KeyError:
            return None
        
    def add(self, sid, session, user):
        """ Add new user to registry """
        assert(isinstance(user, User))
        
        if not sid in self.users:
            self.users[sid] = {session:user}
        elif not session in self.users[sid]:
            self.users[sid][session] = user
        else:
            return False
        return True
    
    def addOrUpdate(self, sid, session, user):
        """ Add user or overwrite existing one """
        assert(isinstance(user, User))
        
        if not sid in self.users:
            self.users[sid] = {session:user}
        else:
            self.users[sid][session] = user
            
        return True
    
    def remove(self, sid, session):
        """ Remove user from registry """
        try:
            del self.users[sid][session]
        except KeyError:
            return False
        return True  
    
    def usingChannel(self, sid, cid):
        """
        Return true if any user in the registry is occupying the given channel
        """
        for user in self.users[sid].itervalues():
            if user.state and user.state.channel == cid:
                return True
        
        return False

