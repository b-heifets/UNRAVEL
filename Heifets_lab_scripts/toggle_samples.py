#!/usr/bin/env python3

import argparse
import pandas as pd
from glob import glob
from pathlib import Path
from rich import print
from rich.traceback import install

from argparse_utils import SuppressMetavar, SM
from unravel_config import Configuration
from unravel_utils import print_cmd_and_times, get_samples


def parse_args():
    parser = argparse.ArgumentParser(description='Inactivate/activate sample?? dirs (i.e., prepend/remove "_" from dir name)', formatter_class=SuppressMetavar)
    parser.add_argument('-e', '--exp_paths', help='List of experiment dir paths w/ sample?? dirs to process.', nargs='*', default=None, action=SM)
    parser.add_argument('-p', '--pattern', help='Pattern for sample?? dirs. Use cwd if no matches.', default='sample??', action=SM)
    parser.add_argument('-d', '--dirs', help='List of sample?? dir names or paths to dirs to process', nargs='*', default=None, action=SM)
    parser.add_argument('-t', '--toggle_all', help='Toggle all sample folders to active, ignoring condition checks.', action='store_true', default=False)
    parser.add_argument('-c', '--csv', help='path/sample_key.csv w/ directory names and conditions', default=None, action=SM)
    parser.add_argument('-a', '--activate', help='Space separated list of conditions to enable processing for (must match sample_key.csv)', default=None, nargs='*', action=SM)
    parser.add_argument('-v', '--verbose', help='Increase verbosity.', action='store_true', default=False)
    parser.epilog = """
Usage for toggling all sample?? dirs to active:
toggle_samples.py -t
    
Usage for activating sample?? dirs for certain conditions:
toggle_samples.py -c <path/sample_key.csv> -a <Saline MDMA> -v

For conditions in the activate list, the script will remove the "_" from the sample?? dir name.
For conditions not in the activate list, the script will prepend "_" to the sample?? dir name.    

The sample_key.csv file should have the following format:
    dir_name,condition
    sample01,control
    sample02,treatment
"""    
    return parser.parse_args()


def main():
    args = parse_args()

    active_samples = get_samples(args.dirs, args.pattern, args.exp_paths)
    inactive_samples = get_samples(args.dirs, f'_{args.pattern}', args.exp_paths)
    samples = active_samples + inactive_samples
    
    for sample in samples:
        sample_path = Path(sample).resolve() if sample != Path.cwd().name else Path.cwd()
        stripped_sample_name = sample_path.name.lstrip('_')  # Strip leading underscore for accurate CSV matching
            
        # Get the condition for the current sample
        mapping_df = pd.read_csv(args.csv)
        condition_df = mapping_df[mapping_df['dir_name'] == stripped_sample_name]['condition']

        if args.toggle_all:
            new_name = sample_path.parent / stripped_sample_name
            sample_path.rename(new_name)
            status = "Activated"
        else:
            if not condition_df.empty:
                condition = condition_df.values[0]
                if condition in args.activate:
                    new_name = sample_path.parent / stripped_sample_name
                    status = "Activated"
                else:
                    new_name = sample_path.parent / f'_{stripped_sample_name}'
                    status = "Inactivated"
            else:
                print(f"No condition found for {stripped_sample_name}, skipping...")
                continue  # Skip to the next iteration if no condition found

        sample_path.rename(new_name)

        if args.verbose: 
            if status == "Activated":
                print(f"  [green]{status}[/] [default bold]{stripped_sample_name}[/] ([default bold]{condition}[/]). New path: {new_name}")
            else: 
                print(f"[red1]{status}[/] [default bold]{stripped_sample_name}[/] ([default bold]{condition}[/]). New path: {new_name}")


if __name__ == '__main__': 
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    print_cmd_and_times(main)()