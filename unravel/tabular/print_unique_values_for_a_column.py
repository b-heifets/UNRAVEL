#!/usr/bin/env python3

"""
Process a CSV file and print unique values for specified column(s) with optional keyword filtering.

Usage:
------
    ./csv_unique_values.py --input path/input.csv --column column_name [--keyword keyword] [-v]
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
    reqs.add_argument('-i', '--input', required=True, help='Path to the input CSV file.')
    reqs.add_argument('-c', '--column', required=True, nargs='*', help='Column name(s) to process (space-separated for multiple).')
    reqs.add_argument('-k', '--keyword', help='Keyword to filter unique values (optional).')

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()

# TODO: Note in Allen docs that this can be useful for checking unique values in large CSV files (e.g., 'region_of_interest_acronym' for scRNA-seq data).

@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    # Load the CSV file
    try:
        data = pd.read_csv(args.input)
    except Exception as e:
        print(f"Error reading CSV file: {e}")
        return

    for column in args.column:
        if column not in data.columns:
            print(f"Column '{column}' not found in the CSV file.")
            continue

        # Get unique values
        unique_values = data[column].dropna().unique()

        # Filter unique values by keyword if provided
        if args.keyword:
            keyword = args.keyword.lower()
            filtered_values = [value for value in unique_values if keyword in str(value).lower()]
            print(f"Filtered unique values in column '{column}' (matching '{args.keyword}'):")
            for value in filtered_values:
                print(f"  {value}")
        else:
            print(f"Unique values in column '{column}':")
            for value in unique_values:
                print(f"  {value}")


    verbose_end_msg()


if __name__ == '__main__':
    main()
