#!/usr/bin/env python3

"""
Use ``utils_region_info`` or ``region`` from UNRAVEL to filter CCFv3-2020_regional_summary.csv by a string and print the results.

Note: 
    - Default csv: UNRAVEL/unravel/core/csvs/CCFv3-2020_regional_summary.csv
    - Alternatively, use CCFv3-2017_regional_summary.csv or path/CSV with: Region_ID, Region, Abbr, General_Region.

Usage:
------
    region -f <string> [-c <filter column>] [-s <sort column>] [-csv <csv_path>] [-e]
"""

from pathlib import Path
import pandas as pd
from rich import print
from rich.console import Console
from rich.table import Table
from rich.traceback import install

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-f', '--filter', help='Filter CCFv3-2020_regional_summary.csv with a string (e.g., ACB)', required=True, action=SM)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-c', '--column', help='Restrict filtering/sorting to this column (e.g., Region_ID, General_Region, Region, or Abbr).', default=None, action=SM)
    opts.add_argument('-e', '--exact', help='Use exact matching instead of contains matching.', action='store_true')
    opts.add_argument('-s', '--sort', help='Sort by column. Default: Same as -c', default=None, action=SM)
    opts.add_argument('-cs', '--case_sensitive', help='Enable case-sensitive filtering (default is case-insensitive)', action='store_true')
    opts.add_argument('-csv', '--csv_path', help='CSV name or path/name.csv. Default: CCFv3-2020_regional_summary.csv', default='CCFv3-2020_regional_summary.csv', action=SM)

    return parser.parse_args()

# TODO: Add hierarchical info (parent regions and abbreviations)

def normalize_text(series, case_sensitive=False):
    """Convert a Series to strings for robust matching, including numeric columns."""
    text = series.astype(str)
    return text if case_sensitive else text.str.lower()

def filter_region_summary(filter_str, column=None, sort_column=None, csv_path='CCFv3-2020_regional_summary.csv', case_sensitive=False, exact=False):
    # Load CSV file
    csv_path = Path(__file__).parent.parent / 'core' / 'csvs' / csv_path if csv_path in ['CCFv3-2020_regional_summary.csv', 'CCFv3-2017_regional_summary.csv'] else Path(csv_path)
    if not csv_path.exists():
        print(f"    [red1]Error: The specified CSV file does not exist: {csv_path}")
        return
    try:
        regional_summary = pd.read_csv(csv_path, usecols=['Region_ID', 'Region', 'Abbr', 'General_Region'])
    except ValueError as e:
        print(f"[red1]Error loading CSV file: {e}")
        return

    # Check if filter column exists
    if column and column not in regional_summary.columns:
        print(f"[red1]Error: Column '{column}' not found in CSV.")
        return

    filter_value = str(filter_str) if case_sensitive else str(filter_str).lower()

    if column:
        search_col = normalize_text(regional_summary[column], case_sensitive)

        if exact:
            mask = search_col == filter_value
        else:
            mask = search_col.str.contains(filter_value, na=False, regex=False)

        filtered = regional_summary[mask]

    else:
        search_df = regional_summary.astype(str)
        if not case_sensitive:
            search_df = search_df.apply(lambda col: col.str.lower())

        if exact:
            mask = search_df.eq(filter_value).any(axis=1)
        else:
            mask = search_df.apply(
                lambda row: row.str.contains(filter_value, na=False, regex=False).any(),
                axis=1,
            )

        filtered = regional_summary[mask]

    if sort_column:
        if sort_column not in regional_summary.columns:
            print(f"\n    [red1]Error: Sort column '{sort_column}' not found in CSV.\n")
            return
        filtered = filtered.sort_values(by=sort_column)
    elif column:
        filtered = filtered.sort_values(by=column)

    # Display filtered results in a table
    console = Console()

    if filtered.empty:
        match_type = "exact match" if exact else "filter"
        console.print(f"\n    [yellow]No results found for {match_type} '{filter_str}' in CSV {csv_path}.\n")
        return

    title = f"Region Summary - {len(filtered)} Result" if len(filtered) == 1 else f"Region Summary - {len(filtered)} Results"
    table = Table(title=title)
    table.add_column("Region_ID", style="magenta")
    table.add_column("General_Region", style="purple3")
    table.add_column("Region", style="cyan")
    table.add_column("Abbr", style="green")

    # Add rows to the table
    for _, row in filtered.iterrows():
        table.add_row(str(row['Region_ID']), row['General_Region'], row['Region'], row['Abbr'])

    print()
    console.print(table, justify='center')

def main():
    install()
    args = parse_args()

    filter_region_summary(args.filter, args.column, args.sort, args.csv_path, case_sensitive=args.case_sensitive, exact=args.exact)


if __name__ == '__main__':
    main()
