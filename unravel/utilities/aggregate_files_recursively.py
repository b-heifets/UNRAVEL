#!/usr/bin/env python3

"""
Use ``utils_agg_files_rec`` from UNRAVEL to recusively copy files matching a glob pattern.

Usage:
------
    utils_agg_files_rec -p '<asterisk>.txt' [-s /path/to/source] [-d /path/to/destination] [--move] [-v]
"""

import shutil
from pathlib import Path
from rich.traceback import install

from help_formatter import RichArgumentParser, SuppressMetavar, SM

from unravel.core.config import Configuration
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-p', '--pattern', help="The pattern to match files, e.g., '*.txt'", required=True, action=SM)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-s', '--source', help='The source directory to search files in. Default: current working dir', default='.', action=SM)
    opts.add_argument('-d', '--destination', help='The destination directory to copy files to. Default: current working dir', default='.', action=SM)
    opts.add_argument('-m', '--move', help='Move files instead of copying. Default: False', action='store_true', default=False)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()


def find_and_copy_files(pattern, src_dir, dest_dir, move=False):
    src_dir = Path(src_dir)
    dest_dir = Path(dest_dir)
    if not dest_dir.is_absolute():
        dest_dir = src_dir.joinpath(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)

    # Use rglob for recursive globbing
    matched_files = list(src_dir.rglob(pattern))  # Convert the generator to a list

    if len(matched_files) == 0:
        print(f"\n    [red1]No files found matching the pattern:[/] [bold]{pattern}[/] in {src_dir}\n")
        import sys ; sys.exit()

    for file_path in matched_files: 
        if dest_dir not in file_path.parents:
            if move:
                shutil.move(str(file_path), dest_dir)
            else:
                shutil.copy(str(file_path), dest_dir)


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    find_and_copy_files(args.pattern, args.source, args.destination, args.move)

    verbose_end_msg()


if __name__ == '__main__':
    main()