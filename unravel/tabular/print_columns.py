#!/usr/bin/env python3

"""
Use ``tabular_print_columns`` (``print_cols``) from UNRAVEL to load a CSV and print the column(s).

Usage:
------
    tabular_print_columns --input path/input.csv [-one-per-line] [-v]
"""

import pandas as pd
from rich import print
from rich.traceback import install

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.config import Configuration 
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg
from unravel.tabular.utils import load_tabular_file


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-i', '--input', required=True, help='Path to the input CSV file.', action=SM)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-o', '--one-per-line', help='Print each column name on a separate line.', action='store_true', default=False)
    opts.add_argument('-d', '--delimiter', help='Delimiter used in the CSV file. Default: ", "', default=', ')


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
    df, _ = load_tabular_file(args.input)

    # Print column names
    if args.one_per_line:
        for col in df.columns:
            print(f'[default]{col}')
    else:
        print("Columns in the CSV file:")
        print(f"[default]{args.delimiter}".join(df.columns))

    verbose_end_msg()


if __name__ == '__main__':
    main()
