#!/usr/bin/env python3

"""
Load a CSV and print the column(s).

Usage:
------
    ./csv_columns.py --input path/input.csv [-v]
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

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()


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
    
    print(data.columns)

    verbose_end_msg()


if __name__ == '__main__':
    main()
