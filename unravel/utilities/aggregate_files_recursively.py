#!/usr/bin/env python3

"""
Use ``utils_agg_files_rec`` from UNRAVEL to recusively copy files matching a glob pattern.

Usage:
------
    utils_agg_files_rec -p '<asterisk>.txt' -s /path/to/source -d /path/to/destination
"""

import argparse
import shutil
from pathlib import Path
from rich.traceback import install

from unravel.core.argparse_utils import SuppressMetavar, SM
from unravel.core.config import Configuration
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg


def parse_args():
    parser = argparse.ArgumentParser(description='', formatter_class=SuppressMetavar)
    parser.add_argument("-p", "--pattern", help="The pattern to match files, e.g., '*.txt'", required=True, action=SM)
    parser.add_argument("-s", "--source", help="The source directory to search files in. Default: current working dir", default=".", action=SM)
    parser.add_argument("-d", "--destination", help="The destination directory to copy files to. Default: current working dir", default=".", action=SM)
    parser.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)
    parser.epilog = __doc__
    return parser.parse_args()


def find_and_copy_files(pattern, src_dir, dest_dir):
    src_dir = Path(src_dir)
    dest_dir = Path(dest_dir)
    if not dest_dir.is_absolute():
        dest_dir = src_dir.joinpath(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)

    for file_path in src_dir.rglob(pattern): # Use rglob for recursive globbing
        if dest_dir not in file_path.parents:
            shutil.copy(str(file_path), dest_dir)
            # print(f"Copied: {file_path} to {dest_dir}")


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    find_and_copy_files(args.pattern, args.source, args.destination)

    verbose_end_msg()


if __name__ == '__main__':
    main()