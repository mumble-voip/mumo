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
    NO_SERVER = ""
    NO_TEAM = -1

    def __init__(self, path = ":memory:"):
        """
        Initialize the sqlite database in the given path. If no path
        is given the database is created in memory.
        """
        self.db = sqlite3.connect(path)
        if self.db:
            self.db.execute("""
                CREATE TABLE IF NOT EXISTS controlled_channels(
                    sid INTEGER NOT NULL,
                    cid INTEGER NOT NULL,
                    game TEXT NOT NULL,
                    server TEXT NOT NULL default "",
                    team INTEGER NOT NULL default -1,
                    UNIQUE(sid, cid),
                    PRIMARY KEY (sid, game, server, team)
                )""")
            
            self.db.execute("""
                CREATE TABLE IF NOT EXISTS mapped_names (
                    sid INTEGER NOT NULL,
                    game TEXT NOT NULL,
                    server TEXT NOT NULL default "",
                    team INTEGER default -1,
                    name TEXT NOT NULL,
                    PRIMARY KEY (sid, game, server, team)
                )""")
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
    
    
    def nameFor(self, sid, game, server = NO_SERVER, team = NO_TEAM, default = ""):
        """
        Returns the mapped name for the given parameters or default if no
        mapping exists.
        """
        assert(sid != None and game != None)
        assert(not (team != self.NO_TEAM and server == self.NO_SERVER))
        
        v = self.db.execute("SELECT name FROM mapped_names WHERE sid is ? and game is ? and server is ? and team is ?", [sid, game, server, team]).fetchone()
        return v[0] if v else default
    
    def mapName(self, name, sid, game, server = NO_SERVER, team = NO_TEAM):
        """
        Stores a mapping for the given (sid, game, server, team) combination
        to the given name. The mapping can then be retrieved with nameFor() in
        the future.
        """
        assert(sid != None and game != None)
        assert(not (team != self.NO_TEAM and server == self.NO_SERVER))
        
        self.db.execute("INSERT OR REPLACE into mapped_names (sid, game, server, team, name) VALUES (?,?,?,?,?)",[sid, game, server, team, name])
        self.db.commit()
    
    def cidFor(self, sid, game, server = NO_SERVER, team = NO_TEAM):
        """
        Returns the channel id for game specific channel. If only game
        is passed the game root channel cid is returned. If additionally
        server (and team) are passed the server (/team) channel cid is returned.
        
        If no channel matching the arguments has been registered with the database
        before None is returned.
        """
        assert(sid != None and game != None)
        assert(not (team != self.NO_TEAM and server == self.NO_SERVER))
        
        v = self.db.execute("SELECT cid FROM controlled_channels WHERE sid is ? and game is ? and server is ? and team is ?", [sid, game, server, team]).fetchone()
        return v[0] if v else None

    def channelForCid(self, sid, cid):
        """
        Returns a tuple of (sid, cid, game, server, team) for the given cid.
        Returns None if the cid is unknown.
        """
        assert(sid != None and cid != None)
        return self.db.execute("SELECT sid, cid, game, server, team FROM controlled_channels WHERE sid is ? and cid is ?", [sid, cid]).fetchone()
        
    def channelFor(self, sid, game, server = NO_SERVER, team = NO_TEAM):
        """
        Returns matching channel as (sid, cid, game, server, team) tuple. Matching
        behavior is the same as for cidFor()
        """
        assert(sid != None and game != None)
        assert(not (team != self.NO_TEAM and server == self.NO_SERVER))
        
        v = self.db.execute("SELECT sid, cid, game, server, team FROM controlled_channels WHERE sid is ? and game is ? and server is ? and team is ?", [sid, game, server, team]).fetchone()
        return v
    
    def channelsFor(self, sid, game, server = NO_SERVER, team = NO_TEAM):
        """
        Returns matching channels as a list of (sid, cid, game, server, team) tuples.
        If only the game is passed all server and team channels are matched.
        This can be limited by passing server (and team).
        Returns empty list if no matches are found.
        """
        assert(sid != None and game != None)
        assert(not (team != self.NO_TEAM and server == self.NO_SERVER))
        
        suffix, params = self.__whereClauseForOptionals(server, team)
        return self.db.execute("SELECT sid, cid, game, server, team FROM controlled_channels WHERE sid is ? and game is ?" + suffix, [sid, game] + params).fetchall()
    
    def registerChannel(self, sid, cid, game, server = NO_SERVER, team = NO_TEAM):
        """
        Register a given channel with the database.
        """
        assert(sid != None and game != None)
        assert(not (team != self.NO_TEAM and server == self.NO_SERVER))
        
        self.db.execute("INSERT INTO controlled_channels (sid, cid, game, server, team) VALUES (?,?,?,?,?)", [sid, cid, game, server, team])
        self.db.commit()
        return True
    
    def __whereClauseForOptionals(self, server, team):
        """
        Generates where class conditions that interpret missing server
        or team as "don't care".
        
        Returns (suffix, additional parameters) tuple
        """
        
        if server != self.NO_SERVER and team != self.NO_TEAM:
            return (" and server is ? and team is ?", [server, team])
        elif server != self.NO_SERVER:
            return (" and server is ?", [server])
        else:
            return ("", [])
        
    def unregisterChannel(self, sid, game, server = NO_SERVER, team = NO_TEAM):
        """
        Unregister a channel previously registered with the database.
        """
        assert(sid != None and game != None)
        assert(not (team != self.NO_TEAM and server == self.NO_SERVER))
        
        suffix, params = self.__whereClauseForOptionals(server, team)
        self.db.execute("DELETE FROM controlled_channels WHERE sid is ? and game is ?" + suffix, [sid, game] + params)
        self.db.commit()
        
    def dropChannel(self, sid, cid):
        """
        Drops channel with given sid + cid
        """
        assert(sid != None and cid != None)
        
        self.db.execute("DELETE FROM controlled_channels WHERE sid is ? and cid is ?", [sid, cid])
        self.db.commit()
    
    def isRegisteredChannel(self, sid, cid):
        """
        Returns true if a channel with given sid and cid is registered
        """
        assert(sid != None and cid != None)
        
        res = self.db.execute("SELECT cid FROM controlled_channels WHERE sid is ? and cid is ?", [sid, cid]).fetchone()
        return res != None
        
    def registeredChannels(self):
        """
        Returns channels as a list of (sid, cid, game, server team) tuples grouped by sid
        """
        return self.db.execute("SELECT sid, cid, game, server, team FROM controlled_channels ORDER by sid").fetchall()
    
    def reset(self):
        """
        Deletes everything in the database
        """
        self.db.execute("DELETE FROM mapped_names")
        self.db.execute("DELETE FROM controlled_channels")
        self.db.commit()
    
if __name__ == "__main__":
    pass
