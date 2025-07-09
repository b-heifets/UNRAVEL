#!/usr/bin/env python3

"""
Use stats_table.py from UNRAVEL to recursively find and concatenate matching CSVs (e.g., to summarize cluster validation info).

Usage:
------
    path/stats_table.py -cp cluster_validation_info.csv -o cluster_validation_summary.csv
"""

import pandas as pd
from pathlib import Path
from rich.traceback import install

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.utils import match_files

def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-cp', '--csv_pattern', help="Pattern to match csv files. Default: cluster_validation_results.csv", default='cluster_validation_info.csv', action=SM)
    opts.add_argument('-o', '--output', help='path/output.csv. Default: cluster_validation_summary.csv', default='cluster_validation_summary.csv', action=SM)

    return parser.parse_args()

def cluster_summary(csv_pattern, output):
    """
    Recursively find and concatenate CSV files matching the given pattern, sort by the first two columns if they exist, and save the result to the specified output file.
    Parameters:
    -----------
    csv_pattern : str
        The pattern to match CSV files (e.g., 'cluster_validation_info.csv').
    output : str
        The output file path where the concatenated CSV will be saved (e.g., 'cluster_validation_summary.csv').
    """
    # Use glob to find all matching CSV files recursively
    csv_files = match_files(f'**/{csv_pattern}')

    # Read and concatenate all matching CSV files
    concatenated_df = pd.concat([pd.read_csv(f) for f in csv_files])

    # Sort by the first and second columns if they exist
    if len(concatenated_df.columns) >= 2:
        concatenated_df = concatenated_df.sort_values(by=[concatenated_df.columns[0], concatenated_df.columns[1]])

    # Save the concatenated CSV file
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    concatenated_df.to_csv(output, index=False)

def main():
    args = parse_args()

    cluster_summary(args.csv_pattern, args.output)


if __name__ == '__main__':
    install()
    main()