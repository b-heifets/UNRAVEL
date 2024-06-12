#!/usr/bin/env python3

"""
Prepend conditions to filenames based on a CSV key

Usage:
    prepend_conditions.py -sk <path/sample_key.csv> -f -r

This script renames files in the current directory based on the conditions specified in the CSV file.

The sample_key.csv should have two columns: 'dir_name' and 'condition'.
The script will prepend the 'condition' to the filenames matching the 'dir_name' prefix.

For example, if the CSV contains the following rows:
    dir_name,condition
    sample01,control
    sample02,treatment

Files will be renamed as follows:
    'sample01_file.csv' --> 'control_sample01_file.csv'
    'sample02_file.csv' --> 'treatment_sample02_file.csv'.

If needed, files and/or folders can be renamed with rename.py
""" 

import argparse
import pandas as pd
from glob import glob
from pathlib import Path
from rich.traceback import install

from unravel.core.argparse_utils import SuppressMetavar, SM
from unravel.core.config import Configuration
from unravel.core.utils import print_cmd_and_times, print_func_name_args_times


def parse_args():
    parser = argparse.ArgumentParser(formatter_class=SuppressMetavar)
    parser.add_argument('-sk', '--sample_key', help='path/sample_key.csv w/ directory names and conditions', required=True, action=SM)
    parser.add_argument('-f', '--file', help='Rename matching files', action='store_true', default=False)
    parser.add_argument('-d', '--dirs', help='Rename matching dirs', action='store_true', default=False)
    parser.add_argument('-r', '--recursive', help='Recursively rename files/dirs', action='store_true', default=False)
    parser.add_argument('-v', '--verbose', help='Increase verbosity.', action='store_true', default=False)
    parser.epilog = __doc__
    return parser.parse_args()


def rename_items(base_path, dir_name, condition, rename_files, rename_dirs, recursive):
    search_pattern = f'**/{dir_name}*' if recursive else f'{dir_name}*'    
    for item in base_path.glob(search_pattern):
        if item.is_file() and rename_files:
            new_name = item.parent / f'{condition}_{item.name}'
            item.rename(new_name)
        elif item.is_dir() and rename_dirs:
            new_name = item.parent / f'{condition}_{item.name}'
            item.rename(new_name)

@print_func_name_args_times()
def prepend_conditions(base_path, csv_file, rename_files, rename_dirs, recursive):
    mapping_df = pd.read_csv(csv_file)
    
    for index, row in mapping_df.iterrows():
        dir_name = row['dir_name']
        condition = row['condition']
        rename_items(base_path, dir_name, condition, rename_files, rename_dirs, recursive)


def main():
    args = parse_args()

    base_path = Path.cwd() 
    prepend_conditions(base_path, args.sample_key, args.file, args.dirs, args.recursive)


if __name__ == '__main__':
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    print_cmd_and_times(main)()
