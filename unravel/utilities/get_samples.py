#!/usr/bin/env python3

"""
Use ``path/get_samples.py`` from UNRAVEL to test the get_samples() function in unravel/core/utils.py.

Usage:
------
``path/get_samples.py`` [-d dirs] [-p pattern]
"""

from rich import print
from rich.traceback import install

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.config import Configuration 
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg, get_samples

def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)
    
    general = parser.add_argument_group('General arguments')
    general.add_argument('-d', '--dirs', help='Paths to sample?? dirs and/or dirs containing them (space-separated) for batch processing. Default: current dir', nargs='*', default=None, action=SM)
    general.add_argument('-p', '--pattern', help='Pattern for directories to process. Default: sample??', default='sample??', action=SM)

    return parser.parse_args()

@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = True
    verbose_start_msg()

    sample_paths = get_samples(args.dirs, args.pattern, args.verbose)

    verbose_end_msg()


if __name__ == '__main__':
    main()