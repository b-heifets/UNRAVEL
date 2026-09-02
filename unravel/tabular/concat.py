#!/usr/bin/env python3

"""
Use ``tabular_concat`` (``concat``) from UNRAVEL to load a CSV file and concatenate multiple CSV files into a single table.

Usage:
------
    tabular_concat --input path/input1.csv path/input2.csv [...] [-a 0|1] [-o path/output.csv] [-v]

Usage in zsh to pass in files in order (e.g., prefix_1.csv, prefix_3.csv, prefix_2.csv):
----------------------------------------------------------------------------------------
    `array=(1 3 2) ; inputs=(${^array/#/prefix_}.csv) ; tabular_concat -i $inputs [-a 0|1] [-o path/output.csv] [-v]`
"""

from pathlib import Path
import pandas as pd
from rich import print
from rich.traceback import install

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.config import Configuration 
from unravel.core.utils import log_command, match_files, verbose_start_msg, verbose_end_msg


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-i', '--input', help='Path(s) or glob pattern(s) to the input CSV.', required=True, nargs='*', action=SM)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-a', '--axis', help='Axis to concatenate along: 0 for rows, 1 for columns. Default: 1', type=int, choices=[0, 1], default=1)
    opts.add_argument('-o', '--output', help='Path to output CSV file.', default=None, action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()


def concat_csvs(input_patterns, axis=1, output=None, verbose=False):
    """
    Load multiple CSV files, concatenate them along the specified axis, and save the result.

    Parameters:
    -----------
    input_patterns : list of str
        List of file paths or glob patterns for input CSV files.
    axis : int
        Axis to concatenate along: 0 for rows (vertical), 1 for columns (horizontal).
    output : str or None
        Path to the output CSV file.
    verbose : bool
        If True, prints additional information during processing.
    """
    paths = match_files(input_patterns)

    if verbose:
        print(f"\nInput CSV file paths: {paths}\n")

    # Load and concatenate the CSV files.
    if axis == 1:
        dfs = [pd.read_csv(path, index_col=0) for path in paths]
        df_concat = pd.concat(dfs, axis=1)
    else:
        dfs = [pd.read_csv(path) for path in paths]
        df_concat = pd.concat(dfs, axis=0, ignore_index=True)

    # Save the concatenated DataFrame.
    output_path = Path(output) if output else Path("concatenated_output.csv")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    df_concat.to_csv(
        output_path,
        index=(axis == 1),
    )

    if verbose:
        print(f"\nConcatenated DataFrame: {df_concat}\n")

    # Save the concatenated DataFrame
    output_path = Path(output) if output else Path('concatenated_output.csv')
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df_concat.to_csv(output_path, index=True)


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    concat_csvs(input_patterns=args.input, axis=args.axis, output=args.output, verbose=args.verbose)

    verbose_end_msg()


if __name__ == '__main__':
    main()
