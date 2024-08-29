#!/usr/bin/env python3

"""
Use ``cstats_mirror_indices`` from UNRAVEL to recursively process img.nii.gz files, apply mirroring, and save new files.

Note:
    - Use this command after ``cstats_fdr`` to mirror the cluster indices for the other side of the brain before running ``cstats_validation``.  
    - Use -ax 2 and -s 0 for the CCFv3 2020 atlas.
    - Use -ax 0 and -s 2 for the 25 um Gubra atlas (deprecated).

Usage:
------
    cstats_mirror_indices -m <RH or LH> [-p `*``*`/`*`rev_cluster_index.nii.gz] [-ax 2] [-s 0] [-v]
"""

import numpy as np
import nibabel as nib
import shutil
from pathlib import Path
from rich.traceback import install
from concurrent.futures import ThreadPoolExecutor

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.config import Configuration
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg
from unravel.voxel_stats.mirror import mirror

def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-m', '--mas_side', help='Side of the brain corresponding to the mask used for ``vstats`` and ``cstats_fdr`` (RH or LH)', choices=['RH', 'LH'], required=True, action=SM)

    opts = parser.add_argument_group('Optional args')
    opts.add_argument('-p', '--pattern', help='Glob pattern to match files. Default: **/*rev_cluster_index.nii.gz', default='**/*rev_cluster_index.nii.gz', action=SM)
    opts.add_argument('-ax', '--axis', help='Axis to flip the image along. Default: 2', default=2, type=int, action=SM)
    opts.add_argument('-s', '--shift', help='Number of voxels to shift content after flipping. Default: 0', default=0, type=int, action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

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