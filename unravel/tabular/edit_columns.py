#!/usr/bin/env python3

"""
Use ``tabular_edit_columns`` (``edit_cols``) from UNRAVEL to drop, keep, rename, or reorder columns in a CSV or XLSX file.

Usage to DROP columns:
----------------------
    `tabular_edit_columns -i 'path/to/data/*.csv' [-d col1 col2 ...] [-o output_dir] [-v]`

Usage to REORDER columns:
-------------------------
    `tabular_edit_columns -i 'path/to/data/*.csv' -c col2 col1 col3 ... [-o output_dir] [-v]`

Usage to RENAME columns:
------------------------
    `tabular_edit_columns -i 'path/to/data/*.csv' --rename OLD=NEW ... [-o output_dir] [-v]`

Usage to REPLACE text in column names:
--------------------------------------
    `tabular_edit_columns -i 'path/to/data/*.csv' --replace OLD=NEW ... [-o output_dir] [-v]`
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
    opts.add_argument('-rp', '--replace', help="Replace text in column names using OLD=NEW syntax.", nargs='*', action=SM)
    opts.add_argument('-o', '--output', help="Output directory path for multiple inputs or output file path for single input.", default=None, action=SM)
    opts.add_argument('-I', '--inplace', help='Overwrite input file(s) instead of creating new output files.', action='store_true', default=False)
    
    opts.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()


def edit_columns(input_pattern, drop_cols, cols, rename=None, replace=None, output=None, inplace=False, verbose=False):
    """
    Load CSV/XLSX file(s), process columns, and save modified file(s).

    Supports:
      - drop columns with -d
      - keep/reorder columns with -c
      - rename columns with -r
      - overwrite inputs with --inplace/-I
      - write to output file/dir with -o

    Parameters:
    -----------
    input_pattern : str
        File path or glob pattern for input CSV/XLSX files.
    drop_cols : list or None
        List of column names to drop.
    cols : list or None
        List of column names to keep and reorder (all others will be dropped).
    rename : list or None
        List of strings in the format OLD=NEW to rename columns.
    output : str or None
        Path to the output file or directory.
    replace : list or None
        List of strings in the format OLD=NEW to replace text in column names.
    inplace : bool
        If True, overwrites the input file(s) instead of creating new output files. 
    verbose : bool
        If True, prints additional information during processing.
    """
    file_paths = match_files(input_pattern)

    for file_path in file_paths:

        # Skip temporary files that start with ~
        if Path(file_path).name.startswith("~"):
            continue

        df, file_extension = load_tabular_file(file_path)

        existing_columns = df.columns.tolist()

        # Drop specified columns
        if drop_cols:
            valid_drop_cols = [col for col in drop_cols if col in existing_columns]
            missing_drop_cols = [col for col in drop_cols if col not in existing_columns]

            if missing_drop_cols and verbose:
                print(f"[yellow]Columns not found in {file_path}: {missing_drop_cols}")

            if valid_drop_cols:
                df.drop(columns=valid_drop_cols, inplace=True)
            else:
                print(f"[yellow]No matching columns found to drop in {file_path}. Skipping...")
                print(f"[dim]Available columns: {existing_columns}")
                continue

        # Keep only specified columns
        if cols:
            missing = [col for col in cols if col not in df.columns]
            if missing:
                print(f"[yellow]Missing columns in {file_path}: {missing}. Skipping...")
                print(f"[dim]Available columns: {df.columns.tolist()}")
                continue

            df = df[cols]

        # Rename columns if requested
        if rename:
            rename_dict = {}

            for r in rename:
                if '=' not in r:
                    print(f"[yellow]Invalid rename syntax '{r}'. Expected OLD=NEW. Skipping...")
                    continue

                old, new = r.split('=', 1)

                if old in df.columns:
                    rename_dict[old] = new
                elif verbose:
                    print(f"[yellow]Column '{old}' not found in {file_path}. Skipping rename.")

            if rename_dict:
                df.rename(columns=rename_dict, inplace=True)

                if verbose:
                    print(f"[dim]Renaming columns in {file_path}: {rename_dict}")
            else:
                print(f"[yellow]No valid columns to rename in {file_path}. Skipping...")
                continue

        # Replace text in column names if requested
        if replace:
            replace_map = {}

            for r in replace:
                if '=' not in r:
                    print(f"[yellow]Invalid replace syntax '{r}'. Expected OLD=NEW. Skipping...")
                    continue

                old, new = r.split('=', 1)
                replace_map[old] = new

            if replace_map:
                new_columns = []
                changed = {}

                for col in df.columns:
                    new_col = col
                    for old, new in replace_map.items():
                        new_col = new_col.replace(old, new)

                    new_columns.append(new_col)

                    if new_col != col:
                        changed[col] = new_col

                df.columns = new_columns

                if verbose:
                    print(f"[dim]Replacing text in column names in {file_path}: {changed}")

        # Handle output path logic
        if inplace:
            output_path = Path(file_path)

        elif output is not None:
            output_path = Path(output)

            if len(file_paths) > 1:
                # Multiple inputs → treat output as directory
                output_path.mkdir(parents=True, exist_ok=True)
                output_path = output_path / f"{Path(file_path).stem}_edit_cols{file_extension}"
            else:
                # Single input → output can be a file path or existing directory
                if output_path.is_dir():
                    output_path = output_path / f"{Path(file_path).stem}_edit_cols{file_extension}"
                else:
                    output_path.parent.mkdir(parents=True, exist_ok=True)

        else:
            # No output specified
            if len(file_paths) > 1:
                output_path = Path(file_path).parent / "edit_cols" / f"{Path(file_path).stem}_edit_cols{file_extension}"
                output_path.parent.mkdir(parents=True, exist_ok=True)
            else:
                output_path = Path(file_path).parent / f"{Path(file_path).stem}_edit_cols{file_extension}"

        save_tabular_file(df, output_path, index=False, verbose=verbose)

@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    # -d and -c are mutually exclusive, but -r can be used alone.
    if args.drop_cols and args.cols:
        print("[bold red]You cannot specify both -d (drop columns) and -c (columns). Please choose one.")
        return

    if not args.drop_cols and not args.cols and not args.rename and not args.replace:
        print("[bold red]You must specify at least one operation: -c, -d, -r, or -rp.")
        return
    
    if args.inplace and args.output:
        print("[bold red]Cannot use --inplace together with -o/--output.")
        return

    edit_columns(
        input_pattern=args.input,
        drop_cols=args.drop_cols,
        cols=args.cols,
        rename=args.rename,
        output=args.output,
        inplace=args.inplace,
        replace=args.replace,
        verbose=args.verbose
    )

    verbose_end_msg()

if __name__ == '__main__':
    main()
