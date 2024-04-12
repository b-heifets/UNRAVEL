#!/usr/bin/env python3

import argparse
import pandas as pd
from glob import glob
from pathlib import Path
from rich import print
from rich.traceback import install

from argparse_utils import SuppressMetavar, SM
from unravel_utils import get_samples


def parse_args():
    parser = argparse.ArgumentParser(description='Inactivate/activate sample?? dirs (i.e., prepend/remove "_" from dir name)', formatter_class=SuppressMetavar)
    parser.add_argument('-e', '--exp_paths', help='List of experiment dir paths w/ sample?? dirs to process.', nargs='*', default=None, action=SM)
    parser.add_argument('-p', '--pattern', help='Pattern for sample?? dirs. Use cwd if no matches.', default='sample??', action=SM)
    parser.add_argument('-d', '--dirs', help='List of sample?? dir names or paths to dirs to process', nargs='*', default=None, action=SM)
    parser.add_argument('-c', '--csv', help='path/sample_key.csv w/ directory names and conditions', required=True)
    parser.add_argument('-a', '--activate', help='Space separated list of conditions to enable processing for (must match sample_key.csv)', required=True)
    parser.epilog = """Example usage:     toggle_samples.py -c <path/sample_key.csv> -a <Saline MDMA> -v
    
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

        # Get the condition for the current sample
        mapping_df = pd.read_csv(args.csv)
        condition = mapping_df[mapping_df['dir_name'] == sample_path.name]['condition'].values[0]

        print(f"Sample: {sample_path.name}, Condition: {condition}")

        # Check if the current sample is in the list of active samples
        if condition in args.activate:
            # Remove the "_" from the sample directory name
            new_name = sample_path.parent / sample_path.name.lstrip('_')
            print(f"Activating [default bold]{sample_path.name}[\] with condition [default bold]{condition}")
            print(f"New name: {new_name}")
        else:
            # Prepend "_" to the sample directory name
            new_name = sample_path.parent / f'_{sample_path.name}'
            print(f"Inactivating [default bold]{sample_path.name} with condition [default bold]{condition}")
            print(f"New name: {new_name}")

        sample_path.rename(new_name)


if __name__ == '__main__':
    install()
    main()