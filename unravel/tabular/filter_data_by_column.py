#!/usr/bin/env python3

"""
Use ``tabular_filter_rows`` or ``filter_rows`` from UNRAVEL to filter tabular data by values in a specified column.

Usage to keep rows where 'region' contains 'AUDp':
--------------------------------------------------
tabular_filter_rows -i data.csv -col region -p AUDp [--exact] [-o output_dir] [-v]

Usage to exclude rows where 'region' contains 'layer1':
-------------------------------------------------------
tabular_filter_rows -i data.csv -col region -p layer1 -f exclude [--exact] [-o output_dir] [-v]
"""

import pandas as pd
from pathlib import Path
from rich import print
from rich.traceback import install

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.config import Configuration
from unravel.core.utils import log_command, match_files, verbose_start_msg, verbose_end_msg
from unravel.tabular.utils import load_tabular_file, save_tabular_file

def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-i', '--input', help="One or more CSV/XLSX file paths or glob patterns (space-separated), e.g., 'data/*.csv'.", required=True, nargs='*', action=SM)
    reqs.add_argument('-col', '--column', help="Column to filter", required=True, action=SM)
    reqs.add_argument('-p', '--patterns', help="List of substring patterns to filter column values (use --exact for full-value matching).", nargs='*', required=True, action=SM)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-f', '--filter', help="Filtering mode ('include' to keep rows with specified values, exclude to remove them). Default: include", choices=['include', 'exclude'], default='include', action=SM)
    opts.add_argument('-e', '--exact', help="Use exact matching instead of substring matching.", action='store_true', default=False)
    opts.add_argument('-o', '--output', help="Directory to save filtered files. Default: filtered_files", default="filtered_files", action=SM)
    opts.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)
    return parser.parse_args()

def filter_table(df, column, patterns, mode='include', exact=False):
    """
    Filter a DataFrame based on a specific column and a list of values.

    Parameters:
    -----------
    df : pandas.DataFrame
        DataFrame containing the tabular data.
    column : str
        Column name to filter by.
    patterns : list
        List of values to filter by. If mode is 'include', rows with these values will be kept; if 'exclude', rows with these values will be removed.
    mode : str
        Filtering mode, either 'include' (default) to keep rows with specified values or 'exclude' to remove them.
    exact : bool
        If True, filter by exact matches of the values in the column. If False, filter by substring matches.

    Returns:
    --------
    pandas.DataFrame or None
        Filtered DataFrame if any rows match the criteria, otherwise None.
    """
    if column not in df.columns:
        print(f"[red]Column '{column}' not found in the DataFrame.")
        print(f"[dim]Available columns: {df.columns.tolist()}[/dim]")
        return None

    df[column] = df[column].astype(str)
    patterns = [str(p) for p in patterns]

    if exact:
        mask = df[column].isin(patterns)
    else:
        mask = df[column].apply(lambda x: any(p in x for p in patterns))

    if mode == 'exclude':
        mask = ~mask

    filtered_df = df[mask]
    return filtered_df if not filtered_df.empty else None


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    file_paths = match_files(args.input)
    for file_path in file_paths:

        # Skip temporary files that start with ~
        if Path(file_path).name.startswith("~"):
            continue
        
        df, file_extension = load_tabular_file(file_path)

        df_filtered = filter_table(df,
                                   column=args.column,
                                   patterns=args.patterns,
                                   mode=args.filter,
                                   exact=args.exact)

        if df_filtered is not None:
            output_dir = Path(args.output)
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / f"{Path(file_path).stem}_filtered{file_extension}"
            save_tabular_file(df_filtered, output_path, verbose=args.verbose)

    verbose_end_msg()

if __name__ == '__main__':
    main()
