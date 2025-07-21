#!/usr/bin/env python3

"""
Use ``tabular_print_unique_values`` or ``print_unique`` from UNRAVEL to print unique values in specified column(s) of a CSV file.

Usage:
------
    tabular_print_unique_values -i input.csv -c column1 column2 [-k keyword1 keyword2 ...] [--exact] [-v]
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
    reqs.add_argument('-i', '--input', help='Path to the input CSV file.', required=True, action=SM)
    reqs.add_argument('-c', '--column', help='Column name(s) to process (space-separated for multiple).', required=True, nargs='*', action=SM)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-n', '--count', help='Print the count for each unique value.', action='store_true', default=False)
    opts.add_argument('-k', '--keyword', help='Keyword(s) to filter unique values. For partial match use "gene", for exact match use --exact.', nargs='*', default=None, action=SM)
    opts.add_argument('-e', '--exact', help='Use exact match instead of partial substring match.', action='store_true', default=False)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()

# TODO: Note in Allen docs that this can be useful for checking unique values in large CSV files (e.g., 'region_of_interest_acronym' for scRNA-seq data).
# TODO: Also add percentage for each value if count is enabled. A table would be cleaner. 
# TODO: Add option to print unique values as a space-separated list for easy copy-pasting to other tools.

def filter_values(values, keywords, exact):
    if not keywords:
        return values
    filtered = []

    for val in values:
        val_str = str(val).lower()
        if any((val_str == kw.lower() if exact else kw.lower() in val_str) for kw in keywords):
            filtered.append(val)

    return filtered

def print_values(column, values, keywords=None, value_counts=None, show_count=False):
    count = len(values)
    plural = "value" if count == 1 else "values"

    if keywords:
        print(f"\nFiltered {count} unique {plural} in column '{column}' (matching {keywords}):")
    else:
        print(f"\nUnique {count} {plural} in column '{column}':")

    for val in values:
        if show_count and value_counts is not None:
            print(f"  [cyan]{val}[/cyan]: {value_counts[val]}")
        else:
            print(f"  [cyan]{val}[/cyan]")


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    df, _ = load_tabular_file(args.input)

    missing = [col for col in args.column if col not in df.columns]
    if missing:
        print(f"[bold yellow]Warning:[/bold yellow] Column(s) not found in CSV: {missing}")

    valid_columns = [col for col in args.column if col in df.columns]
    if not valid_columns:
        print("No valid columns found in the CSV file.")
        return

    for column in valid_columns:
        col_series = df[column].dropna()
        value_counts = col_series.value_counts()
        unique_values = sorted(df[column].dropna().unique(), key=lambda x: str(x).lower())

        if not unique_values:
            print(f"[dim]No matching values found in column '{column}'.[/dim]")
            continue

        filtered_values = filter_values(unique_values, args.keyword, args.exact)
        filtered_value_counts = value_counts[filtered_values] if args.count else None

    print_values(column, filtered_values, keywords=args.keyword, value_counts=filtered_value_counts, show_count=args.count)

    verbose_end_msg()


if __name__ == '__main__':
    main()
