#!/usr/bin/env python3

import argparse
import numpy as np
import nibabel as nib
from glob import glob
from fsl.wrappers import fslmaths
from pathlib import Path
from rich import print
from rich.traceback import install

from argparse_utils import SM, SuppressMetavar
from mirror import mirror
from unravel_config import Configuration
from unravel_utils import print_cmd_and_times


def parse_args():
    parser = argparse.ArgumentParser(description='Automatically average hemisphere images with their mirrored counterparts', formatter_class=SuppressMetavar)
    parser.add_argument('-k', '--kernel', help='Smoothing kernel radius in mm if > 0. Default: 0 ', default=0, type=float, action=SM)
    parser.add_argument('-a', '--axis', help='Axis to flip the image along. Default: 0', default=0, type=int, action=SM)
    parser.add_argument('-s', '--shift', help='Number of voxels to shift content after flipping. Default: 2', default=2, type=int, action=SM)
    parser.add_argument('-v', '--verbose', help='Increase verbosity', default=False, action='store_true')
    parser.epilog = """Usage:    hemi_to_LR_avg.py -k 0.05

Inputs: input_img_LH.nii.gz & input_img_RH.nii.gz
Output: input_img_LRavg.nii.gz or input_img_s50_LRavg.nii.gz"""
    return parser.parse_args()


def main(): 

    path = Path.cwd()
    rh_files = list(path.glob('*_RH.nii.gz'))

    for rh_file in rh_files:
        lh_file = Path(str(rh_file).replace('_RH.nii.gz', '_LH.nii.gz'))
        if rh_file.exists():
            print(f"\nProcessing L/R pair: [default bold]{lh_file.name}[/], [default bold]{rh_file.name}")

            # Load images
            right_nii = nib.load(str(rh_file))
            left_nii = nib.load(str(lh_file))

            # Smooth the images with a kernel
            if args.kernel > 0:
                print(f"    Smoothing images with a kernel radius of {args.kernel} mm")
                kernel_in_um = str(int(args.kernel * 1000))
                right_nii_smoothed = fslmaths(right_nii).s(args.kernel).run()
                right_img = np.asanyarray(right_nii_smoothed.dataobj, dtype=right_nii.header.get_data_dtype()).squeeze()
                left_nii_smoothed = fslmaths(left_nii).s(args.kernel).run()
                left_img = np.asanyarray(left_nii_smoothed.dataobj, dtype=left_nii.header.get_data_dtype()).squeeze()
            else: 
                right_img = np.asanyarray(right_nii.dataobj, dtype=right_nii.header.get_data_dtype()).squeeze()
                left_img = np.asanyarray(left_nii.dataobj, dtype=left_nii.header.get_data_dtype()).squeeze()


            # Mirror the left image along the specified axis and shift
            print(f"    Mirroring the left hemisphere image")
            mirrored_left_img = mirror(left_img, axis=args.axis, shift=args.shift)

            # Average the left and mirrored right images
            print(f"    Averaging the left image with the mirrored right hemisphere image")

            averaged_img = (right_img + mirrored_left_img) / 2

            # Save the averaged image
            if args.kernel > 0:
                output_filename = rh_file.name.replace('_RH.nii.gz', f'_s{kernel_in_um}_LRavg.nii.gz')
            else: 
                output_filename = rh_file.name.replace('_RH.nii.gz', '_LRavg.nii.gz')
            averaged_nii = nib.Nifti1Image(averaged_img, right_nii.affine, right_nii.header)
            nib.save(averaged_nii, path / output_filename)
            print(f"    Saved averaged image to {output_filename}\n")


if __name__ == '__main__': 
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    print_cmd_and_times(main)()