#!/usr/bin/env python3

"""
Use ``path/get_samples.py`` from UNRAVEL to test the get_samples() function in unravel/core/utils.py.

Usage:
------
``path/get_samples.py`` [-d dirs] [-p pattern] [-v]

"""

import argparse
from rich import print
from rich.traceback import install

from unravel.core.argparse_utils_rich import SuppressMetavar, SM, CustomHelpAction
from unravel.core.config import Configuration 
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg, get_samples

def parse_args():
    parser = argparse.ArgumentParser(formatter_class=SuppressMetavar, add_help=False)
    parser.add_argument('-h', '--help', action=CustomHelpAction, help='Show this help message and exit.', docstring=__doc__)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-d', '--dirs', help='Paths to sample?? dirs and/or dirs containing them. Default: use current dir', nargs='*', default=None, action=SM)
    general.add_argument('-p', '--pattern', help='Pattern for directories to process. Default: sample??', default='sample??', action=SM)
    general.add_argument('-v', '--verbose', help='Increase verbosity.', action='store_true', default=False)

    return parser.parse_args()

@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    sample_paths = get_samples(args.dirs, args.pattern, args.verbose)

    print(f'\n{sample_paths=}\n')

    verbose_end_msg()


if __name__ == '__main__':
    main()