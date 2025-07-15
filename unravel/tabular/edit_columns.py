#!/usr/bin/env python3

"""
Use ``tabular_edit_columns`` (``edit_cols``) from UNRAVEL to drop, keep, rename, or reorder columns in a CSV or XLSX file.

Usage:
------
    tabular_edit_columns -i "path/to/data/*.csv" [-d col1 col2 ... or -c col2 col1 ...] [--rename OLD=NEW ...] [-o output_dir/] [-v]
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
    reqs.add_argument('-i', '--input', help="One or more CSV/XLSX file paths or glob patterns (space-separated), e.g., 'data/*.csv'", required=True, nargs='*', action=SM)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-d', '--drop_cols', help="Columns to drop (use either -d or -c, not both)", nargs='*', action=SM)
    opts.add_argument('-c', '--cols',  help="Keep and reorder columns.", nargs='*', action=SM)
    opts.add_argument('-r', '--rename', help="Rename columns using OLD=NEW syntax.", nargs='*', action=SM)
    opts.add_argument('-o', '--output', help="Output directory path. Default: edit_cols.", default=None, action=SM)
    opts.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()


def edit_columns(file_path, drop_cols, cols, rename=None, output_dir=None, verbose=False):
    """
    Load a CSV or XLSX file, process columns (drop/keep/reorder), and save the modified file.

    Parameters:
    -----------
    file_path : str
        Path to the input file (CSV or XLSX).
    
    drop_cols : list or None
        List of column names to drop.

    cols : list or None
        List of column names to keep and reorder (all others will be dropped).

    rename : list or None
        List of strings in the format OLD=NEW to rename columns.

    output_dir : str or None
        Path to the output directory. If None, saves in "edit_cols" directory next to the input file.

    verbose : bool
        If True, prints additional information during processing.
    """
    df, file_extension = load_tabular_file(file_path)

    existing_columns = df.columns.tolist()

    # Drop specified columns
    if drop_cols:
        drop_cols = [col for col in drop_cols if col in existing_columns]
        if drop_cols:
            df.drop(columns=drop_cols, inplace=True)
        else:
            print(f"[yellow]No matching columns found to drop in {file_path}. Skipping...")
            print(f"[dim]Available columns: {existing_columns}")
            return

    # Keep only specified columns
    if cols:
        missing = [col for col in cols if col not in df.columns]
        if missing:
            print(f"[yellow]Missing columns: {missing}. Skipping...")
            print(f"[dim]Available columns: {df.columns.tolist()}")
            return
        else:
            df = df[cols]

    # Rename columns if requested
    if rename is not None:
        rename_dict = {}
        for r in rename:
            if '=' in r:
                old, new = r.split('=', 1)
                if old in df.columns:
                    rename_dict[old] = new
        if rename_dict:
            df.rename(columns=rename_dict, inplace=True)
            if verbose:
                print(f"[dim]Renaming columns: {rename_dict}")
        else:
            print("[yellow]No valid columns to rename. Skipping...")

    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{Path(file_path).stem}_edit_cols{file_extension}"
    else:
        output_path = Path(file_path).parent / "edit_cols" / f"{Path(file_path).stem}_edit_cols{file_extension}"
        output_path.parent.mkdir(parents=True, exist_ok=True)

    save_tabular_file(df, output_path, index=False, verbose=verbose)

@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    # Check that -d or -k is provided and not both
    if not args.drop_cols and not args.cols:
        print("[bold red]You must specify at least one of -c (columns) or -d (drop columns).")
        return
    if args.drop_cols and args.cols:
        print("[bold red]You cannot specify both -d (drop columns) and -c (columns). Please choose one.")
        return

    file_paths = match_files(args.input)

    for file_path in file_paths:

        # Skip temporary files that start with ~
        if Path(file_path).name.startswith("~"):
            continue

        edit_columns(
            file_path=file_path,
            drop_cols=args.drop_cols,
            cols=args.cols,
            rename=args.rename,
            output_dir=Path(args.output) if args.output else None,
            verbose=args.verbose
        )

    verbose_end_msg()

if __name__ == '__main__':
    main()
