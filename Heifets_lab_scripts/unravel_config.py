#!/usr/bin/env python3

import configparser

class AttrDict(dict):
    """A dictionary that allows attribute access."""
    def __getattr__(self, name):
        return self[name]

class Config:
    """A class to read configuration from a file and allow attribute access."""
    def __init__(self, config_file):
        self.parser = configparser.ConfigParser()
        self.parser.read(config_file)

    def __getattr__(self, section):
        if section in self.parser:
            return AttrDict(self.parser[section])
        else:
            raise AttributeError(f"No such section: {section}")
        
class Configuration:
    """A class to hold configuration settings."""
    verbose = False