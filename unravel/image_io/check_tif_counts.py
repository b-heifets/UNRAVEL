#!/usr/bin/env python3
"""
Use ``io_check_tif_counts`` to compare the number of TIFF files across two or more
image directories for each sample. Accepts .tif, .ome.tif, and .tiff files.

Inputs:
    - Relative paths to TIFF directories within each sample (e.g., 488 561 561_rb20)

Output:
    - Prints OK for matching counts and MISMATCH with per-directory counts otherwise.
    - No image data is loaded and no TIFF files are modified.

Usage:
------
    io_check_tif_counts -i 488 561 [-d list of sample or parent directories] [-p sample??] [-v]
    io_check_tif_counts -i 488 561 561_rb20 -d <paths to condition dirs> -p '*sample??'
"""

import os
from pathlib import Path

from rich import print
from rich.traceback import install

from unravel.core.config import Configuration
from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.utils import get_samples, log_command, verbose_start_msg, verbose_end_msg


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-i', '--input', help='Relative TIFF directory paths to compare within each sample (at least 2)', required=True, nargs='*', action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-d', '--dirs', help='Paths to sample dirs and/or dirs containing them. Default: current dir', nargs='*', default=None, action=SM)
    general.add_argument('-p', '--pattern', help='Pattern for sample directories. Default: sample??; use *sample?? to include _sample??', default='sample??', action=SM)
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()


def count_tifs(directory):
    """Count files ending in .tif or .tiff, including .ome.tif, without loading images."""
    if not directory.is_dir():
        return None
    with os.scandir(directory) as entries:
        return sum(
            entry.is_file() and entry.name.lower().endswith(('.tif', '.tiff'))
            for entry in entries
        )


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    if not args.input or len(args.input) < 2:
        raise ValueError('Provide at least two TIFF directories with -i (e.g., -i 488 561).')

    sample_paths = get_samples(args.dirs, args.pattern, args.verbose)
    if not sample_paths:
        raise ValueError(f'No sample directories found matching {args.pattern!r}.')

    matched = 0
    mismatched = 0
    for sample in sample_paths:
        counts = [(rel, count_tifs(sample / rel)) for rel in args.input]
        values = [count for _, count in counts]
        label = f'{sample.parent.name}/{sample.name}'

        if all(count is not None and count > 0 for count in values) and len(set(values)) == 1:
            matched += 1
            print(f'    [green]OK[/]        {label}: {values[0]} TIFFs')
        else:
            mismatched += 1
            print(f'    [red]MISMATCH[/]  {label}')
            for rel, count in counts:
                count_label = 'MISSING' if count is None else str(count)
                print(f'        {rel}: {count_label}')

    print(f'\n    Summary: {matched} OK, {mismatched} mismatched/missing ({len(sample_paths)} samples)\n')
    verbose_end_msg()


if __name__ == '__main__':
    main()
