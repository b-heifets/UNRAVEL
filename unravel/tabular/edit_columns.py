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


def edit_columns(data, drop_cols=None, cols=None, rename=None, output_dir=None, output_name=None, output_ext=None, verbose=False):
    """
    Edit columns from a CSV/XLSX file or an in-memory DataFrame.

    Parameters
    ----------
    data : str | Path | pd.DataFrame
        Path to the input file (CSV/XLSX) or a pandas DataFrame.
    drop_cols : list[str] | None
        Columns to drop.
    cols : list[str] | None
        Columns to keep (and reorder). All others are dropped.
    rename : list[str] | None
        Rename rules as 'OLD=NEW'.
    output_dir : Path | None
        Where to save the edited table. If `data` is a path and this is None,
        the file is saved under `<input_parent>/edit_cols/` (legacy behavior).
        If `data` is a DataFrame and this is None, nothing is written to disk.
    output_name : str | None
        Base filename (without extension) to use when saving (mainly for DataFrame input).
        Defaults to stem of the input file, or "df_edit_cols" for DataFrame input.
    output_ext : str | None
        File extension (including dot) to use when saving with DataFrame input (e.g., ".csv" or ".xlsx").
        Defaults to the source file's extension, or ".csv" for DataFrame input.
    verbose : bool
        Verbose logging.

    Returns
    -------
    pd.DataFrame | None
        The edited DataFrame. Returns None if the function exits early due to missing columns.
    """

    # --- Load data and set naming/extension context ---
    if isinstance(data, (str, Path)):
        input_path = Path(data)
        df, file_extension = load_tabular_file(input_path)
        base_name = input_path.stem
        ext = file_extension  # preserves .csv/.xlsx
        source_label = str(input_path)
    elif isinstance(data, pd.DataFrame):
        df = data.copy()
        base_name = output_name or "df_edit_cols"
        ext = output_ext or ".csv"
        source_label = "DataFrame"
    else:
        raise TypeError("`data` must be a file path or a pandas DataFrame.")

    existing_columns = df.columns.tolist()

    # --- Drop specified columns ---
    if drop_cols:
        to_drop = [c for c in drop_cols if c in existing_columns]
        if to_drop:
            df.drop(columns=to_drop, inplace=True)
            if verbose:
                print(f"[dim]Dropped columns from {source_label}: {to_drop}")
        else:
            print(f"[yellow]No matching columns found to drop in {source_label}. Skipping...")
            print(f"[dim]Available columns: {existing_columns}")
            return None

    # --- Keep only specified columns (and reorder) ---
    if cols:
        missing = [c for c in cols if c not in df.columns]
        if missing:
            print(f"[yellow]Missing columns in {source_label}: {missing}. Skipping...")
            print(f"[dim]Available columns: {df.columns.tolist()}")
            return None
        df = df[cols]
        if verbose:
            print(f"[dim]Kept/reordered columns: {cols}")

    # Rename columns if requested
    if rename:
        rename_dict = {}
        for rule in rename:
            if "=" in rule:
                old, new = rule.split("=", 1)
                if old in df.columns:
                    rename_dict[old] = new
        if rename_dict:
            df.rename(columns=rename_dict, inplace=True)
            if verbose:
                print(f"[dim]Renamed columns: {rename_dict}")
        else:
            if verbose:
                print("[yellow]No valid columns to rename. Skipping...")

    # --- Determine output path & save (if applicable) ---
    # If input was a path, always save.
    # If input was a DataFrame: only save if output_dir is provided.
    should_save = isinstance(data, (str, Path)) or (isinstance(data, pd.DataFrame) and output_dir is not None)

    if should_save:
        if output_dir is None:
            # legacy default: <input_parent>/edit_cols/
            output_dir = Path(data).parent / "edit_cols"  # type: ignore[arg-type]
        output_dir.mkdir(parents=True, exist_ok=True)

        # Use provided output_name if given, otherwise fall back to base_name
        final_name = (output_name or base_name) + "_edit_cols"
        output_path = output_dir / f"{final_name}{ext}"

        save_tabular_file(df, output_path, index=False, verbose=verbose)

    return df

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

        df = edit_columns(
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
