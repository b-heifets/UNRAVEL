#!/usr/bin/env python3

import argparse
from rich.traceback import install

from argparse_utils import SuppressMetavar, SM
from unravel_config import Configuration
from unravel_utils import get_samples, print_cmd_and_times


def parse_args():
    parser = argparse.ArgumentParser(description='Load full res image (.czi, .nii.gz, or tif series) to get metadata and save to ./parameters/metadata.txt', formatter_class=SuppressMetavar)
    parser.add_argument('-e', '--exp_paths', help='List of experiment dir paths w/ sample?? dirs to process.', nargs='*', default=None, action=SM)
    parser.add_argument('-p', '--pattern', help='Pattern for sample?? dirs. Use cwd if no matches.', default='sample??', action=SM)
    parser.add_argument('-s', '--dirs', help='List of folders to process. Overrides --pattern', nargs='*', default=None, action=SM)
    parser.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)
    return parser.parse_args()

def main(): 

    samples = get_samples(args.dirs, args.pattern, args.exp_paths)

    print(f'\n{samples=}\n')


if __name__ == '__main__': 
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    print_cmd_and_times(main)()