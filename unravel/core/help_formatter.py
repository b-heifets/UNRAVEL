#!/usr/bin/env python3

"""
This script enhances the formatting and handling of argparse arguments by defining custom classes that improve 
the readability and usability of help messages, with a focus on suppressing metavar display and leveraging 
the Rich library for styled terminal output.

Classes:
    - SuppressMetavar: A custom HelpFormatter class that suppresses the display of metavar for arguments and 
                       customizes the formatting of action invocations and epilog text.
    - SM: A custom argparse.Action class that manages argument values while suppressing metavar display across 
          all nargs configurations.
    - RichArgumentParser: An enhanced ArgumentParser that integrates custom help message formatting and 
                            handling, including filtering and styling of argparse help text.
    - CustomHelpAction: An argparse Action that displays a richly formatted help message, integrating the script's 
                        docstring.

Functions:
    - format_argparse_help: Processes and applies custom styles to argparse help text, highlighting flags, 
                            default values, and section headers with specific colors and styles.
    - format_docstring_for_terminal: Formats the script's docstring with Rich's styled output, improving readability 
                                     by highlighting sections, command names, and other key elements.

Usage:
    The custom classes and functions can be used in any argparse-based script to suppress metavar display, 
    format help messages with Rich's styled output, and enhance the overall user experience.

Example:
    import argparse
    from unravel.core.help_formatter import SuppressMetavar, SM, CustomArgumentRich

    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    parser.add_argument('-e', '--example', help='Example argument', action=SM)
    args = parser.parse_args()

Note:
    - The `SuppressMetavar` class is designed to suppress metavar display and improve the formatting of epilog text.
    - The `SM` action ensures that metavar is consistently suppressed across different nargs configurations.
    - The `CustomArgumentRich` and `CustomHelpAction` provide enhanced help message handling, integrating 
      formatted docstrings and filtering out unwanted lines.
    - nargs='``+``' with action=SM: This combination causes issues when the terminal window is small. 
    - Use nargs='``*``' with action=SM if zero arguments are acceptable, or drop action=SM to avoid conflicts.
"""

import argparse
import re
from rich import print
from rich.console import Console
from rich.text import Text

class SuppressMetavar(argparse.HelpFormatter):
    def __init__(self, prog):
        super().__init__(prog, max_help_position=52)

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

class CustomHelpAction(argparse.Action):
    def __init__(self, option_strings, dest=argparse.SUPPRESS, default=argparse.SUPPRESS, help=None, docstring=None):
        self.docstring = docstring
        super().__init__(option_strings=option_strings, dest=dest, default=default, nargs=0, help=help)

    def __call__(self, parser, namespace, values, option_string=None):
        parser.print_help()
        parser.exit()

