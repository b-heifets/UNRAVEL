#!/usr/bin/env python3

"""
Use ``utils_toggle`` from UNRAVEL to inactivate/activate sample?? dirs (i.e., prepend/remove "_" from dir name).

Usage for toggling all sample?? dirs to active:
-----------------------------------------------
    utils_toggle -t -e <list_of_exp_dir_paths>
    
Usage for activating sample?? dirs for certain conditions:
----------------------------------------------------------
    utils_toggle -c <path/sample_key.csv> -a <Saline MDMA> -v -e <list_of_exp_dir_paths>

For conditions in the activate list, the command will remove the "_" from the sample?? dir name.
For conditions not in the activate list, the command will prepend "_" to the sample?? dir name.    

The sample_key.csv file should have the following format:
    dir_name,condition
    sample01,control
    sample02,treatment
"""    

import argparse
import pandas as pd
from glob import glob
from pathlib import Path
from rich import print
from rich.traceback import install

from unravel.core.argparse_utils import SuppressMetavar, SM
from unravel.core.config import Configuration
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg, get_samples


def parse_args():
    parser = argparse.ArgumentParser(formatter_class=SuppressMetavar)
    parser.add_argument('-e', '--exp_paths', help='List of experiment dir paths w/ sample?? dirs to process.', nargs='*', default=None, action=SM)
    parser.add_argument('-p', '--pattern', help='Pattern for sample?? dirs. Use cwd if no matches.', default='sample??', action=SM)
    parser.add_argument('-d', '--dirs', help='List of sample?? dir names or paths to dirs to process', nargs='*', default=None, action=SM)
    parser.add_argument('-t', '--toggle_all', help='Toggle all sample folders to active, ignoring condition checks.', action='store_true', default=False)
    parser.add_argument('-sk', '--sample_key', help='path/sample_key.csv w/ directory names and conditions', default=None, action=SM)
    parser.add_argument('-a', '--activate', help='Space separated list of conditions to enable processing for (must match sample_key.csv)', default=None, nargs='*', action=SM)
    parser.add_argument('-v', '--verbose', help='Increase verbosity.', action='store_true', default=False)
    parser.epilog = __doc__
    return parser.parse_args()


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    active_samples = get_samples(args.dirs, args.pattern, args.exp_paths)
    inactive_samples = get_samples(args.dirs, f'_{args.pattern}', args.exp_paths)
    samples = active_samples + inactive_samples
    
    for sample in samples:
        sample_path = Path(sample).resolve() if sample != Path.cwd().name else Path.cwd()
        stripped_sample_name = sample_path.name.lstrip('_')  # Strip leading underscore for accurate CSV matching
            
        # Get the condition for the current sample
        if args.sample_key is not None: 
            mapping_df = pd.read_csv(args.sample_key)
            condition_df = mapping_df[mapping_df['dir_name'] == stripped_sample_name]['condition']

        if args.toggle_all:
            new_name = sample_path.parent / stripped_sample_name
            print(f'{new_name=}')
            status = "Activated"
        else:
            if args.sample_key is not None:
                condition = condition_df.values[0]
                if condition in args.activate:
                    new_name = sample_path.parent / stripped_sample_name
                    status = "Activated"
                else:
                    new_name = sample_path.parent / f'_{stripped_sample_name}'
                    status = "Inactivated"

        sample_path.rename(new_name)

        if args.verbose: 
            if status == "Activated":
                print(f"  [green]{status}[/] [default bold]{stripped_sample_name}[/] ([default bold]{condition}[/]). New path: {new_name}")
            else: 
                print(f"[red1]{status}[/] [default bold]{stripped_sample_name}[/] ([default bold]{condition}[/]). New path: {new_name}")

    verbose_end_msg()


if __name__ == '__main__':
    main()