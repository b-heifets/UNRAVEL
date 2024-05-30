#!/usr/bin/env python3

import configparser
import re

class AttrDict(dict):
    """A dictionary that allows attribute access."""
    def __getattr__(self, name):
        return self[name]

class Config:
    """A class to read configuration from a file and allow attribute access using RawConfigParser."""
    def __init__(self, config_file):
        self.parser = configparser.RawConfigParser()
        self.parser.read(config_file)

    def __getattr__(self, section):
        if section in self.parser:
            section_dict = {k: self._strip_comments(v) for k, v in self.parser[section].items()}
            return AttrDict(section_dict)
        else:
            raise AttributeError(f"No such section: {section}")

    @staticmethod
    def _strip_comments(value):
        """Strip inline comments from configuration values."""
        return re.sub(r"\s*#.*$", "", value, flags=re.M)
    
class Configuration:
    """A class to hold configuration settings."""
    verbose = False