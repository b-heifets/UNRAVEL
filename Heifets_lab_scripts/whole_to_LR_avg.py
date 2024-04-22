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
    parser = argparse.ArgumentParser(description='Average an image with its mirrored version for voxel-wise stats', formatter_class=SuppressMetavar)
    parser.add_argument('-p', '--pattern', help='Pattern to match files. Default: *.nii.gz', default='*.nii.gz', action=SM)
    parser.add_argument('-k', '--kernel', help='Smoothing kernel radius in mm if > 0. Default: 0 ', default=0, type=float, action=SM)
    parser.add_argument('-a', '--axis', help='Axis to flip the image along. Default: 0', default=0, type=int, action=SM)
    parser.add_argument('-s', '--shift', help='Number of voxels to shift content after flipping. Default: 2', default=2, type=int, action=SM)
    parser.add_argument('-v', '--verbose', help='Increase verbosity', default=False, action='store_true')
    parser.epilog = """Usage:    whole_to_LR_avg.py -k 0.05 -v

Run in the directory with the images to process (e.g in a dir w/ *_ochann_rb4_gubra_space_z.nii.gz)
    
Output: input_img_LRavg.nii.gz"""
    return parser.parse_args()


def main(): 
    files = Path().cwd().glob(args.pattern)
    print(f'\nImages to process: {list(files)}\n')

    files = Path().cwd().glob(args.pattern)
    for file in files:
        print(f"    Processing {file}\n")
        nii = nib.load(file)

        # Smooth the image with a kernel
        if args.kernel > 0:
            print(f"    Smoothing image with a kernel radius of {args.kernel} mm")
            nii_smoothed = fslmaths(nii).s(args.kernel).run()
            img = np.asanyarray(nii_smoothed.dataobj, dtype=np.float32).squeeze()
            kernel_in_um = str(int(args.kernel * 1000))
        else: 
            img = np.asanyarray(nii.dataobj, dtype=nii.header.get_data_dtype()).squeeze()

        # Mirror the image along the specified axis and shift the content by the specified number of voxels
        mirrored_img = mirror(img, axis=args.axis, shift=args.shift)

        # Average the original and mirrored images
        averaged_img = (img + mirrored_img) / 2

        # Save the averaged image
        averaged_nii = nib.Nifti1Image(averaged_img, nii.affine, nii.header)
        if args.kernel > 0:
            averaged_filename = f"{Path(file).name}".replace('.nii.gz', f'_s{kernel_in_um}_LRavg.nii.gz')
        else: 
            averaged_filename = f"{Path(file).name}".replace('.nii.gz', '_LRavg.nii.gz')
        nib.save(averaged_nii, averaged_filename)
        

if __name__ == '__main__': 
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    print_cmd_and_times(main)()