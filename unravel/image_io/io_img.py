#!/usr/bin/env python3

"""
Use ``io_img`` from UNRAVEL to load a 3D image, [get metadata], and save as the specified image type.

Usage: 
------
    io_img -i path/to/image.czi -o path/to/tif_dir

Input image types:
    .czi, .nii.gz, .ome.tif series, .tif series, .h5, .zarr

Output image types: 
    .nii.gz, .tif series, .zarr
"""

import argparse
from rich.traceback import install

from unravel.core.argparse_utils import SuppressMetavar, SM
from unravel.core.config import Configuration
from unravel.core.img_io import load_3D_img, save_as_h5, save_as_nii, save_as_tifs, save_as_zarr
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg

def parse_args():
    parser = argparse.ArgumentParser(formatter_class=SuppressMetavar)
    parser.add_argument('-i', '--input', help='path/image .czi, path/img.nii.gz, or path/tif_dir', required=True, action=SM)
    parser.add_argument('-x', '--xy_res', help='xy resolution in um', required=True, type=float, action=SM)
    parser.add_argument('-z', '--z_res', help='z resolution in um', required=True, type=float, action=SM)
    parser.add_argument('-c', '--channel', help='.czi channel number. Default: 0 for autofluo', default=0, type=int, action=SM)
    parser.add_argument('-o', '--output', help='Output path. Default: None', default=None, action=SM)
    parser.add_argument('-d', '--dtype', help='Data type for .nii.gz. Default: uint16', default='uint16', action=SM)
    parser.add_argument('-r', '--reference', help='Reference image for .nii.gz metadata. Default: None', default=None, action=SM)
    parser.add_argument('-ao', '--axis_order', help='Default: xyz. (other option: zyx)', default='xyz', action=SM)
    parser.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)
    parser.epilog = __doc__
    return parser.parse_args()

# TODO: Test if other scripts in image_io are redundant and can be removed. If not, consolidate them into this script.

@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    # Load image and metadata
    if args.xy_res is None or args.z_res is None:
        img, xy_res, z_res = load_3D_img(args.input, return_res=True)
    else:
        img = load_3D_img(args.input)
        xy_res, z_res = args.xy_res, args.z_res

    # Print metadata
    if args.verbose:
        print(f"\n    Type: {type(img)}")
        print(f"    Image shape: {img.shape}")
        print(f"    Image dtype: {img.dtype}")
        print(f"    xy resolution: {xy_res} um")
        print(f"    z resolution: {z_res} um")

    # Save image    
    if args.output.endswith('.nii.gz'):
        save_as_nii(img, args.output, xy_res, z_res, data_type=args.dtype, reference=args.reference)
    elif args.output.endswith('.zarr'):
        save_as_zarr(img, args.output, ndarray_axis_order=args.axis_order)
    elif args.output.endswith('.h5'):
        save_as_h5(img, args.output, ndarray_axis_order=args.axis_order)
    else: 
        save_as_tifs(img, args.output, ndarray_axis_order=args.axis_order)

    verbose_end_msg()


if __name__ == '__main__':
    main()