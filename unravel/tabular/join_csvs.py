#!/usr/bin/env python3

"""
Use ``tabular_join_csvs`` (``join_csvs``) from UNRAVEL to load a CSV file and join using the first column as the index.

Note:
    - The first column in each CSV is treated as the index for joining.
    - The order of input files matters; later files will add columns to the right of earlier ones.
    - When there are overlapping column names (other than the index), suffixes _1, _2, etc. will be added to distinguish them.

Usage:
------
    tabular_join_csvs --input path/input1.csv path/input2.csv [...] [-v]

Usage in zsh to pass in files in order (e.g., prefix_1.csv, prefix_3.csv, prefix_2.csv):
----------------------------------------------------------------------------------------
    array=(1 3 2) ; inputs=(${^array/#/prefix_}.csv) ; tabular_join_csvs -i $inputs [-o path/output.csv] [-v]
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
    opts.add_argument('-o', '--output', help='Path to output CSV file.', default=None, action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    paths = match_files(args.input)
    print(f"\nInput CSV file paths: {paths}\n")

    # Load all CSV files into DataFrames
    dfs = [pd.read_csv(path, index_col=0) for path in paths]

    # Join the DataFrames on the index (first column)
    df1 = dfs[0]
    for i, df2 in enumerate(dfs[1:], start=1):
        df1 = df1.join(df2, how='left', lsuffix='', rsuffix=f'_{i}')

    print(f"\nJoined DataFrame: {df1}\n")

    # Save the joined DataFrame
    output_path = Path(args.output) if args.output else Path('joined_output.csv')
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df1.to_csv(output_path, index=True)

    verbose_end_msg()


if __name__ == '__main__':
    main()
