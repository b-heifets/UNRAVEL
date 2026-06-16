#!/usr/bin/env python3

"""
Use ``utils_agg_files_rec`` (``agg_rec``) from UNRAVEL to recusively copy files matching a glob pattern.

Usage:
------
    utils_agg_files_rec -p '<asterisk>.txt' [-s /path/to/source] [-d /path/to/destination] [--move] [-v]
"""

import shutil
from pathlib import Path
from rich.traceback import install
from rich import print

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM

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
    src_dir = Path(src_dir).resolve()
    dest_dir = Path(dest_dir)

    if not dest_dir.is_absolute():
        dest_dir = src_dir / dest_dir
    dest_dir = dest_dir.resolve()
    dest_dir.mkdir(parents=True, exist_ok=True)

    matched_files = [p.resolve() for p in src_dir.rglob(pattern) if p.is_file()]

    files_to_process = []
    seen_outputs = set()

    for file_path in matched_files:
        out_path = dest_dir / file_path.name

        # Case 1: destination is the source root.
        # Skip files already directly in the root destination.
        if dest_dir == src_dir and file_path.parent == dest_dir:
            continue

        # Case 2: destination is a subdirectory.
        # Skip files already inside that destination directory.
        if dest_dir != src_dir and dest_dir in file_path.parents:
            continue

        # Avoid processing duplicate target basenames more than once.
        # This matters if matches exist both in nested dirs and _CCF30.
        if out_path in seen_outputs:
            continue
        seen_outputs.add(out_path)

        files_to_process.append((file_path, out_path))

    if len(files_to_process) == 0:
        print(f"\n    [red1]No files found matching the pattern:[/] [bold]{pattern}[/] in {src_dir}\n")
        import sys
        sys.exit()

    n_copied = 0
    n_skipped = 0

    for file_path, out_path in files_to_process:
        if out_path.exists():
            print(f"    [yellow]Skipping existing file:[/] {out_path}")
            n_skipped += 1
            continue

        if move:
            shutil.move(str(file_path), str(out_path))
        else:
            shutil.copy2(str(file_path), str(out_path))

        n_copied += 1

    action = "Moved" if move else "Copied"
    print(f"\n{action} {n_copied} file(s) to: {dest_dir}")
    if n_skipped:
        print(f"Skipped {n_skipped} existing file(s).\n")
    else:
        print()


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