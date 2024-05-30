#!/usr/bin/env python3

import argparse
import numpy as np
import nibabel as nib
import shutil
from pathlib import Path
from rich.traceback import install
from concurrent.futures import ThreadPoolExecutor

from unravel.argparse_utils import SM, SuppressMetavar
from voxel_stats.mirror import mirror
from unravel.config import Configuration
from unravel.utils import print_cmd_and_times

def parse_args():
    parser = argparse.ArgumentParser(description='Recursively process img.nii.gz files, apply mirroring, and save new files.', formatter_class=SuppressMetavar)
    parser.add_argument('-m', '--mas_side', help='Side of the brain corresponding to the mask used for vstats.py and fdr.py (RH or LH)', choices=['RH', 'LH'], required=True, action=SM)
    parser.add_argument('-p', '--pattern', help='Glob pattern to match files. Default: **/*rev_cluster_index.nii.gz', default='**/*rev_cluster_index.nii.gz', action=SM)
    parser.add_argument('-ax', '--axis', help='Axis to flip the image along. Default: 0', default=0, type=int, action=SM)
    parser.add_argument('-s', '--shift', help='Number of voxels to shift content after flipping. Default: 2', default=2, type=int, action=SM)
    parser.add_argument('-v', '--verbose', action='store_true', help='Increase verbosity')
    parser.epilog = """Usage: recursively_mirror_rev_cluster_indices.py -m RH -v
    
Use this script after fdr.py to mirror the cluster indices for the other side of the brain before running valid_clusters_1_cell_or_label_densities.py    
"""
    return parser.parse_args()

# TODO: adapt to work with CCFv3 images if needed 


def process_file(file_path, args):
    if not file_path.is_file():
        return

    basename = str(file_path.name).replace('.nii.gz', '')
    new_file_path = file_path.parent / f"{basename}_{args.mas_side}.nii.gz"
    shutil.copy(file_path, new_file_path)

    nii = nib.load(str(file_path))
    img = np.asanyarray(nii.dataobj, dtype=nii.header.get_data_dtype()).squeeze()
    mirrored_img = mirror(img, axis=args.axis, shift=args.shift)
    mirrored_nii = nib.Nifti1Image(mirrored_img, nii.affine, nii.header)

    mirrored_filename = file_path.parent / f"{basename}_{'LH' if args.mas_side == 'RH' else 'RH'}.nii.gz"
    nib.save(mirrored_nii, mirrored_filename)

def main(): 
    root_path = Path().resolve()
    files = list(root_path.glob(args.pattern))

    with ThreadPoolExecutor() as executor:
        executor.map(lambda file: process_file(file, args), files)


if __name__ == '__main__': 
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    print_cmd_and_times(main)()