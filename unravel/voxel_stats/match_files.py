#!/usr/bin/env python3

"""
Use ``vstats_match_files`` or ``match_files`` from UNRAVEL to match files and print the order.

Note:
    - This is useful for noting group order in ``vstats``.

Usage:
------
    vstats_match_files [-i path/<asterisk>.nii.gz or glob pattern(s) to match] [-idx] [-v]
"""

from pathlib import Path
from rich import print
from rich.traceback import install

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.config import Configuration
from unravel.core.utils import log_command, match_files, verbose_start_msg, verbose_end_msg


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-i', '--input', help="path/*.nii.gz for input images or glob pattern(s) to match. Default: '*.nii.gz'", nargs='*', default=['*.nii.gz'], action=SM)
    opts.add_argument('-idx', '--index', help='Print the index of each matched file. Default: False', action='store_true', default=False)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', default=False, action='store_true')

    return parser.parse_args()


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    images = match_files(args.input)
    print("\nMatched files in this order:\n")
    if args.index:
        for i, image in enumerate(images):
            print(f"{i}: {image.name}")
    else:
        for image in images:
            print(f"{image.name}")
    
    verbose_end_msg()


if __name__ == '__main__':
    main()