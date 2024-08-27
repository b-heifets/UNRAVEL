#!/usr/bin/env python3

"""
This script defines custom classes to enhance the formatting and handling of argparse arguments
using the Rich library for beautiful terminal output.

Classes:
    - SuppressMetavar: A custom RichHelpFormatter class that suppresses the display of metavar for
                       arguments and customizes the epilog formatting.
    - SM: A custom argparse.Action class that suppresses the display of metavar across all nargs 
          configurations and manages argument values.

Usage:
    Import the classes and use them in an argparse-based script to suppress metavar and format help
    messages with Rich's styled output.

Example:
    import argparse
    from rich_argparse import RichHelpFormatter
    from path.to.this.script import SuppressMetavar, SM

    parser = argparse.ArgumentParser(formatter_class=SuppressMetavar)
    parser.add_argument('-e', '--example', help='Example argument', action=SM)
    args = parser.parse_args()

Classes:
    SuppressMetavar
        - Inherits from RichHelpFormatter to modify the formatting of action invocations and epilog text.
        - Methods:
            - _format_action_invocation: Customizes the formatting of argument options.
            - _fill_text: Formats the epilog text with specified indentation and width.

    SM
        - Inherits from argparse.Action to suppress metavar display and manage argument values.
        - Methods:
            - __init__: Initializes the custom action and sets the metavar to an empty string or tuple.
            - __call__: Sets the argument values in the namespace, handling both single and multiple values.

Note:
    - This script relies on the rich and argparse libraries for enhanced help message formatting.
    - The SuppressMetavar class is specifically designed to work with Rich's RichHelpFormatter for styled terminal output.
    - nargs='``+``' with action=SM: This combination causes issues when the terminal window is small. 
    - Use nargs='``*``' with action=SM if zero arguments are acceptable, or drop action=SM to avoid conflicts.
    - Difference:
    - nargs='``+``' requires at least one argument.
    - nargs='``*``' allows zero or more arguments, providing more flexibility but no guarantee of input.
"""

import argparse
import re
from rich import print
from rich.text import Text
from rich_argparse import RichHelpFormatter
import textwrap

# Custom RichHelpFormatter class to suppress metavar display
class SuppressMetavar(RichHelpFormatter):
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

