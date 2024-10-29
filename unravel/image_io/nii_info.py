#!/usr/bin/env python3

"""
Use ``io_nii_info`` (``i``) from UNRAVEL to load an .nii.gz image and print its data type, shape, voxel sizes, and affine matrix.

Usage:
------
    i -i path/img.nii.gz [-u] [-v]
"""

import nibabel as nib
import numpy as np
from rich import print
from rich.traceback import install

from unravel.core.config import Configuration
from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.img_tools import label_IDs
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-i', '--input', help='path/img.nii.gz', action=SM)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-u', '--unique', help='Print unique intensities. Default: False', action='store_true', default=False)
    opts.add_argument('-v', '--verbose', help='Print volume and intenisty info. Default: False', action='store_true', default=False)

    return parser.parse_args()


def nii_axis_codes(nii):
    """Get and return axes codes (three letter orientation like RAS) from an nibabel NIfTI image"""
    axcodes_tuple = nib.orientations.aff2axcodes(nii.affine) 
    axcodes = ''.join(axcodes_tuple) 
    return axcodes


def main():
    install()
    args = parse_args()

    nii_path = args.input if str(args.input).endswith(".nii.gz") else f"{args.input}.nii.gz"
    nii = nib.load(nii_path)
    
    np.set_printoptions(precision=2, suppress=True)

    # Print data type
    data_type = nii.get_data_dtype()
    print(f'\nData type: [default bold]{data_type}')

    # Print intensity range
    if args.verbose:
        img = np.asanyarray(nii.dataobj, dtype=nii.header.get_data_dtype()).squeeze()
        max_intensity = img.max()
        min_intensity = img.min()
        print(f'Intensity range: {min_intensity} to {max_intensity}')

    # Print dimensions
    print(f'\nShape (x, y, z): {nii.shape}')

    # Print the voxel sizes
    voxel_sizes = nii.header.get_zooms()
    voxel_sizes = tuple(np.array(voxel_sizes) * 1000)
    print(f'Voxel sizes (µm): {voxel_sizes}')

    # Print number of non-zero voxels and total number of voxels
    if args.verbose:
        num_nonzero = np.count_nonzero(img)
        num_voxels = np.prod(img.shape)
        nonzero_volume_in_mm = (voxel_sizes[0] * voxel_sizes[1] * voxel_sizes[2]) * num_nonzero / 1e9
        total_volume_in_mm = (voxel_sizes[0] * voxel_sizes[1] * voxel_sizes[2]) * num_voxels / 1e9
        print(f'\nNumber of non-zero voxels: {num_nonzero} out of {num_voxels} ([default bold]{num_nonzero / num_voxels:.2%}[/])')
        print(f'Volume of non-zero voxels: {nonzero_volume_in_mm:.2f} out of {total_volume_in_mm:.2f} ([default bold]mm^3[/])')

    # Print number of unique intensities
    if args.unique:
        if not 'img' in locals():
            img = np.asanyarray(nii.dataobj, dtype=nii.header.get_data_dtype()).squeeze()
        uniq_intensities = label_IDs(img, min_voxel_count=1, print_IDs=False, print_sizes=False)
        print(f'\nUnique intensities (total: [default bold]{len(uniq_intensities)}):')
        uniq_intensities = label_IDs(img, min_voxel_count=1, print_IDs=True, print_sizes=False)

    # Print orientation and affine
    axcodes = nii_axis_codes(nii)
    np.set_printoptions(precision=4, suppress=True)
    print(f'\nAffine matrix ([default bold]{axcodes}[/]):\n{nii.affine}\n')


if __name__ == '__main__':
    main()