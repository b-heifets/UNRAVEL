#!/usr/bin/env python3

"""
Use ``utils_toggle`` (``toggle``) from UNRAVEL to inactivate/activate sample?? dirs for batch processing (i.e., prepend/remove "_" from dir name).

Note: 
    - For samples matching conditions in -c, "_" will be removed from the sample?? dir name.
    - For sampled not matching conditions in -c, "_" will be prepended to the sample?? dir name.

The sample_key.csv file should have the following format:
    dir_name,condition
    sample01,control
    sample02,treatment

Usage for toggling all sample?? dirs to active:
-----------------------------------------------
    utils_toggle [-d list of paths] [-p sample??] [-v]
    
Usage for activating sample?? dirs for certain conditions:
----------------------------------------------------------
    utils_toggle -sk <path/sample_key.csv> -c <Saline MDMA> [-d list of paths] [-p sample??] [-v]
"""    

import pandas as pd
from glob import glob
from pathlib import Path
from rich import print
from rich.traceback import install

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM

from unravel.core.config import Configuration
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg, get_samples


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    opts = parser.add_argument_group('Optional arguments for activating sample?? dirs based on conditions')
    opts.add_argument('-sk', '--sample_key', help='path/sample_key.csv w/ directory names and conditions (for activating sample?? dirs based on -a)', default=None, action=SM)
    opts.add_argument('-c', '--conditions', help='Space separated list of conditions to activate for processing (must match sample_key.csv)', default=None, nargs='*', action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-d', '--dirs', help='Paths to sample?? dirs and/or dirs containing them (space-separated) for batch processing. Default: current dir', nargs='*', default=None, action=SM)
    general.add_argument('-p', '--pattern', help='Pattern for directories to process. Default: sample??', default='sample??', action=SM)
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    active_sample_paths = get_samples(args.dirs, args.pattern, args.verbose)
    inactive_sample_paths = get_samples(args.dirs, f'_{args.pattern}', args.verbose)

    if args.verbose:
        print(f'\n{active_sample_paths=}\n')
        print(f'\n{inactive_sample_paths=}\n')

    sample_paths = active_sample_paths + inactive_sample_paths
    
    for sample_path in sample_paths:
        stripped_sample_name = sample_path.name.lstrip('_')  # Strip leading underscore for accurate CSV matching
            
        # Get the condition for the current sample
        if args.sample_key is not None: 
            mapping_df = pd.read_csv(args.sample_key)
            condition_df = mapping_df[mapping_df['dir_name'] == stripped_sample_name]['condition']

        if args.sample_key is None:
            new_name = sample_path.parent / stripped_sample_name
            print(f'{new_name=}')
            status = "Activated"
        else:
            if args.sample_key is not None:
                condition = condition_df.values[0]
                if condition in args.conditions:
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