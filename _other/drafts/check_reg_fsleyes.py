#!/usr/bin/env python3

import argparse
import subprocess
from glob import glob
from rich.traceback import install

from unravel.core.argparse_utils import SuppressMetavar, SM


def parse_args():
    parser = argparse.ArgumentParser(description='Prepares and displays medical images in fsleyes for analysis.', formatter_class=SuppressMetavar)
    parser.add_argument('-fri', '--fixed_reg_in', help='Pattern for fixed image from registration. Default: *autofl_50um_masked_fixed_reg_input.nii.gz', default="*autofl_50um_masked_fixed_reg_input.nii.gz", action=SM)
    parser.add_argument('-wa', '--warped_atlas', help='Pattern for the warped atlas image from registration. Default: *gubra_ano_combined_25um_in_tissue_space.nii.gz', default="*gubra_ano_combined_25um_in_tissue_space.nii.gz", action=SM)
    parser.epilog = """Usage: check_reg_fsleyes.py"""
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