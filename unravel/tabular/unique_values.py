#!/usr/bin/env python3

"""
Use ``tabular_unique_values`` or ``uniq_vals`` from UNRAVEL to print unique values in specified column(s) of a CSV file.

Usage:
------
    tabular_unique_values -i input.csv -c column1 column2 [-k keyword1 keyword2 ...] [--exact] [-v]
"""

import pandas as pd
from rich import print
from rich.traceback import install
from rich.table import Table
from rich import box

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.config import Configuration
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg
from unravel.tabular.utils import load_tabular_file, save_tabular_file


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-i', '--input', help='Path to the input CSV file.', required=True, action=SM)
    reqs.add_argument('-c', '--column', help='Column name(s) to process (space-separated for multiple).', required=True, nargs='*', action=SM)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-n', '--count', help='Print the count for each unique value.', action='store_true', default=False)
    opts.add_argument('-k', '--keyword', help='Keyword(s) to filter unique values. For partial match use "gene", for exact match use --exact.', nargs='*', default=None, action=SM)
    opts.add_argument('-e', '--exact', help='Use exact match instead of partial substring match.', action='store_true', default=False)
    opts.add_argument('-o', '--output', help='Output file path to save the results. Default: None (prints to console).', default=None, action=SM)
    opts.add_argument('-s', '--space', help='Print unique values as a space-separated list for easy copy-pasting.', action='store_true', default=False)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()

# TODO: Note in Allen docs that this can be useful for checking unique values in large CSV files (e.g., 'region_of_interest_acronym' for scRNA-seq data).
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

def print_values(column, values, keywords=None, value_counts=None, show_count=False, space_mode=False):
    if space_mode:
        list_str = " ".join(str(v) for v in values)
        print(list_str)
        return list_str
    
    count = len(values)
    plural = "value" if count == 1 else "values"

    if keywords:
        print(f"\n Filtered {count} unique {plural} in column '{column}' (matching {keywords}):")
    else:
        print(f"\n Unique {count} {plural} in column '{column}':")

    if show_count and value_counts is not None:
        df_out = pd.DataFrame({
            'Value': values,
            'Count': [value_counts[val] for val in values],
        })
        total = df_out['Count'].sum()
        df_out['Percent'] = df_out['Count'] / total * 100
    else:
        df_out = pd.DataFrame({'Value': values})

    # Rich table display
    table = Table(title=None, box=box.SIMPLE)
    table.add_column("Value", style="green", no_wrap=True)
    if show_count and value_counts is not None:
        table.add_column("Count", justify="right", style="cyan")
        table.add_column("Percent", justify="right", style="magenta")

        for _, row in df_out.iterrows():
            table.add_row(str(row["Value"]), str(row["Count"]), f"{row['Percent']:.2f}%")
    else:
        for val in df_out['Value']:
            table.add_row(str(val))

    print(table)
    return df_out


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

        output_df_or_list = print_values(
            column,
            filtered_values,
            keywords=args.keyword,
            value_counts=filtered_value_counts,
            show_count=args.count,
            space_mode=args.space
        )

        if args.output and output_df_or_list is not None:
            if args.space:
                with open(args.output, 'w') as f:
                    f.write(output_df_or_list+ '\n')
                    if args.verbose:
                        print(f"\n[green]Data saved to: {args.output}[/green]")
            else:
                save_tabular_file(output_df_or_list, args.output, index=False, verbose=args.verbose)

    verbose_end_msg()


if __name__ == '__main__':
    main()
