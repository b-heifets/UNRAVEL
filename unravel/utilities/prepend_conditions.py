#!/usr/bin/env python3

"""
Use ``utils_prepend`` (``prepend``) from UNRAVEL to prepend conditions to filenames based on a CSV key.

Note:
    - This command renames files in the current directory based on the conditions specified in the CSV file.
    - The sample_key.csv should have two columns: 'dir_name' and 'condition'.
    - The command will prepend the 'condition' to the filenames matching the 'dir_name' prefix.
    - If needed, files and/or folders can be renamed with ``utils_rename``.

For example, if the CSV contains the following rows:
    dir_name,condition
    sample01,control
    sample02,treatment

Files will be renamed as follows:
    'sample01_file.csv' --> 'control_sample01_file.csv'
    'sample02_file.csv' --> 'treatment_sample02_file.csv'.

Next commands for voxel-wise stats: 
    - Check images in FSLeyes and run ``vstats`` to perform voxel-wise stats.

Usage for files:
----------------
    utils_prepend -sk <path/sample_key.csv> -f [--recursive] [-v]

Usage for directories:
----------------------
    utils_prepend -sk <path/sample_key.csv> -d [--recursive] [-v]
""" 

import pandas as pd
from glob import glob
from pathlib import Path
from rich.traceback import install

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM

from unravel.core.config import Configuration
from unravel.core.utils import log_command, match_files, verbose_start_msg, verbose_end_msg, print_func_name_args_times


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-sk', '--sample_key', help='path/sample_key.csv w/ directory names and conditions', required=True, action=SM)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-f', '--file', help='Rename matching files', action='store_true', default=False)
    opts.add_argument('-d', '--dirs', help='Rename matching dirs', action='store_true', default=False)
    opts.add_argument('-r', '--recursive', help='Recursively rename files/dirs', action='store_true', default=False)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()

# TODO: Add --input to specify glob pattern(s) for files to rename. Change default behavior to rename all matching files/dirs. Change -f and -d to enable selective renaming of files or directories.


def rename_items(base_path, dir_name, condition, rename_files, rename_dirs, recursive):
    search_pattern = f'**/{dir_name}*' if recursive else f'{dir_name}*'
    items = match_files(search_pattern, base_path)
    for item in items:
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


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    base_path = Path.cwd() 
    prepend_conditions(base_path, args.sample_key, args.file, args.dirs, args.recursive)

    verbose_end_msg()


if __name__ == '__main__':
    main()