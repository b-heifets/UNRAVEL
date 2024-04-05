#!/usr/bin/env python3

import argparse
from pathlib import Path
import shutil
from rich.traceback import install

from argparse_utils import SuppressMetavar, SM
from unravel_utils import print_cmd_and_times

def parse_args():
    parser = argparse.ArgumentParser(description='Sort data based on conditions and directory names.', formatter_class=SuppressMetavar)
    parser.add_argument('-c', '--conditions', help='List of conditions. Files not matching these will be moved to a dir called <other_data>', nargs='+', required=True, action=SM)
    parser.add_argument('-t', '--target_dir', help='Name of the folder to move the files to. Default: other_data', default='other_data', action=SM)
    parser.epilog = """Example usage:     sort_files_by_condition.py -c control treatment

A file will be moved if: 
    - the prefix does not match any of the conditions.
    - or the prefix is not in the parent directory name (separator: '_').
"""

    return parser.parse_args()


def move_files_to_other(folder, other_data_path):
    prefix_set = set(folder.name.split('_'))
    for file in folder.iterdir():
        if file.is_file():
            file_prefix = file.stem.split('_')[0] 
            # Move file if prefix is not in conditions or not in parent directory name
            if file_prefix not in prefix_set or file_prefix not in args.conditions: 
                new_location = other_data_path / file.name
                shutil.move(str(file), str(new_location))

def process_folders(base_path, conditions, target_dir):
    for folder in base_path.iterdir():
        if folder.is_dir():
            other_data_path = folder / target_dir
            other_data_path.mkdir(exist_ok=True)
            move_files_to_other(folder, other_data_path)


def main():
    base_path = Path.cwd()
    process_folders(base_path, args.conditions, args.target_dir)


if __name__ == '__main__':
    install()
    args = parse_args()
    print_cmd_and_times(main)()