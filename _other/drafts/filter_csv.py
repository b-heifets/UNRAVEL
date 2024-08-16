#!/usr/bin/env python3


import argparse
import glob
import pandas as pd
from pathlib import Path
from rich import print
from rich.traceback import install

from unravel.core.argparse_utils import SuppressMetavar, SM
from unravel.core.config import Configuration
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg


def parse_args():
    parser = argparse.ArgumentParser(formatter_class=SuppressMetavar)
    parser.add_argument('-g', '--glob_pattern', help="Glob pattern to match CSV files", required=True, action=SM)
    parser.add_argument('-col', '--column', help="Column to filter", required=True, action=SM)
    parser.add_argument('-vals', '--values', nargs='*', help="Values to filter by", required=True, action=SM)
    parser.add_argument('-od', '--output_dir', help="Directory to save filtered CSVs", default="filtered_csvs", action=SM)
    parser.add_argument('-v', '--verbose', help='Increase verbosity.', action='store_true', default=False)
    parser.epilog = __doc__
    return parser.parse_args()


def filter_csv(file_path, column, values, output_dir):
    """
    Filter a CSV file based on column values and save the filtered CSV to an output directory.

    Parameters:
    -----------
    file_path : str
        Path to the input CSV file.
    
    column : str
        Column name to filter by.

    values : list
        List of values to filter by.

    output_dir : str
        Path to the output directory to save the filtered CSV.
    """
    df = pd.read_csv(file_path)
    
    # Filter the dataframe based on the column and values
    filtered_df = df[df[column].isin(values)]
    
    # Save the filtered dataframe to the output directory
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / str(Path(file_path).name).replace(".csv", "_filtered.csv")
    filtered_df.to_csv(output_path, index=False)


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    for file_path in glob.glob(args.glob_pattern):
        filter_csv(file_path, args.column, args.values, args.output_dir)

    verbose_end_msg()
    

if __name__ == '__main__':
    main()