#!/usr/bin/env python3

"""
Use ``tabular_edit_rows`` (``edit_rows``) from UNRAVEL to drop or keep specific rows based on index values.

Usage:
------
    tabular_edit_rows -i 'path/to/data/*.csv' [-d row1 row2 ... | -k row1 row2 ...] [-o output_dir/] [-v]
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
    opts.add_argument('-d', '--drop', help="Row indices (index names) to drop.", nargs='*', action=SM)
    opts.add_argument('-k', '--keep', help="Row indices (index names) to keep. All others will be dropped.", nargs='*', action=SM)
    opts.add_argument('-o', '--output', help="Output directory path for multiple inputs or output file path for single input.", default=None, action=SM)
    opts.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()


def edit_rows(input_pattern, drop=None, keep=None, output=None, verbose=False):
    """Load a CSV/XLSX file, filter rows by index, and save the modified file."""
    file_paths = match_files(input_pattern)

    for file_path in file_paths:
        if Path(file_path).name.startswith("~"):
            continue

        df, file_extension = load_tabular_file(file_path)

        # Ensure we have a named index; if none, use the first column as index
        if df.index.name is None:
            df.set_index(df.columns[0], inplace=True)

        if keep:
            # Preserve order from --keep and support duplicate index labels
            order = [k for k in keep if k in df.index]
            if not order:
                print(f"[yellow]None of the requested rows found in {file_path}. Skipping...")
                continue
            # Concatenate slices in the order of `keep` (handles duplicates correctly)
            df = pd.concat([df.loc[df.index == k] for k in order], axis=0)

        elif drop:
            df = df[~df.index.isin(drop)]

        # Output logic (same as your columns script)
        if output is not None:
            output_path = Path(output)
            if len(file_paths) > 1:
                output_path.mkdir(parents=True, exist_ok=True)
                output_path = output_path / f"{Path(file_path).stem}_edit_rows{file_extension}"
            else:
                if output_path.is_dir():
                    output_path = output_path / f"{Path(file_path).stem}_edit_rows{file_extension}"
                else:
                    output_path.parent.mkdir(parents=True, exist_ok=True)
        else:
            if len(file_paths) > 1:
                output_path = Path(file_path).parent / "edit_rows" / f"{Path(file_path).stem}_edit_rows{file_extension}"
                output_path.parent.mkdir(parents=True, exist_ok=True)
            else:
                output_path = Path(file_path).parent / f"{Path(file_path).stem}_edit_rows{file_extension}"

        save_tabular_file(df, output_path, index=True, verbose=verbose)


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    if not args.drop and not args.keep:
        print("[bold red]You must specify either -k (keep rows) or -d (drop rows).")
        return
    if args.drop and args.keep:
        print("[bold red]You cannot specify both -d and -k. Please choose one.")
        return

    edit_rows(
        input_pattern=args.input,
        drop=args.drop,
        keep=args.keep,
        output=args.output,
        verbose=args.verbose
    )

    verbose_end_msg()


if __name__ == '__main__':
    main()