class RichArgumentParser(argparse.ArgumentParser):
    def __init__(self, *args, docstring=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.docstring = docstring
        # Automatically add the custom help action with the provided docstring
        self.add_argument('-h', '--help', action=CustomHelpAction, docstring=self.docstring)

    def print_help(self, file=None):
        # Print the __doc__ string if available
        if self.docstring:
            print(format_docstring_for_terminal(self.docstring))
        
        # Capture the help output
        help_output = self.format_help().strip()  # Strip extra newlines from the raw help output
        
        # Filter out unwanted lines
        filtered_output = self.filter_help_output(help_output)
        
        # Apply custom styling to the help text
        styled_help_text = format_argparse_help(filtered_output)
        
        # Print the styled help text
        console = Console()
        console.print(styled_help_text)  # No need to call .strip() on styled_help_text since it's a Text object

    def filter_help_output(self, help_output):
        lines = help_output.splitlines()
        
        # Filter out lines that start with 'usage:', 'options:', or contain '-h, --help'
        filtered_lines = [
            line for line in lines if not line.startswith('usage:') and '-h, --help' not in line and not line.startswith('options:')
        ]
        
        return '\n'.join(filtered_lines)

    def format_usage(self):
        # Override to suppress the usage line
        return ''
    
# Custom action class to suppress metavar across all nargs configurations
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

def format_argparse_help(help_text):
    """
    Apply rich formatting to the argparse help message.

    This function processes the help text generated by argparse and applies
    custom styles using the Rich library. It colors the flags according to the 
    section they belong to (e.g., purple3 for "Required arguments:").

    grey50 style is applied to lines containing "Default:" to make them less prominent.

    Parameters
    ----------
    help_text : str
        The help text generated by argparse.

    Returns
    -------
    Text
        A `rich.text.Text` object containing the formatted help text.
    """
    # Regex to find flags (like -i, --input)
    flag_pattern = r"(\s--[\w-]+|\s-\w+)"

    # Regex to identify lines with unwanted patterns
    unwanted_pattern = r"\[-\w+|\[-\w+"

    # Split the help text into lines
    lines = help_text.splitlines()

    # Initialize the final formatted text
    final_text = Text()

    current_style = None

    for line in lines:
        # Skip unwanted lines
        if re.search(unwanted_pattern, line):
            continue

        # Style "Required arguments:" with purple3
        if line.strip().startswith("Required arguments:"):
            current_style = "purple3"
            styled_line = Text(line, style="bold purple3")
        elif line.strip().startswith("Optional"):
            current_style = "bright_blue"
            styled_line = Text(line, style="bold bright_blue")
        elif line.strip().startswith("General"):
            current_style = "green"
            styled_line = Text(line, style="bold green")
        elif "Default:" in line:
            # Apply grey50 style to lines with "Default:"
            line = re.sub(flag_pattern, fr"[{current_style}]\1[/]", line)
            # Make "Default:" and the entire following text bold
            line = re.sub(r"(Default:\s*.*)", r"[bold]\1[/]", line)
            styled_line = Text.from_markup(line, style="grey50")
        else:
            # Apply the current style to the flags using regex
            if current_style:
                line = re.sub(flag_pattern, fr"[{current_style}]\1[/]", line)
            # Default styling for other lines
            styled_line = Text.from_markup(line)

        # Append the styled line to the final text
        final_text.append(styled_line)
        final_text.append("\n")

    return final_text

def format_docstring_for_terminal(docstring):
    """
    Apply rich formatting to a docstring for enhanced terminal display.

    This function processes a docstring by applying various formatting styles
    using the Rich library. It handles sections like script descriptions,
    usage examples, command arguments, and specific keywords like "Input:",
    "Output", "Note", "Prereq", and "Next". Additionally, it applies
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
    - Script description lines are styled as bold.
    - Section headers starting with "Prereq", "Input", "Output", "Note", "Next", and "Usage" are colored.
    - Command names enclosed in double backticks or appearing in usage examples are styled as bold bright magenta.
    - Required arguments (before the first optional argument) are styled as purple3.
    - Optional arguments (within square brackets) are styled as bright blue.
    - Required command-line flags (e.g., `-m`, `--input`) are styled as bold in the required arg section.
    - General arguments like `[-d list of paths]`, `[-p sample??]`, and `[-v]` in the Usage section are styled as green.
    - The Usage section should be last and is separated by a horizontal line.
    """

    # Replace ``*`` or `*` with a plain asterisk *
    docstring = re.sub(r'``\*``', '*', docstring)
    docstring = re.sub(r'`\*`', '*', docstring)

    # Replace <asterisk> with a plain asterisk *
    docstring = docstring.replace('<asterisk>', '*')

    def apply_section_style(line):
        """Apply the appropriate style based on the section header."""
        if line.strip().startswith("Prereqs:"):
            return Text(line, style="red")
        elif line.strip().startswith("Input"):
            return Text(line, style="dark_orange")
        elif line.strip().startswith("Output"):
            return Text(line, style="gold1")
        elif line.strip().startswith("Note"):
            return Text(line, style="green")
        elif line.strip().startswith("Next"):
            return Text(line, style="grey50")
        elif line.strip().startswith("Usage"):
            return Text(line, style="bold cyan")
        return Text(line)  # Return the line as is if no match is found

    # Regex to find text enclosed in double backticks, excluding cases like ``*``
    command_pattern = r"``(?!\*)(.*?)``"
    
    # Regex to find flags (like -m, --input, -abc)
    flag_pattern = r"(\s-\w[\w-]*|\s--\w[\w-]*)"

    # Regex to find general arguments in usage
    general_arg_pattern = r"(\[-d list of paths\]|\[-p sample\?\?\]|\[-v\])"

    # Prepare the final formatted text
    final_text = Text()

    # Split the docstring into lines for processing
    lines = docstring.splitlines()

    # Extract the first command in the docstring
    command = None
    for line in lines:
        match = re.search(command_pattern, line)
        if match:
            command = match.group(1)  # group(1) contains the text inside the backticks
            break

    # Flags to manage the sections
    in_description = True
    separator_added = False
    processing_usage = False

    for line in lines:
        # Skip lines that start with "---"
        if line.strip().startswith("---"):
            continue

        if in_description:
            # Style "UNRAVEL" with custom formatting in the description
            line = re.sub(command_pattern, r"[bold bright_magenta]\1[/]", line)
            line = line.replace("UNRAVEL", "[red1]U[/][dark_orange]N[/][gold1]R[/][green]A[/][bright_blue]V[/][purple3]E[/][bright_magenta]L[/]")

            # Apply bold style to the script description lines
            styled_line = Text.from_markup(line, style="bold")

            # Check if this line is the start of a section
            if line.strip().startswith(("Usage", "Input", "Output", "Note", "Prereq", "Next")):
                in_description = False
                # Process the section header
                styled_line = apply_section_style(line)
                if line.strip().startswith("Usage"):
                    processing_usage = True
                    if not separator_added:
                        # Add a separator line before the first Usage section
                        console_width = Console().size.width
                        separator = Text("─" * console_width, style="dim")
                        final_text.append(separator)
                        final_text.append("\n\n")
                        separator_added = True

        else:
            # Apply section styles to headers
            if line.strip().startswith(("Input", "Output", "Note", "Prereq", "Next")):
                styled_line = apply_section_style(line)
            elif line.strip().startswith("Usage"):
                processing_usage = True
                styled_line = apply_section_style(line)
                if not separator_added:
                    # Add a separator line before the first Usage section
                    console_width = Console().size.width
                    separator = Text("─" * console_width, style="dim")
                    final_text.append(separator)
                    final_text.append("\n\n")
                    separator_added = True
            elif processing_usage:
                # We're in a Usage section and processing subsequent lines

                # Ensure the command name is styled correctly at the start of the line
                line = line.replace(f"  {command}", f"[bold bright_magenta]{command}[/]")

                # Identify the start of optional arguments
                tuple_parts = re.split(r'(\s\[-\w|\s\[--\w)', line, 1)
                if len(tuple_parts) == 3:
                    required_part, optional_start, optional_part = tuple_parts
                    required_part = required_part.strip()
                    optional_part = (optional_start + optional_part).strip()
                else:
                    required_part = line.strip()
                    optional_part = ""

                # Style the flags as bold
                required_part = re.sub(flag_pattern, r"[bold]\1[/]", required_part)
                optional_part = re.sub(flag_pattern, r"[bold]\1[/]", optional_part)

                # Split the optional part into general arguments and others
                general_args = re.findall(general_arg_pattern, optional_part)
                non_general_args = re.sub(general_arg_pattern, '', optional_part).strip()

                # Style the required arguments (before the bracket) as purple3
                styled_required = Text.from_markup(f"[purple3]{required_part}[/]") if required_part else Text()

                # Style the non-general optional arguments as bright_blue
                styled_optional = Text.from_markup(f"[bright_blue]{non_general_args}[/]") if non_general_args else Text()

                # Style the general arguments as green
                styled_general = Text()
                for arg in general_args:
                    styled_general.append(Text.from_markup(f"[green]{arg}[/] "))
                styled_general.rstrip()  # Remove the trailing space

                # Combine the styled parts together
                styled_line = Text()
                styled_line.append(styled_required)
                if styled_optional:
                    styled_line.append(" ")
                    styled_line.append(styled_optional)
                if styled_general:
                    styled_line.append(" ")
                    styled_line.append(styled_general)
            else:
                # Apply command formatting within the section
                line = re.sub(command_pattern, r"[bold bright_magenta]\1[/]", line)
                styled_line = Text.from_markup(line)

        # Add the processed line to the final text
        final_text.append(styled_line)
        final_text.append("\n")

    return final_text
