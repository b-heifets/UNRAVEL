#!/usr/bin/env python3

import argparse
import numpy as np
import nibabel as nib
import shutil
from pathlib import Path
from rich.traceback import install

from argparse_utils import SM, SuppressMetavar
from mirror import mirror
from unravel_config import Configuration
from unravel_utils import print_cmd_and_times, print_func_name_args_times


def parse_args():
    parser = argparse.ArgumentParser(description='Recursively process img.nii.gz files, apply mirroring, and save new files.', formatter_class=SuppressMetavar)
    parser.add_argument('-m', '--mas_side', help='Side of the brain corresponding to the mask used for vstats.py and fdr.py (RH or LH)', choices=['RH', 'LH'], required=True, action=SM)
    parser.add_argument('-p', '--pattern', help='Glob pattern to match files.', default='**/*rev_cluster_index.nii.gz', action=SM)
    parser.add_argument('-a', '--axis', help='Axis to flip the image along. Default: 0', default=0, type=int, action=SM)
    parser.add_argument('-s', '--shift', help='Number of voxels to shift content after flipping. Default: 2', default=2, type=int, action=SM)
    parser.add_argument('-v', '--verbose', action='store_true', help='Increase verbosity')
    parser.epilog = """Usage: recursively_mirror_rev_cluster_indices.py -side RH -v"""
    return parser.parse_args()

# TODO: adapt to work with CCFv3 images if needed 


def main(): 
    root_path = Path().resolve()
    files = list(root_path.glob(args.pattern))
    for file_path in files:
        # Skip if it is not a file
        if not file_path.is_file():
            continue

        print(f'Processing: {file_path}') if args.verbose else None

        # Copy the original file to a new file and label suffix using args.mask_side
        new_file_path = file_path.parent / f"{file_path.name}_{args.mas_side}.nii.gz"
        shutil.copy(file_path, new_file_path)

        # Handle mirroring
        nii = nib.load(str(file_path))
        img = np.asanyarray(nii.dataobj, dtype=nii.header.get_data_dtype()).squeeze()
        mirrored_img = mirror(img, axis=args.axis, shift=args.shift)
        mirrored_nii = nib.Nifti1Image(mirrored_img, nii.affine, nii.header)

        # Saving mirrored images
        if args.mas_side == 'RH':
            mirrored_filename = file_path.parent / f"{file_path.name}_LH.nii.gz"
        elif args.mas_side == 'LH':
            mirrored_filename = file_path.parent / f"{file_path.name}_RH.nii.gz"

        nib.save(mirrored_nii, mirrored_filename)
        print(f'Saved mirrored image to {mirrored_filename}') if args.verbose else None


if __name__ == '__main__': 
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    print_cmd_and_times(main)()