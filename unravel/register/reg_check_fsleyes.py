#!/usr/bin/env python3

"""
Use ``reg_check_fsleyes`` (``rcf``) from UNRAVEL to check registration in fsleyes.

Prerequisites:
    - ``fsleyes`` must be installed.
    - Recommended: ``reg_check`` must be run before this script to aggregate the fixed_reg_in and warped_atlas files.
    - ``reg_check`` also prepends them with the sample?? dir name.

Notes:
    - The script will recursively search for the fixed_reg_in and warped_atlas files.

Usage:
------
``reg_check_fsleyes`` [-fri fixed_reg_in] [-wa warped_atlas] [-min min_val] [-max max_val] [-d dirs] 
"""

import subprocess
from pathlib import Path
from rich import print
from rich.traceback import install

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.utils import log_command


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-fri', '--fixed_reg_in', help='Fixed image from registration ``reg``. Default: autofl_50um_masked_fixed_reg_input.nii.gz', default="autofl_50um_masked_fixed_reg_input.nii.gz", action=SM)
    opts.add_argument('-wa', '--warped_atlas', help='Warped atlas image from ``reg``. Default: atlas_CCFv3_2020_30um_in_tissue_space.nii.gz', default="atlas_CCFv3_2020_30um_in_tissue_space.nii.gz", action=SM)
    opts.add_argument('-min', '--min', help='Minimum intensity value for ``fsleyes`` display. Default: 0', type=float, default=0.0)
    opts.add_argument('-max', '--max', help='Maximum intensity value for ``fsleyes`` display. Default: 5000', type=float, default=5000.0)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-d', '--dirs', help='Paths to sample?? dirs and/or dirs containing them (space-separated) for batch processing. Default: current dir', nargs='*', default=None, action=SM)

    return parser.parse_args()

@log_command
def main():
    install()
    args = parse_args()

    dirs = [Path(d) for d in args.dirs] if args.dirs else [Path.cwd()]
    print(f'\n{dirs=}\n')

    # Collect autofl NIfTI paths
    autofl_nii_paths = []
    for dir in dirs:
        autofl_nii_paths.extend(dir.rglob(f'**/*{args.fixed_reg_in}'))
    print(f'\n{autofl_nii_paths=}\n')

    # Collect warped atlas NIfTI paths
    warped_atlas_nii_paths = []
    for dir in dirs:
        warped_atlas_nii_paths.extend(dir.rglob(f'**/*{args.warped_atlas}'))
    print(f'\n{warped_atlas_nii_paths=}\n')

    # Sort the paths by file name
    autofl_nii_paths = sorted(autofl_nii_paths, key=lambda p: p.name)
    print(f'\nSorted autofl_nii_paths= {autofl_nii_paths}\n')

    warped_atlas_nii_paths = sorted(warped_atlas_nii_paths, key=lambda p: p.name) 
    print(f'\nSorted warped_atlas_nii_paths= {warped_atlas_nii_paths}\n')

    # Ensure both lists have the same length
    if len(autofl_nii_paths) != len(warped_atlas_nii_paths):
        print("Warning: The number of fixed and warped atlas files do not match.")
        return

    # Define command for fsleyes
    fsleyes_command = ['fsleyes']
    fsleyes_command.extend([str(autofl_nii_paths[0]), '-dr', str(args.min), str(args.max)])
    fsleyes_command.extend([str(warped_atlas_nii_paths[0]), '-ot', 'label', '-l', 'ccfv3_2020', '-o', '-a', '50'])

    # Drop the first element from the lists
    autofl_nii_paths.pop(0)
    warped_atlas_nii_paths.pop(0)

    # Iterate over fixed_reg_input_files and warped_atlas_files
    for fixed_image, warped_image in zip(autofl_nii_paths, warped_atlas_nii_paths):
        fsleyes_command.extend([str(fixed_image), '-dr', str(args.min), str(args.max), '-d'])
        fsleyes_command.extend([str(warped_image), '-ot', 'label', '-l', 'ccfv3_2020', '-o', '-a', '50', '-d'])

    # Execute fsleyes command
    subprocess.run(fsleyes_command)


if __name__ == '__main__':
    main()
