#!/usr/bin/env python3

"""
Use ``parquet_unique_values.py`` from UNRAVEL to group by a column from a Parquet file
and check for non-zero values in one or more specified columns.

Usage:
------
    parquet_unique_values.py -i path/to/file.parquet -g groupby_column -c column1 [column2 ...] [-k keyword] [-v]
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
    reqs.add_argument('-i', '--input', required=True, help='Path to the input Parquet file.', action=SM)
    reqs.add_argument('-g', '--groupby', required=True, help='Column name to group by (e.g., region name).', action=SM)
    reqs.add_argument('-c', '--columns', required=True, nargs='*', help='One or more value columns to check for non-zero values.', action=SM)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-k', '--keyword', help='Filter groupby column by keyword (e.g., region name contains this).', action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    columns_to_load = [args.groupby] + args.columns
    df = pd.read_parquet(args.input, engine="pyarrow", columns=columns_to_load)

    print(f'\n{df}\n')

    if args.keyword:
        df = df[df[args.groupby].str.contains(args.keyword, case=False, na=False)]

    print(f'\nGroupby column ({args.groupby}) filtered by keyword ({args.keyword}): \n{df}\n')

    grouped = df.groupby(args.groupby)

    print(f'\nGrouped df: {grouped}\n')

    for group_name, group_df in grouped:
        print(f'\n{group_name=}\n')
        print(f'\n{group_df=}\n')

    for group_name, group_df in grouped:
        has_nonzero = (group_df[args.columns] != 0).any().any()
        status = "[green]Non-zero found[/green]" if has_nonzero else "[red]All zero[/red]"
        print(f"[bold]{group_name}[/bold]: {status}")

        # if has non_zero, print values for the columns corresonding to the keyword
        if has_nonzero:
            for col in args.columns:
                nonzero_values = group_df[group_df[col] != 0][col].unique()
                print(f"  {col}: {nonzero_values}")

    verbose_end_msg()


if __name__ == '__main__':
    main()
