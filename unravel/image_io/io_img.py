#!/usr/bin/env python3

"""
Use ``io_img`` from UNRAVEL to load a 3D image, [get metadata], and save as the specified image type.

Input image types:
    .czi, .nii.gz, .ome.tif series, .tif series, .h5, .zarr

Output image types: 
    .nii.gz, .tif series, .zarr, .h5

Usage: 
------
    io_img -i path/to/image.czi -x 3.5232 -z 6 [-c 0] [-o path/to/tif_dir] [-d np.uint8] [-r path/to/reference.nii.gz] [-ao zyx] [-v]
"""

from rich.traceback import install

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM

from unravel.core.config import Configuration
from unravel.core.img_io import load_3D_img, save_3D_img
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg

def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-i', '--input', help='path/image .czi, path/img.nii.gz, or path/tif_dir', required=True, action=SM)
    reqs.add_argument('-x', '--xy_res', help='xy resolution in um', required=True, type=float, action=SM)
    reqs.add_argument('-z', '--z_res', help='z resolution in um', required=True, type=float, action=SM)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-c', '--channel', help='.czi channel number. Default: 0 for autofluo', default=0, type=int, action=SM)
    opts.add_argument('-o', '--output', help='Output path (image type determined by extension). Default: None', default=None, action=SM)
    opts.add_argument('-d', '--dtype', help='Data type for .nii.gz. Default: None. Options: np.uint8, np.uint16, np.float32.', default=None, action=SM)
    opts.add_argument('-r', '--reference', help='Reference image for .nii.gz metadata. Default: None', default=None, action=SM)
    opts.add_argument('-ao', '--axis_order', help='Default: xyz. (other option: zyx)', default='xyz', action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

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
    save_3D_img(img, args.output, args.axis_order, xy_res, z_res, args.dtype, args.reference)

    verbose_end_msg()


if __name__ == '__main__':
    main()