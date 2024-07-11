#!/usr/bin/env python3

"""
Use ``cluster_mirror_indices`` from UNRAVEL to recursively process img.nii.gz files, apply mirroring, and save new files.

Usage
-----
    cluster_mirror_indices -m RH -v
    
Use this command after ``cluster_fdr`` to mirror the cluster indices for the other side of the brain before running ``cluster_validation``.  

Note:
    - Use -ax 2 and -s 0 for the CCFv3 2020 atlas.
    - Use -ax 0 and -s 2 for the 25 um Gubra atlas
"""

import argparse
import numpy as np
import nibabel as nib
import shutil
from pathlib import Path
from rich.traceback import install
from concurrent.futures import ThreadPoolExecutor

from unravel.core.argparse_utils import SM, SuppressMetavar
from unravel.core.config import Configuration
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg
from unravel.voxel_stats.mirror import mirror

def parse_args():
    parser = argparse.ArgumentParser(formatter_class=SuppressMetavar)
    parser.add_argument('-m', '--mas_side', help='Side of the brain corresponding to the mask used for ``vstats`` and ``cluster_fdr`` (RH or LH)', choices=['RH', 'LH'], required=True, action=SM)
    parser.add_argument('-p', '--pattern', help='Glob pattern to match files. Default: **/*rev_cluster_index.nii.gz', default='**/*rev_cluster_index.nii.gz', action=SM)
    parser.add_argument('-ax', '--axis', help='Axis to flip the image along. Default: 2', default=2, type=int, action=SM)
    parser.add_argument('-s', '--shift', help='Number of voxels to shift content after flipping. Default: 0', default=0, type=int, action=SM)
    parser.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)
    parser.epilog = __doc__
    return parser.parse_args()


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

@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()


    root_path = Path().resolve()
    files = list(root_path.glob(args.pattern))

    with ThreadPoolExecutor() as executor:
        executor.map(lambda file: process_file(file, args), files)

    verbose_end_msg()
    

if __name__ == '__main__':
    main()