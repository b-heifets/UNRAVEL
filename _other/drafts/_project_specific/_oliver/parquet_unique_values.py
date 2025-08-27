#!/usr/bin/env python3

"""
Use ``parquet_unique_values.py`` from UNRAVEL to load a column from a parquet file and print the unique values.

Usage:
------
    parquet_unique_values -i path/to/parquet -c column_names [-k keyword] [-v]
"""

import numpy as np
import pandas as pd
from rich import print
from rich.traceback import install

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.config import Configuration
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-i', '--input', required=True, help='Path to the input parquet file.')
    reqs.add_argument('-c', '--columns', required=True, nargs='*', help='Column name(s) to process (space-separated for multiple).')
    reqs.add_argument('-k', '--keyword', help='Keyword to filter unique values (optional).')

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    df = pd.read_parquet(args.input, engine="pyarrow", columns=args.columns)

    for column in args.columns:
        if column not in df.columns:
            print(f"Column '{column}' not found in the CSV file.")

            print(f'\n{df.columns=}\n')
            continue

        # Get unique values
        unique_values = df[column].dropna().unique()

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