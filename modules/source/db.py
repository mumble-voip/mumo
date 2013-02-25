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

class SourceDB(object):
    def __init__(self, path = ":memory:"):
        self.db = sqlite3.connect(path)
        if self.db:
            self.db.execute("CREATE TABLE IF NOT EXISTS source(sid INTEGER, cid INTEGER, game TEXT, server TEXT, team INTEGER)")
            self.db.commit()

    def close(self):
        if self.db:
            self.db.commit()
            self.db.close()
            self.db = None
        
    def isOk(self):
        """ True if the database is correctly initialized """
        return self.db != None
        
    def cidFor(self, sid, game, server = None, team = None):
        assert(sid != None and game != None)
        assert(not (team != None and server == None))
        
        v = self.db.execute("SELECT cid FROM source WHERE sid is ? and game is ? and server is ? and team is ?", [sid, game, server, team]).fetchone()
        return v[0] if v else None
    
    def registerChannel(self, sid, cid, game, server = None, team = None):
        assert(sid != None and game != None)
        assert(not (team != None and server == None))
        
        self.db.execute("INSERT INTO source (sid, cid, game, server, team) VALUES (?,?,?,?,?)", [sid, cid, game, server, team])
        self.db.commit()
        return True
    
    def unregisterChannel(self, sid, game, server = None, team = None):
        assert(sid != None and game != None)
        assert(not (team != None and server == None))
        
        base = "DELETE FROM source WHERE sid is ? and game is ?"
        
        if server != None and team != None:
            self.db.execute(base + " and server is ? and team is ?", [sid, game, server, team])
        elif server != None:
            self.db.execute(base + " and server is ?", [sid, game, server])
        else:
            self.db.execute(base, [sid, game])
        
        self.db.commit()
        
    def dropChannel(self, sid, cid):
        """ Drops channel with given sid + cid """
        self.db.execute("DELETE FROM source WHERE sid is ? and cid is ?", [sid, cid])
        self.db.commit()
    
    def registeredChannels(self):
        """ Returns channels as a list of (sid, cid, game, server team) tuples grouped by sid """
        return self.db.execute("SELECT sid, cid, game, server, team FROM source ORDER by sid").fetchall()
    
    def reset(self):
        """ Deletes everything in the database """
        self.db.execute("DELETE FROM source")
        self.db.commit()
    
if __name__ == "__main__":
    pass