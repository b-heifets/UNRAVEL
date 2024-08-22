#!/usr/bin/env python3

"""
Use ``path/get_samples.py`` from UNRAVEL to test the get_samples() function in unravel/core/utils.py.
"""

import argparse
from rich import print
from rich.traceback import install

from unravel.core.argparse_utils import SuppressMetavar, SM
from unravel.core.config import Configuration 
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg, get_samples

def parse_args():
    parser = argparse.ArgumentParser(formatter_class=SuppressMetavar)
    parser.add_argument('-d', '--dirs', help='Paths to sample?? dirs and/or dirs containing them. Default: use current dir', nargs='*', default=None, action=SM)
    parser.add_argument('-p', '--pattern', help='Pattern for directories to process. Default: sample??', default='sample??', action=SM)
    parser.add_argument('-v', '--verbose', help='Increase verbosity.', action='store_true', default=False)
    parser.epilog = __doc__
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