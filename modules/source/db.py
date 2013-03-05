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

import sqlite3

#TODO: Functions returning channels probably should return a dict instead of a tuple

class SourceDB(object):
    def __init__(self, path = ":memory:"):
        """
        Initialize the sqlite database in the given path. If no path
        is given the database is created in memory.
        """
        self.db = sqlite3.connect(path)
        if self.db:
            self.db.execute("CREATE TABLE IF NOT EXISTS source(sid INTEGER, cid INTEGER, game TEXT, server TEXT, team INTEGER)")
            self.db.execute("VACUUM")
            self.db.commit()

    def close(self):
        """
        Closes the database connection
        """
        if self.db:
            self.db.commit()
            self.db.close()
            self.db = None
        
    def isOk(self):
        """
        True if the database is correctly initialized
        """
        return self.db != None
        
    def cidFor(self, sid, game, server = None, team = None):
        """
        Returns the channel id for game specific channel. If only game
        is passed the game root channel cid is returned. If additionally
        server (and team) are passed the server (/team) channel cid is returned.
        
        If no channel matching the arguments has been registered with the database
        before None is returned.
        """
        assert(sid != None and game != None)
        assert(not (team != None and server == None))
        
        v = self.db.execute("SELECT cid FROM source WHERE sid is ? and game is ? and server is ? and team is ?", [sid, game, server, team]).fetchone()
        return v[0] if v else None

    def channelForCid(self, sid, cid):
        """
        Returns a tuple of (sid, cid, game, server, team) for the given cid.
        Returns None if the cid is unknown.
        """
        assert(sid != None and cid != None)
        return self.db.execute("SELECT sid, cid, game, server, team FROM source WHERE sid is ? and cid is ?", [sid, cid]).fetchone()
        
    def channelFor(self, sid, game, server = None, team = None):
        """
        Returns matching channel as (sid, cid, game, server, team) tuple. Matching
        behavior is the same as for cidFor()
        """
        assert(sid != None and game != None)
        assert(not (team != None and server == None))
        
        v = self.db.execute("SELECT sid, cid, game, server, team FROM source WHERE sid is ? and game is ? and server is ? and team is ?", [sid, game, server, team]).fetchone()
        return v
    
    def channelsFor(self, sid, game, server = None, team = None):
        """
        Returns matching channels as a list of (sid, cid, game, server, team) tuples.
        If only the game is passed all server and team channels are matched.
        This can be limited by passing server (and team).
        Returns empty list if no matches are found.
        """
        assert(sid != None and game != None)
        assert(not (team != None and server == None))
        
        suffix, params = self.__whereClauseForOptionals(server, team)
        return self.db.execute("SELECT sid, cid, game, server, team FROM source WHERE sid is ? and game is ?" + suffix, [sid, game] + params).fetchall()
    
    def registerChannel(self, sid, cid, game, server = None, team = None):
        """
        Register a given channel with the database.
        """
        assert(sid != None and game != None)
        assert(not (team != None and server == None))
        
        self.db.execute("INSERT INTO source (sid, cid, game, server, team) VALUES (?,?,?,?,?)", [sid, cid, game, server, team])
        self.db.commit()
        return True
    
    def __whereClauseForOptionals(self, server, team):
        """
        Generates where class conditions that interpret missing server
        or team as "don't care".
        
        Returns (suffix, additional parameters) tuple
        """
        
        if server != None and team != None:
            return (" and server is ? and team is ?", [server, team])
        elif server != None:
            return (" and server is ?", [server])
        else:
            return ("", [])
        
    def unregisterChannel(self, sid, game, server = None, team = None):
        """
        Unregister a channel previously registered with the database.
        """
        assert(sid != None and game != None)
        assert(not (team != None and server == None))
        
        suffix, params = self.__whereClauseForOptionals(server, team)
        self.db.execute("DELETE FROM source WHERE sid is ? and game is ?" + suffix, [sid, game] + params)
        self.db.commit()
        
    def dropChannel(self, sid, cid):
        """
        Drops channel with given sid + cid
        """
        self.db.execute("DELETE FROM source WHERE sid is ? and cid is ?", [sid, cid])
        self.db.commit()
    
    def isRegisteredChannel(self, sid, cid):
        """
        Returns true if a channel with given sid and cid is registered
        """
        res = self.db.execute("SELECT cid FROM source WHERE sid is ? and cid is ?", [sid, cid]).fetchone()
        return res != None
        
    def registeredChannels(self):
        """
        Returns channels as a list of (sid, cid, game, server team) tuples grouped by sid
        """
        return self.db.execute("SELECT sid, cid, game, server, team FROM source ORDER by sid").fetchall()
    
    def reset(self):
        """
        Deletes everything in the database
        """
        self.db.execute("DELETE FROM source")
        self.db.commit()
    
if __name__ == "__main__":
    pass