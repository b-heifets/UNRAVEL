#!/usr/bin/env python3

"""
Use ``vstats_check_fsleyes`` (``vcf``) from UNRAVEL to check inputs for voxel-wise stats in fsleyes.

Prereqs:
    - ``fsleyes`` must be installed and the custom look up table (LUT) must be in the correct directory.
    - Use ``agg`` to aggregate the atlas space images from sample directories.

Usage:
------
``vstats_check_fsleyes`` -min -1 -max 3 [-i '<asterisk>.nii.gz'] [-a atlas/atlas_CCFv3_2020_30um.nii.gz] [-l ccfv3_2020]
"""

import os
import subprocess
from pathlib import Path
from rich import print
from rich.traceback import install

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.utils import log_command, match_files

ATLAS = os.getenv("ATLAS", "None")

def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-min', '--min', help='Minimum intensity value for ``fsleyes`` display (.e.g., "-1" for z scored or "0")', type=float, required=True)
    reqs.add_argument('-max', '--max', help='Maximum intensity value for ``fsleyes`` display (e.g., "3" for z-scored or "3000")', type=float, required=True)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-i', '--input', help="NIfTI image path(s) or pattern(s) to process (e.g., '*.nii.gz')", default='*.nii.gz', nargs='*', action=SM)
    opts.add_argument('-a', '--atlas', help=f'path/atlas.nii.gz (e.g., atlas_CCFv3_2020_30um.nii.gz). Default: {ATLAS}', default=ATLAS, action=SM)
    opts.add_argument('-l', '--lut', help='Look up table name. Default: ccfv3_2020', default='ccfv3_2020', action=SM)

    return parser.parse_args()

@log_command
def main():
    install()
    args = parse_args()

    nii_paths = match_files(args.input)

    # Define command for fsleyes
    fsleyes_command = ['fsleyes']
    fsleyes_command.extend([str(nii_paths[0]), '-dr', str(args.min), str(args.max)])

    # Drop the first element
    nii_paths.pop(0)

    # Iterate over the remaining
    for nii_path in nii_paths:
        fsleyes_command.extend([str(nii_path), '-dr', str(args.min), str(args.max), '-d'])

    # Add atlas to fsleyes command
    fsleyes_command.extend([args.atlas, '-ot', 'label', '-l', args.lut, '-o', '-a', '50'])

    print(f'\n{fsleyes_command=}\n')    

    # Execute fsleyes command
    subprocess.run(fsleyes_command)


if __name__ == '__main__':
    main()
