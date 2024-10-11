#!/usr/bin/env python3

"""
Use ``_other/drafts/_other/key_value_to_excel.py`` from UNRAVEL to convert key-value structured text data into an Excel (.xlsx) file.

Input file format:
    - Format: <key><delimiter><value>
    - Example:
        cluster,1
        Pearson correlation,-0.1567
        p-value,0.2359
        cluster,2
        Pearson correlation,0.1376
        p-value,0.4449

Groups of key-value pairs, separated by blank lines, form rows in the output.

Output file format: 
    - An Excel file where each key becomes a column header, and each group forms a row.
    
Usage:
------
    _other/drafts/_other/key_value_to_excel.py -i path/input.txt [-o path/output.xlsx] [-d ,] [-v]
"""

import pandas as pd
from rich import print
from rich.traceback import install

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.config import Configuration 
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-i', '--input', help='Path to the input text file containing key-value data.', required=True, action=SM)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-o', '--output', help='Path to the output Excel file.', action=SM)
    opts.add_argument('-d', '--delimiter', help="Delimiter used in the key-value pairs (default: ',').", default=',', action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()


def parse_key_value_data(data, delimiter=","):
    """Parse structured key-value data.
    
    Parameters:
    -----------
    data : str
        The structured key-value data. 
    delimiter : str, optional
        The delimiter used to separate keys and values. Default is ','.

    Returns:
    --------
    pd.DataFrame organized as a table with keys as columns and groups of key-value pairs as rows.
    
    """
    rows = [line.split(delimiter) for line in data.strip().split("\n") if line]

    # Filter out lines that don't contain the delimiter
    valid_rows = [row for row in rows if len(row) == 2]

    # Remove leading and trailing spaces from keys and values
    valid_rows = [(key.strip(), value.strip()) for key, value in valid_rows]

    # Replace spaces in the key with underscores
    valid_rows = [(key.replace(" ", "_"), value) for key, value in valid_rows]

    # Get the unique keys and the first unique key
    unique_keys = [key for key, _ in valid_rows]
    first_unique_key = unique_keys[0] if unique_keys else None
    
    # Restructure the data for a DataFrame
    structured_data = []
    current_row = {}
    for key, value in valid_rows:
        # Check against the first_unique_key dynamically
        if key == first_unique_key and current_row:
            structured_data.append(current_row)  # Add the previous group's data
            current_row = {}  # Start a new group
        current_row[key] = value
    structured_data.append(current_row)  # Add the last group's data

    # Create a DataFrame and fill missing values with NaN
    df = pd.DataFrame(structured_data).fillna(value=pd.NA)

    return df


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    """Main function to convert key-value data to Excel."""
    # Read the input data
    with open(args.input, 'r') as file:
        data = file.read()

    # Parse the data
    df = parse_key_value_data(data, args.delimiter)

    # Save to Excel
    if args.output:
        output_file = args.output
    else:
        output_file = args.input.replace(".txt", ".xlsx")
    df.to_excel(output_file, index=False)
    print(f"\n    Data successfully saved to {output_file}\n")

    verbose_end_msg()

if __name__ == '__main__':
    main()