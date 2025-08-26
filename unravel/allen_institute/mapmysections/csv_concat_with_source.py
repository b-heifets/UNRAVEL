#!/usr/bin/env python3

"""
Use ``mms_concat_with_source`` or ``cws`` from UNRAVEL to concatenate multiple CSV files, include a 'source_file' column, and sort rows by that column.

Prereqs:
    - ``mms_soma_ratio`` or ``mms_seg_summary``
    - Aggregate their outputs
    - For ``mms_seg_summary``, use ``agg`` to aggregate results across samples and cd to the target directory.

Note:
    - This command loads all matching CSV files.
    - It adds a 'source_file' column (file stem).
    - It handles empty files by filling rows with 0s for all expected columns.
    - It sorts all rows by 'source_file'.

Usage:
------
    csv_concat_with_source [-i '<asterisk>.csv'] [-o output.csv] [-v]
"""

import pandas as pd
from pathlib import Path
from rich import print
from rich.traceback import install

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.utils import log_command, match_files, verbose_start_msg, verbose_end_msg


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-i', '--input', help="Path(s) or glob pattern(s) for input CSV files. Default: '*.csv'", default='*.csv', nargs='*', action=SM)
    opts.add_argument('-o', '--output', help="Output CSV path. Default: concatenated_output.csv", default='concatenated_output.csv', action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Verbose output.', action='store_true')

    return parser.parse_args()


@log_command
def main():
    install()
    args = parse_args()
    verbose_start_msg()
    
    input_files = match_files(args.input)

    file_dfs = []
    all_columns = set()

    for file in sorted(input_files):
        if args.verbose:
            print(f'📂 Reading: {file}')

        try:
            df = pd.read_csv(file)
            empty = df.empty
        except pd.errors.EmptyDataError:
            empty = True

        if empty:
            print(f'[yellow]⚠️ Empty file detected:[/yellow] {file.name}')
            if not all_columns:
                print(f"[red]❌ Cannot infer columns for empty file before loading any non-empty file.[/red]")
                continue
            df = pd.DataFrame([{col: 0 for col in all_columns}])
        else:
            all_columns.update(df.columns)

        df['source_file'] = file.stem
        file_dfs.append(df)

    if not file_dfs:
        raise ValueError("No valid dataframes loaded.")

    df_concat = pd.concat(file_dfs, ignore_index=True).fillna(0)

    # Reorder: source_file first, then alphabetized rest
    cols = [c for c in df_concat.columns if c != 'source_file']
    df_concat = df_concat[['source_file'] + sorted(cols)]

    # Sort by source_file
    df_concat = df_concat.sort_values(by='source_file').reset_index(drop=True)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df_concat.to_csv(output_path, index=False)

    print(f'\n[bold green]✅ Saved concatenated CSV to:[/bold green] {output_path}\n')
    verbose_end_msg()


if __name__ == '__main__':
    main()
