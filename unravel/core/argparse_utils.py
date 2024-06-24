#!/usr/bin/env python3

"""
This script defines custom classes to enhance the formatting and handling of argparse arguments,
with a focus on suppressing metavar display and improving help message readability.

Classes:
    - SuppressMetavar: A custom HelpFormatter class that suppresses the display of metavar for
                       arguments and customizes the epilog formatting.
    - SM: A custom argparse.Action class that suppresses the display of metavar and manages
          argument values.

Usage:
    Import the classes and use them in an argparse-based script to suppress metavar and format help
    messages for improved readability.

Example:
    import argparse
    from path.to.this.script import SuppressMetavar, SM

    parser = argparse.ArgumentParser(description="A script example.", formatter_class=SuppressMetavar)
    parser.add_argument('-e', '--example', help='Example argument', action=SM)
    args = parser.parse_args()

Classes:
    SuppressMetavar
        - Inherits from argparse.HelpFormatter to modify the formatting of action invocations and epilog text.
        - Methods:
            - _format_action_invocation: Customizes the formatting of argument options.
            - _fill_text: Formats the epilog text with specified indentation and width.

    SM
        - Inherits from argparse.Action to suppress metavar display and manage argument values.
        - Methods:
            - __init__: Initializes the custom action and sets the metavar to an empty string or tuple.
            - __call__: Sets the argument values in the namespace, handling both single and multiple values.

Notes:
    - This script relies on the argparse library for command-line argument parsing.
    - The SuppressMetavar class is designed to improve the readability of help messages by suppressing
      metavar display and customizing the formatting of epilog text.
"""

import argparse
import textwrap

class SuppressMetavar(argparse.HelpFormatter):
    def _format_action_invocation(self, action):
        if not action.option_strings:
            metavar, = self._metavar_formatter(action, action.dest)(1)
            return metavar
        else:
            parts = []
            if action.nargs == 0:
                parts.extend(action.option_strings)
            else:
                for option_string in action.option_strings:
                    parts.append(option_string)
            return ', '.join(parts)
    
    def _fill_text(self, text, width, indent):
        # This method formats the epilog. Override it to split the text into lines and format each line individually.
        text_lines = text.splitlines()
        formatted_lines = [textwrap.fill(line, width, initial_indent=indent, subsequent_indent=indent) for line in text_lines]
        return '\n'.join(formatted_lines)


#Suppress metavar
class SM(argparse.Action):
    def __init__(self, option_strings, dest, nargs=None, **kwargs):
        if nargs is not None:
            kwargs.setdefault('metavar', '')
        super(SM, self).__init__(option_strings, dest, nargs=nargs, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        # If this action is for a single value (not expecting multiple values)
        if self.nargs is None or self.nargs == 0:
            setattr(namespace, self.dest, values)  # Set the single value directly
        else:
            # If the action expects multiple values, handle it as a list
            if isinstance(values, list):
                setattr(namespace, self.dest, values)
            else:
                current_values = getattr(namespace, self.dest, [])
                if not isinstance(current_values, list):
                    current_values = [current_values]
                current_values.append(values)
                setattr(namespace, self.dest, current_values)
