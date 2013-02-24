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

import ConfigParser
import types

class Config(object):
    """
    Small abstraction for config loading
    """

    def __init__(self, filename = None, default = None):
        if (filename and not default) or \
            (not filename and not default): return
        
        sections = set(default.iterkeys())
        if filename:
            cfg = ConfigParser.RawConfigParser()
            cfg.optionxform = str
            cfg.read(filename)
            sections.update(cfg.sections())
            
        for section in sections:
            if type(section) == types.FunctionType: continue
            
            match = None
            for default_section in default.iterkeys():
                try:
                    if section == default_section or \
                        (type(default_section) == types.FunctionType and default_section(section)):
                        match = default_section
                        break
                except ValueError:
                    continue
                
            if match == None:
                continue

            optiondefaults = default[match]

            if not optiondefaults:
                # Output this whole section as a list of raw key/value tuples
                if not filename:
                    self.__dict__[section] = []
                else:
                    try:
                        self.__dict__[section] = cfg.items(section)
                    except ConfigParser.NoSectionError:
                        self.__dict__[section] = []
            else:
                self.__dict__[section] = Config()
                for name, conv, vdefault in optiondefaults:
                    if not filename:
                        self.__dict__[section].__dict__[name] = vdefault
                    else:
                        try:
                            self.__dict__[section].__dict__[name] = conv(cfg.get(section, name))
                        except (ValueError, ConfigParser.NoSectionError, ConfigParser.NoOptionError):
                            self.__dict__[section].__dict__[name] = vdefault
    
    def __getitem__(self, key):
        return self.__dict__.__getitem__(key)
    
    def __contains__(self, key):
        return self.__dict__.__contains__(key)

def x2bool(s):
    """
    Helper function to convert strings from the config to bool
    """
    if isinstance(s, bool):
        return s
    elif isinstance(s, basestring):
        return s.strip().lower() in ['1', 'true']
    raise ValueError()

def commaSeperatedIntegers(s):
    """
    Helper function to convert a string from the config
    containing comma seperated integers into a list of integers
    """
    return map(int, s.split(','))

def commaSeperatedStrings(s):
    """
    Helper function to convert a string from the config
    containing comma seperated strings into a list of strings
    """
    return map(str.strip, s.split(','))

def commaSeperatedBool(s):
    """
    Helper function to convert a string from the config
    containing comma seperated strings into a list of booleans
    """
    return map(x2bool, s.split(','))
