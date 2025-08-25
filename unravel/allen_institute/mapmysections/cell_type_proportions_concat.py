#!/usr/bin/env python3

"""
Use ``abca_cell_type_proportions_concat`` or ``cell_types_concat`` from UNRAVEL to concatenate cell type proportions
across multiple filtered cell metadata files.

Prereqs:
    - Each file should contain a row of cell type proportions (e.g., output from ``abca_cell_type_proportions`` with --transpose).
    - The script aligns all cell type columns, fills in missing types with 0, and optionally recalculates proportions.

Features:
    - Aligns cell type columns across multiple input files, filling missing values with 0.
    - Keeps ``source_file`` as the first column for traceability.
    - Optionally filters to a specific list of desired cell types (columns) using a text file.
    - If filtering is applied, proportions are recalculated per row based on the remaining columns.

Note:
    - If no keep list is provided, all cell types present in the input files will be included in the output.
    - If --keep_list is provided, only those cell types will be retained, and proportions will be re-normalized per row (proportions will sum to 1).
    - This .txt file should contain a single column (no header) with one desired cell type (column name) per line, e.g. (don't include the indent/dash):
    - ABC.NN
    - Astro.TE.NN
    - L5.IT.CTX.Glut
    - Vip.Gaba

Outputs:
    - A single CSV file with concatenated and aligned cell type proportions (one row per input file).
    - By default, saved as concatenated_cell_type_proportions.csv in the current directory.

Usage:
------
    abca_cell_type_proportions_concat -i '<asterisk>.csv' [-o output_path] [--keep_list path/to/keep_list.txt] [-v]
"""

import pandas as pd
from pathlib import Path
from rich import print
from rich.traceback import install

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.config import Configuration 
from unravel.core.utils import log_command, match_files, verbose_start_msg, verbose_end_msg


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    opts = parser.add_argument_group('Optional args')
    opts.add_argument('-i', '--input', help='Glob pattern(s) for input CSV files (e.g., "*.csv").', nargs='*', action=SM)
    opts.add_argument('-o', '--output', help='Output path for the concatenated CSV file. Default: concatenated_cell_type_proportions.csv in the current directory.', default=None, action=SM)
    opts.add_argument('-k', '--keep_list', help='Optional path to a text file listing which cell types (columns) to keep. Default: keep_cell_type_columns.txt in the current directory.', default=None, action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    input_files = match_files(args.input)

    input_files = [f for f in input_files if f.name != 'concatenated_cell_type_proportions.csv']
    if not input_files:
        raise ValueError("No valid input files found after excluding concatenated_cell_type_proportions.csv.")

    # Load keep list if available
    keep_cols = None
    keep_cols_path = Path(args.keep_list) if args.keep_list else Path().cwd() / 'keep_cell_type_columns.txt'

    if keep_cols_path.exists():
        print(f"\n[bold yellow]Using keep list from:[/bold yellow] {keep_cols_path}")
        keep_cols = [line.strip() for line in keep_cols_path.read_text().splitlines() if line.strip()]

    file_dfs = []
    for file in input_files:
        if args.verbose:
            print(f'Loading file: {file}')
        
        try:
            df = pd.read_csv(file)
            empty = df.empty
        except pd.errors.EmptyDataError:
            empty = True

        if empty:
            print(f'File is empty: {file.name}')
            if keep_cols:
                df = pd.DataFrame([{col: 0 for col in keep_cols}])
            else:
                print(f"[red]Cannot infer columns for empty file {file.name} without keep_cell_type_columns.txt or prior data.[/red]")
                continue

        df['source_file'] = file.stem
        file_dfs.append(df)

    if not file_dfs:
        raise ValueError("No usable input files (non-empty or inferable).")

    # Concatenate all, align on columns, fill missing with 0
    concatenated_df = pd.concat(file_dfs, ignore_index=True).fillna(0)

    # Reorder columns: source_file first
    cols = [c for c in concatenated_df.columns if c != 'source_file']
    concatenated_df = concatenated_df[['source_file'] + sorted(cols)]

    # Filter and normalize
    if keep_cols:
        keep_set = set(keep_cols)
        all_present_cols = set(concatenated_df.columns) - {'source_file'}

        # Warn about extra columns
        extra_cols = all_present_cols - keep_set
        if extra_cols:
            print(f"[yellow]Dropping extra columns not in keep list:[/yellow] {sorted(extra_cols)}")

        # Warn about missing expected columns
        missing_cols = keep_set - all_present_cols
        if missing_cols:
            print(f"[yellow]The following expected columns are missing and will be filled with 0:[/yellow] {sorted(missing_cols)}")

        # Keep only the specified columns, plus 'source_file'
        all_cols = ['source_file'] + sorted(keep_cols)
        concatenated_df = concatenated_df.reindex(columns=all_cols, fill_value=0)

        # Recalculate row-wise proportions (excluding source_file)
        data_cols = [c for c in concatenated_df.columns if c != 'source_file']
        row_sums = concatenated_df[data_cols].sum(axis=1).replace({0: 1})
        concatenated_df[data_cols] = concatenated_df[data_cols].div(row_sums, axis=0)

    # Sort by source_file
    concatenated_df = concatenated_df.sort_values(by='source_file').reset_index(drop=True)

    print(f'\n[bold green]Concatenated DataFrame:[/bold green]')
    print(concatenated_df)

    print(f"\nFinal columns in output: {list(concatenated_df.columns)}")
    print(f"Number of columns: {len(concatenated_df.columns)}")

    # Save the output
    output_path = Path(args.output or 'concatenated_cell_type_proportions.csv')
    output_path.parent.mkdir(parents=True, exist_ok=True)
    concatenated_df.to_csv(output_path, index=False)

    print(f'\n[bold cyan]Saved output to:[/bold cyan] {output_path}\n')
    verbose_end_msg()


if __name__ == '__main__':
    main()