# Custom action class to suppress metavar across all nargs configurations
class SM(argparse.Action):
    def __init__(self, option_strings, dest, nargs=None, **kwargs):
        # Forcefully suppress metavar display by setting it to an empty string or an appropriate tuple
        if nargs is not None:
            # Use an empty tuple with a count matching nargs when nargs is a specific count or '+'
            kwargs['metavar'] = tuple('' for _ in range(nargs if isinstance(nargs, int) else 1))
        else:
            # Default single metavar suppression
            kwargs['metavar'] = ''
        super(SM, self).__init__(option_strings, dest, nargs=nargs, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        # Simply set the value(s) in the namespace
        if self.nargs is None or self.nargs == 0:
            setattr(namespace, self.dest, values)  # Directly set the value
        else:
            # Handle multiple values as a list
            current_values = getattr(namespace, self.dest, [])
            if not isinstance(current_values, list):
                current_values = [current_values]  # Ensure it is a list
            current_values.append(values)
            setattr(namespace, self.dest, current_values)  # Append new values

def format_docstring_for_terminal(docstring):
    """
    Apply rich formatting to a docstring for enhanced terminal display.

    This function processes a docstring by applying various formatting styles
    using the Rich library. It handles sections like script descriptions,
    usage examples, command arguments, and specific keywords like "Inputs:",
    "Outputs:", "Note:", "Prereqs:", and "Next steps:". Additionally, it applies
    special styles to text enclosed in double backticks and command-line flags.

    Parameters
    ----------
    docstring : str
        The original docstring to be formatted.

    Returns
    -------
    Text
        A `rich.text.Text` object containing the formatted text.

    Notes
    -----
    The function applies the following styles:
    - "UNRAVEL" is styled with a custom multi-colored format.
    - Script description lines (before "Usage:") are styled as bold.
    - Lines starting with "Usage:" are styled as bold cyan.
    - Command names enclosed in double backticks or appearing in usage examples are styled as bold bright magenta.
    - Required arguments (before the first optional argument) are styled as purple3.
    - Optional arguments (within square brackets) are styled as bright blue.
    - Command-line flags (e.g., `-m`, `--input`) are styled as bold.
    - Section headers "Inputs:", "Outputs:", "Note:", "Prereqs:", and "Next steps:" 
      are styled in green, gold1, dark_orange, red, and grey50, respectively.
    """

    # Regex to find text enclosed in double backticks
    command_pattern = r"``(.*?)``"
    
    # Regex to find flags (like -m or --input)
    flag_pattern = r"(\s-\w|\s--\w[\w-]*)"

    # Prepare the final formatted text
    final_text = Text()

    # Split the docstring into lines for processing
    lines = docstring.splitlines()

    # Flags to manage the sections
    in_description = True
    command = None

    for line in lines:
        # Replace text between double backticks with bold bright_magenta
        line = re.sub(command_pattern, r"[bold bright_magenta]\1[/]", line)

        if in_description:
            # Style "UNRAVEL" with custom formatting
            line = line.replace("UNRAVEL", "[red1]U[/][dark_orange]N[/][bold gold1]R[/][green]A[/][bright_blue]V[/][purple3]E[/][bright_magenta]L[/]")

            if line.strip().startswith("Usage"):
                in_description = False
                # Apply bold cyan style to the Usage line
                styled_line = Text(line, style="bold cyan")
            else:
                # Apply bold style to the script description
                styled_line = Text.from_markup(line, style="bold")

            final_text.append(styled_line)
            final_text.append("\n")
            continue  # Skip the rest of the loop to avoid adding the line twice

        if line.strip().startswith("Usage"):
            # Apply bold cyan style to subsequent Usage lines
            styled_line = Text(line, style="bold cyan")
            final_text.append(styled_line)
            final_text.append("\n")
            continue

        # Skip lines that start with "---"
        if line.strip().startswith("---"):
            continue

        # Apply specific colors for section headers
        if line.strip().startswith("Inputs:"):
            styled_line = Text(line, style="green")
        elif line.strip().startswith("Outputs:"):
            styled_line = Text(line, style="gold1")
        elif line.strip().startswith("Note:"):
            styled_line = Text(line, style="dark_orange")
        elif line.strip().startswith("Prereqs:"):
            styled_line = Text(line, style="red")
        elif line.strip().startswith("Next steps:"):
            styled_line = Text(line, style="grey50")
        else:
            # Extract the command from the line
            if not command and " " in line:
                command = line.strip().split(" ")[0]

            if command and line.strip().startswith(command):
                # Ensure the command is styled as bold bright magenta (e.g., when it is not in backticks)
                line = line.replace(command, f"[bold bright_magenta]{command}[/]", 1)

                # Remove tabs from the line
                line = line.replace("\t", "")
                line = line.replace("    ", "")

                # Check if there are optional arguments in the line
                index = line.find(' [')

                # Split the line into required and optional parts
                if index != -1:  # If there are optional arguments
                    required_part = line[:index].strip()
                    optional_part = line[index:].strip()
                else:
                    required_part = line.strip()
                    optional_part = ""

                # Style the flags as bold
                required_part = re.sub(flag_pattern, r"[bold]\1[/]", required_part)
                optional_part = re.sub(flag_pattern, r"[bold]\1[/]", optional_part)

                # Style the required arguments (before the bracket) as purple3
                styled_required = Text.from_markup(f"[purple3]{required_part}[/]") if required_part else Text()

                # Style the optional arguments (within the bracket) as bright_blue
                styled_optional = Text.from_markup(f"[bright_blue]{optional_part}[/]") if optional_part else Text()

                # Combine the styled parts together
                styled_line = Text()
                styled_line.append(styled_required)
                if optional_part:  # Adding space between required and optional parts only if there are optional parts
                    styled_line.append(" ")
                styled_line.append(styled_optional)
            else:
                # Revert to default styling for lines after the usage section
                styled_line = Text.from_markup(line)

        final_text.append(styled_line)
        final_text.append("\n")

    # Add a separator line to visually separate the docstring from argparse help
    
    # initialize console
    from rich.console import Console


    console_width = Console().size.width
    separator = Text("─" * console_width, style="dim")
    final_text.append(separator)
    final_text.append("\n")

    return final_text


# Custom help action to print formatted __doc__ and the argument help
class CustomHelpAction(argparse.Action):
    def __init__(self, option_strings, dest=argparse.SUPPRESS, default=argparse.SUPPRESS, help=None, docstring=None):
        self.docstring = docstring
        super(CustomHelpAction, self).__init__(option_strings=option_strings, dest=dest, default=default, nargs=0, help=help)

    def __call__(self, parser, namespace, values, option_string=None):
        if self.docstring:
            print(format_docstring_for_terminal(self.docstring))
        else:
            print(format_docstring_for_terminal(__doc__))
        parser.print_help()
        parser.exit()