#!/usr/bin/env python3

"""
This removes or keeps specified columns in a CSV or XLSX file.

Usage:
------
    filter_columns.py -i "path/to/data/*.csv" [-d col1 col2 ... or -k col3 col4 ...] [-o output_file.csv] [-v]

"""

import glob
import pandas as pd
from pathlib import Path
from rich import print
from rich.traceback import install

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.config import Configuration
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg

def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-i', '--input', help="Glob pattern to match CSV or XLSX files", required=True, action=SM)


    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-d', '--drop_cols', help="Columns to drop (use -d or -k)", nargs='*', action=SM)
    opts.add_argument('-k', '--keep_cols', help="Columns to keep (drops all others)", nargs='*', action=SM)
    opts.add_argument('-o', '--output', help="Output file path/name. Default: <input>_cols_filtered.csv", default=None, action=SM)
    opts.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()

# TODO: add to the main repo

def filter_columns(file_path, drop_cols, keep_cols, output_path=None):
    """
    Load a CSV or XLSX file, process columns (drop/keep), and save the modified file.

    Parameters:
    -----------
    file_path : str
        Path to the input file (CSV or XLSX).
    
    drop_cols : list or None
        List of column names to drop.

    keep_cols : list or None
        List of column names to keep (all others will be dropped).

    output_path : str or None
        Path to save the processed file. If None, saves in the same directory with "_cols_filtered" suffix.
    """
    # Determine file extension and read the file accordingly
    if file_path.lower().endswith('.csv'):
        df = pd.read_csv(file_path)
        file_extension = ".csv"
    elif file_path.lower().endswith(('.xls', '.xlsx')):
        df = pd.read_excel(file_path)
        file_extension = ".xlsx"
    else:
        print(f"[bold red]Unsupported file format: {file_path}[/bold red]")
        return

    existing_columns = df.columns.tolist()

    # Drop specified columns
    if drop_cols:
        drop_cols = [col for col in drop_cols if col in existing_columns]
        if drop_cols:
            df.drop(columns=drop_cols, inplace=True)
        else:
            print(f"[yellow]No matching columns found in {file_path}. Skipping...[/yellow]")

    # Keep only specified columns
    if keep_cols:
        keep_cols = [col for col in keep_cols if col in existing_columns]
        if keep_cols:
            df = df[keep_cols]
        else:
            print(f"[yellow]No matching columns found in {file_path}. Skipping...[/yellow]")

    # Input file extension check
    if file_extension not in [".csv", ".xlsx"]:
        print(f"[bold red]Unsupported file format: {file_extension}[/bold red]")
        return

    # Save the processed dataframe
    if output_path is None:
        output_path = Path(file_path).parent / f"{Path(file_path).stem}_cols_filtered{file_extension}"
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if file_extension == ".csv":
        df.to_csv(output_path, index=False)
    else:
        df.to_excel(output_path, index=False)

    print(f"[green]Filtered data saved to: {output_path}[/green]")

@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    # Check that -d or -k is provided and not both
    if not args.drop_cols and not args.keep_cols:
        print("[bold red]You must specify either -d (drop columns) or -k (keep columns).[/bold red]")
        return
    if args.drop_cols and args.keep_cols:
        print("[bold red]You cannot specify both -d (drop columns) and -k (keep columns). Please choose one.[/bold red]")
        return

    for file_path in glob.glob(args.input):

        # Skip temporary files that start with ~
        if Path(file_path).name.startswith("~"):
            continue
        
        filter_columns(file_path, args.drop_cols, args.keep_cols, args.output)

    verbose_end_msg()

if __name__ == '__main__':
    main()
