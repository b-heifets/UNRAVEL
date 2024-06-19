#!/usr/bin/env python3

"""
Use stats_table.py from UNRAVEL to recursively find and concatenate matching CSVs (e.g., to summarize cluster validation info).

Usage:
------
    path/stats_table.py -cp cluster_validation_info.csv -o cluster_validation_summary.csv
"""

import argparse
import pandas as pd
from pathlib import Path
from glob import glob
from rich.traceback import install

from unravel.core.argparse_utils import SuppressMetavar, SM


def parse_args():
    parser = argparse.ArgumentParser(formatter_class=SuppressMetavar)
    parser.add_argument('-cp', '--csv_pattern', help="Pattern to match csv files. Default: cluster_validation_results.csv", default='cluster_validation_info.csv', action=SM)
    parser.add_argument('-o', '--output', help='path/output.csv. Default: cluster_validation_summary.csv', default='cluster_validation_summary.csv', action=SM)
    parser.epilog = __doc__
    return parser.parse_args()

def cluster_summary(csv_pattern, output):
    # Use glob to find all matching CSV files recursively
    csv_files = glob(str(f'**/{csv_pattern}'), recursive=True)
    if not csv_files:
        print(f"No CSV files found matching the pattern {csv_pattern}.")
        return

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