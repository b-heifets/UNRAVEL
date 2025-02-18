#!/usr/bin/env python3

"""
This script processes tabular data by either removing specified columns 
or keeping only specified columns and dropping all others.

Example use cases:
- Drop unnecessary metadata columns to reduce file size.
- Retain only essential columns from large datasets.

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

    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('-d', '--drop_cols', nargs='+', help="Columns to drop", action=SM)
    mode.add_argument('-k', '--keep_cols', nargs='+', help="Columns to keep (drops all others)", action=SM)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-od', '--output_dir', help="Directory to save processed files", default="processed_files", action=SM)
    opts.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()

# TODO complete __doc__ string and add to the main repo

def process_columns(file_path, drop_cols, keep_cols, output_dir):
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

    output_dir : str
        Path to the output directory to save the processed file.
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

    # Save the processed dataframe
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    suffix = "_filtered" if drop_cols else "_selected"
    output_path = output_dir / str(Path(file_path).stem + suffix + file_extension)
    
    if file_extension == ".csv":
        df.to_csv(output_path, index=False)
    else:
        df.to_excel(output_path, index=False)

    print(f"[green]Processed file saved to:[/green] {output_path}")

@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    for file_path in glob.glob(args.input):

        # Skip temporary files that start with ~
        if Path(file_path).name.startswith("~"):
            continue
        
        process_columns(file_path, args.drop_cols, args.keep_cols, args.output_dir)

    verbose_end_msg()

if __name__ == '__main__':
    main()
