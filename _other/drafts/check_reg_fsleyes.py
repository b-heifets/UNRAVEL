#!/usr/bin/env python3

"""
Use ``check_reg_fsleyes.py`` to view images in fsleyes.

Usage: 
------
``check_reg_fsleyes.py``
"""

import argparse
import subprocess
from glob import glob
from rich.traceback import install

from unravel.core.argparse_utils_rich import SuppressMetavar, SM, CustomHelpAction



def parse_args():
    parser = argparse.ArgumentParser(formatter_class=SuppressMetavar, add_help=False)
    parser.add_argument('-h', '--help', action=CustomHelpAction, help='Show this help message and exit.', docstring=__doc__)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-fri', '--fixed_reg_in', help='Pattern for fixed image from registration. Default: *autofl_50um_masked_fixed_reg_input.nii.gz', default="*autofl_50um_masked_fixed_reg_input.nii.gz", action=SM)
    opts.add_argument('-wa', '--warped_atlas', help='Pattern for the warped atlas image from registration. Default: *atlas_CCFv3_2020_30um_in_tissue_space.nii.gz', default="*atlas_CCFv3_2020_30um_in_tissue_space.nii.gz", action=SM)

    return parser.parse_args()

def main():
    args = parse_args()

    fixed_reg_input_files = glob(args.fixed_reg_in)
    warped_atlas_files = glob(args.warped_atlas)

    visible = True  # Variable to control visibility of images

    # Iterate over fixed_reg_input_files and warped_atlas_files
    for fixed_image, warped_image in zip(fixed_reg_input_files, warped_atlas_files):
            # Building fsleyes command
            fsleyes_command = ['fsleyes']
            fsleyes_command.extend([str(fixed_image), '--visible', str(visible).lower(), '--alpha', '100'])
            fsleyes_command.extend([str(warped_image), '--visible', str(visible).lower(), '--alpha', '100', '-ot', 'label', '--cmap', 'Random', '-lw', '2'])
            
            # Only the first set should be visible
            visible = False
            
            # Execute fsleyes command
            subprocess.run(fsleyes_command)

if __name__ == '__main__':
    install()
    main()