#!/usr/bin/env python3

"""
Use ``cluster_group_data`` from UNRAVEL to organize bilateral csv outputs from ``cluster_validation``

Run this command in the target_dir from ``cluster_org_data``
        
Usage
-----
    cluster_group_data

It consolidates CSV files into pooled directories based on hemisphere.

Folder naming convention: 
    - <cluster_validation_dir>_LH for left hemisphere files
    - <cluster_validation_dir>_RH for right hemisphere files

For example, if the command is run in a directory containing the following directories:
    - cluster_valid_results_1_LH
    - cluster_valid_results_1_RH
    - cluster_valid_results_2_LH
    - cluster_valid_results_2_RH

The command will create a new directory for each cluster and move the corresponding left and right hemisphere files into it. 
The original directories will be removed.

The resulting directory structure will be:
    - cluster_valid_results_1
    - cluster_valid_results_2
"""

import argparse
import shutil
from pathlib import Path
from rich.traceback import install

from unravel.core.argparse_utils import SuppressMetavar
from unravel.core.config import Configuration
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg, print_func_name_args_times


def parse_args():
    parser = argparse.ArgumentParser(formatter_class=SuppressMetavar)
    parser.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)
    parser.epilog = __doc__
    return parser.parse_args()

@print_func_name_args_times()
def group_hemisphere_data(base_path):

    # Collect all relevant directories
    base_path = Path(base_path)
    dirs = [d for d in base_path.iterdir() if d.is_dir()]

    # Separate left and right hemisphere directories into dictionaries 
    # (key: common basename, value: side-specific directory path)
    lh_dirs_dict = {d.name[:-3]: d for d in dirs if d.name.endswith('_LH')}
    rh_dirs_dict = {d.name[:-3]: d for d in dirs if d.name.endswith('_RH')}

    # Process matching pairs
    for common_name, lh_dir in lh_dirs_dict.items():
        rh_dir = rh_dirs_dict.get(common_name) # Check if there is a matching RH dir
        if rh_dir:  # Only proceed if both left and right directories exist
            new_dir_path = base_path / common_name
            new_dir_path.mkdir(exist_ok=True)

            # Move files from left hemisphere directory to new directory
            for file in lh_dir.iterdir():
                dest_file = Path(new_dir_path, file.name)
                if not dest_file.exists():
                    shutil.move(str(file), dest_file)
            
            # Move files from right hemisphere directory to new directory
            for file in rh_dir.iterdir():
                dest_file = Path(new_dir_path, file.name)
                if not dest_file.exists():
                    shutil.move(str(file), dest_file)
            
            # Remove the original directories
            shutil.rmtree(lh_dir)
            shutil.rmtree(rh_dir)

@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    base_path = Path.cwd()

    has_hemisphere = False
    for subdir in [d for d in Path.cwd().iterdir() if d.is_dir()]:
        if str(subdir).endswith('_LH') or str(subdir).endswith('_RH'):
            has_hemisphere = True

    if has_hemisphere: 
        group_hemisphere_data(base_path)

    verbose_end_msg()


if __name__ == '__main__':
    main()