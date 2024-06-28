#!/usr/bin/env python3

"""
Use ``vstats_hemi_to_avg`` from UNRAVEL to automatically average hemisphere images with their mirrored counterparts. This can also smooth the images with a kernel and apply a mask.

Usage:
------
    vstats_hemi_to_avg -k 0.1 -tp -v

Inputs: 
    - input_img_LH.nii.gz
    - input_img_RH.nii.gz

Outputs:
    - input_img_LRavg.nii.gz
    - input_img_s100_LRavg.nii.gz

"""


import argparse
import numpy as np
import nibabel as nib
from glob import glob
from pathlib import Path
from rich import print
from rich.traceback import install
from concurrent.futures import ThreadPoolExecutor

from fsl.wrappers import fslmaths

from unravel.core.argparse_utils import SM, SuppressMetavar
from unravel.core.config import Configuration
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg, print_func_name_args_times
from unravel.voxel_stats.apply_mask import load_mask
from unravel.voxel_stats.mirror import mirror


def parse_args():
    parser = argparse.ArgumentParser(formatter_class=SuppressMetavar)
    parser.add_argument('-k', '--kernel', help='Smoothing kernel radius in mm if > 0. Default: 0 ', default=0, type=float, action=SM)
    parser.add_argument('-ax', '--axis', help='Axis to flip the image along. Default: 0', default=0, type=int, action=SM)
    parser.add_argument('-s', '--shift', help='Number of voxels to shift content after flipping. Default: 2', default=2, type=int, action=SM)
    parser.add_argument('-tp', '--parallel', help='Enable parallel processing with thread pools', default=False, action='store_true')
    parser.add_argument('-amas', '--atlas_mask', help='path/atlas_mask.nii.gz', default=None, action=SM)
    parser.add_argument('-v', '--verbose', help='Increase verbosity', default=False, action='store_true')
    parser.epilog = __doc__
    return parser.parse_args()


@print_func_name_args_times()
def hemi_to_LR_avg(lh_file, rh_file, kernel=0, axis=0, shift=2, atlas_mask=None):
    path = lh_file.parent
    output_filename = rh_file.name.replace('_RH.nii.gz', f'_s{str(int(kernel * 1000))}_LRavg.nii.gz' if kernel > 0 else '_LRavg.nii.gz')
    output_path = path / output_filename

    # Check if the output file already exists
    if output_path.exists():
        print(f"Output {output_filename} already exists. Skipping...")
        return

    # Load images
    right_nii = nib.load(str(rh_file))
    left_nii = nib.load(str(lh_file))

    # Optionally smooth images
    if kernel > 0:
        print(f"    Smoothing images with a kernel radius of {kernel} mm")
        right_nii = fslmaths(right_nii).s(kernel).run()
        left_nii = fslmaths(left_nii).s(kernel).run()

    right_img = np.asanyarray(right_nii.dataobj, dtype=right_nii.header.get_data_dtype()).squeeze()
    left_img = np.asanyarray(left_nii.dataobj, dtype=left_nii.header.get_data_dtype()).squeeze()

    # Mirror and average images
    mirrored_left_img = mirror(left_img, axis=axis, shift=shift)
    averaged_img = (right_img + mirrored_left_img) / 2

    # Apply the mask
    if atlas_mask is not None:
        mask_img = load_mask(atlas_mask)
        averaged_img[~mask_img] = 0  # Use logical NOT to flip True/False

    # Save the averaged image
    averaged_nii = nib.Nifti1Image(averaged_img, right_nii.affine, right_nii.header)
    nib.save(averaged_nii, output_path)
    print(f"    Saved averaged image to {output_filename}")


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    path = Path.cwd()
    rh_files = list(path.glob('*_RH.nii.gz'))

    if args.parallel:
        with ThreadPoolExecutor() as executor:
            executor.map(lambda rh_file: hemi_to_LR_avg(path / str(rh_file).replace('_RH.nii.gz', '_LH.nii.gz'), rh_file, args.kernel, args.axis, args.shift, args.atlas_mask), rh_files)
    else:
        for rh_file in rh_files:
            lh_file = path / str(rh_file).replace('_RH.nii.gz', '_LH.nii.gz')
            hemi_to_LR_avg(lh_file, rh_file, args.kernel, args.axis, args.shift, args.atlas_mask)

    verbose_end_msg()


if __name__ == '__main__':
    main()