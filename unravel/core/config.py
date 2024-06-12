#!/usr/bin/env python3

"""
This script defines classes for reading configuration settings from a file and accessing them
using attribute-style access. It uses the ConfigParser module to parse configuration files
and provides convenient access to configuration sections and values.

Classes:
    - AttrDict: A dictionary subclass that allows attribute access to its keys.
    - Config: A class to read configuration from a file and allow attribute access using RawConfigParser.
    - Configuration: A class to hold global configuration settings.

Usage:
    Import the classes and use them to read and access configuration settings from a file.

Example:
    from path.to.this.script import Config, Configuration

    config = Config("path/to/config_file.ini")
    database_config = config.database
    print(database_config.username)  # Access a configuration value using attribute access

Classes:
    AttrDict
        - A dictionary that allows attribute access to its keys.
        - Methods:
            - __getattr__: Returns the value associated with the given key.

    Config
        - Reads configuration from a file and allows attribute access using RawConfigParser.
        - Methods:
            - __init__: Initializes the Config object and reads the configuration file.
            - __getattr__: Returns a dictionary-like object for the specified section, with comments stripped from values.
            - _strip_comments: Static method that strips inline comments from configuration values.

    Configuration
        - Holds global configuration settings.
        - Attributes:
            - verbose: A boolean flag to control verbosity of the application.

Notes:
    - The Config class uses the RawConfigParser from the configparser module to parse the configuration file.
    - The AttrDict class allows for convenient attribute access to dictionary keys.
    - The Configuration class can be extended to hold additional global settings as needed.
"""

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