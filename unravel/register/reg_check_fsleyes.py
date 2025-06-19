#!/usr/bin/env python3

"""
Use ``reg_check_fsleyes`` (``rcf``) from UNRAVEL to check registration in fsleyes.

Prerequisites:
    - ``fsleyes`` must be installed.
    - ``reg_check`` to aggregate the fixed_reg_in, warped_atlas, and optionally the original autofluorescence image.
    - Set up LUT for the atlas in FSLeyes (see "Setting up Allen brain atlas coloring in FSLeyes" at https://b-heifets.github.io/UNRAVEL/guide.html#reg-check)

Notes:
    - The inputs can be glob patterns 

    Usage:
------
    reg_check_fsleyes [-fri fixed_reg_in] [-wa warped_atlas] [-min min_val] [-max max_val] [-og] [-af autofl_img] [-d list of paths]
"""

import subprocess
from glob import glob
from pathlib import Path
from rich import print
from rich.traceback import install

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.utils import log_command


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-fri', '--fixed_reg_in', help='Fixed image from registration ``reg``. Default: autofl_50um_masked_fixed_reg_input.nii.gz', default="autofl_50um_masked_fixed_reg_input.nii.gz", action=SM)
    opts.add_argument('-af', '--autofl_img', help='The original autofluorescence image (loaded if present). Default: autofl_50um.nii.gz', default="autofl_50um.nii.gz", action=SM)
    opts.add_argument('-wa', '--warped_atlas', help='Warped atlas image from ``reg``. Default: atlas_CCFv3_2020_30um_in_tissue_space.nii.gz', default="atlas_CCFv3_2020_30um_in_tissue_space.nii.gz", action=SM)
    opts.add_argument('-min', '--min', help='Minimum intensity value for ``fsleyes`` display. Default: 0', type=float, default=0.0)
    opts.add_argument('-max', '--max', help='Maximum intensity value for ``fsleyes`` display. Default: 5000', type=float, default=5000.0)

    return parser.parse_args()


@log_command
def main():
    install()
    args = parse_args()

    cwd = Path.cwd()

    # Collect autofl NIfTI paths
    autofl_nii_paths, masked_autofl_nii_paths, warped_atlas_nii_paths = [], [], []
    autofl_nii_paths.extend(cwd.glob(args.autofl_img))
    masked_autofl_nii_paths.extend(cwd.glob(args.fixed_reg_in))
    warped_atlas_nii_paths.extend(cwd.glob(args.warped_atlas))

    # If lists are empty, raise an error
    if not masked_autofl_nii_paths and not autofl_nii_paths:
        print("Error: No autofluorescence or masked autofluorescence images found.")
        return
    
    if not warped_atlas_nii_paths:
        print("Error: No warped atlas images found.")
        return

    # Sort the paths by file name
    autofl_nii_paths = sorted(autofl_nii_paths, key=lambda p: p.name) if autofl_nii_paths else []
    masked_autofl_nii_paths = sorted(masked_autofl_nii_paths, key=lambda p: p.name)
    warped_atlas_nii_paths = sorted(warped_atlas_nii_paths, key=lambda p: p.name) 
    print(f'\nSorted orig_autofl_nii_paths= {autofl_nii_paths}\n')
    print(f'\nSorted masked_autofl_nii_paths= {masked_autofl_nii_paths}\n')
    print(f'\nSorted warped_atlas_nii_paths= {warped_atlas_nii_paths}\n')

    # Ensure lists have the same length
    if len(masked_autofl_nii_paths) != len(warped_atlas_nii_paths):
        print("Warning: The number of fixed and warped atlas files do not match.")
        return
    
    if autofl_nii_paths and len(masked_autofl_nii_paths) != len(autofl_nii_paths):
        print("Warning: The number of fixed and autofluorescence files do not match.")
        return

    # Define command for fsleyes
    fsleyes_command = ['fsleyes']
    if autofl_nii_paths:
        fsleyes_command.extend([str(autofl_nii_paths[0]), '-dr', str(args.min), str(args.max)])
    fsleyes_command.extend([str(masked_autofl_nii_paths[0]), '-dr', str(args.min), str(args.max)])
    fsleyes_command.extend([str(warped_atlas_nii_paths[0]), '-ot', 'label', '-l', 'ccfv3_2020', '-o', '-a', '50'])

    # Drop the first element from the lists (so that visualization of remaining images is off)
    if autofl_nii_paths:
        autofl_nii_paths.pop(0)
    masked_autofl_nii_paths.pop(0)
    warped_atlas_nii_paths.pop(0)

    # Iterate over fixed_reg_input_files and warped_atlas_files
    if autofl_nii_paths:
        for autofl, masked_autofl, atlas,  in zip(autofl_nii_paths, masked_autofl_nii_paths, warped_atlas_nii_paths):
            fsleyes_command.extend([str(autofl), '-dr', str(args.min), str(args.max), '-d'])
            fsleyes_command.extend([str(masked_autofl), '-dr', str(args.min), str(args.max), '-d'])
            fsleyes_command.extend([str(atlas), '-ot', 'label', '-l', 'ccfv3_2020', '-o', '-a', '50', '-d'])
    else: 
        for masked_autofl, atlas in zip(masked_autofl_nii_paths, warped_atlas_nii_paths):
            fsleyes_command.extend([str(masked_autofl), '-dr', str(args.min), str(args.max), '-d']) # -d for no display
            fsleyes_command.extend([str(atlas), '-ot', 'label', '-l', 'ccfv3_2020', '-o', '-a', '50', '-d'])

    # Execute fsleyes command
    subprocess.run(fsleyes_command)


if __name__ == '__main__':
    main()
