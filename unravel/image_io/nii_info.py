#!/usr/bin/env python3

"""
Use ``io_nii_info`` (``i``) from UNRAVEL to print NIfTI metadata,
including data type, shape, voxel sizes, orientation, and affine matrix.

Voxel data are only loaded when using -u or -v.

Usage:
------
    i -i path/img.nii.gz [-u] [-v]
"""

from rich import print
from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-i', '--input', help='path/img.nii.gz', action=SM)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-u', '--unique', help='Print unique intensities. Default: False', action='store_true', default=False)
    opts.add_argument('-v', '--verbose', help='Print volume, intensity, and precise voxel size info. Default: False', action='store_true', default=False)

    return parser.parse_args()


def read_header(nii_path):
    """Read only the binary NIfTI-1 or NIfTI-2 header."""
    from gzip import open as gzip_open
    from nibabel import Nifti1Header, Nifti2Header

    opener = gzip_open if nii_path.endswith('.gz') else open

    with opener(nii_path, 'rb') as f:
        prefix = f.read(4)

        header_size = int.from_bytes(prefix, 'little')

        if header_size not in (348, 540):
            header_size = int.from_bytes(prefix, 'big')

        if header_size not in (348, 540):
            raise ValueError(f'Invalid NIfTI header: {nii_path}')

        binary_header = prefix + f.read(header_size - 4)

    header_class = Nifti1Header if header_size == 348 else Nifti2Header

    return header_class(binaryblock=binary_header)


def nii_axis_codes(affine):
    """Return three-letter orientation codes from a NIfTI affine."""
    from nibabel.orientations import aff2axcodes

    return ''.join(code or '?' for code in aff2axcodes(affine))


def main():
    args = parse_args()

    from rich.traceback import install
    from numpy import array2string

    install()

    nii_path = str(args.input)
    if not nii_path.endswith(('.nii', '.nii.gz')):
        nii_path += '.nii.gz'

    # Load voxel data only when needed
    if args.verbose or args.unique:
        from nibabel import load
        from numpy import asanyarray

        nii = load(nii_path)
        header = nii.header
        affine = nii.affine
        img = asanyarray(nii.dataobj)

    else:
        header = read_header(nii_path)
        affine = header.get_best_affine()

    # Print stored data type
    print(f'\nData type: [default bold]{header.get_data_dtype()}[/]')

    # Print intensity range
    if args.verbose:
        print(f'Intensity range: {img.min()} to {img.max()}')

    # Print dimensions
    shape = header.get_data_shape()
    print(f'\nShape (x, y, z): {shape}')

    # Print spatial voxel sizes
    voxel_sizes = tuple(float(v) * 1000 for v in header.get_zooms()[:3])
    voxel_sizes_str = voxel_sizes if args.verbose else tuple(round(v, 1) for v in voxel_sizes)
    print(f'Voxel sizes (µm): {voxel_sizes_str}')

    # Print voxel counts and volumes
    if args.verbose:
        from math import prod
        from numpy import count_nonzero

        num_nonzero = count_nonzero(img)
        num_voxels = img.size

        voxel_volume_mm3 = prod(voxel_sizes) / 1e9
        nonzero_volume_mm3 = voxel_volume_mm3 * num_nonzero
        total_volume_mm3 = voxel_volume_mm3 * num_voxels

        print(f'\nNumber of non-zero voxels: {num_nonzero} out of {num_voxels} ([default bold]{num_nonzero / num_voxels:.2%}[/])')
        print(f'Volume of non-zero voxels: {nonzero_volume_mm3:.2f} out of {total_volume_mm3:.2f} ([default bold]mm^3[/])')

    # Print unique intensities
    if args.unique:
        from unravel.core.img_tools import label_IDs

        uniq_intensities = label_IDs(
            img,
            min_voxel_count=1,
            print_IDs=False,
            print_sizes=False,
        )

        print(f'\nUnique intensities (total: [default bold]{len(uniq_intensities)}[/]):')
        print(uniq_intensities)

    # Print orientation and affine
    axcodes = nii_axis_codes(affine)
    affine_str = array2string(affine, precision=4, suppress_small=True)

    print(f'\nAffine matrix ([default bold]{axcodes}[/]):\n{affine_str}\n')


if __name__ == '__main__':
    main()