#!/usr/bin/env python3

import argparse
from rich.traceback import install
from unravel_config import Configuration
from unravel_img_tools import load_3D_img
from unravel_utils import print_cmd_and_times


def parse_args():
    parser = argparse.ArgumentParser(description='Load image (.czi, .nii.gz, or tif series) and get metadata')
    parser.add_argument('-i', '--input', help='path/img.czi, path/img.nii.gz, or path/tif_dir', metavar='')
    parser.add_argument('-c', '--channel', help='.czi channel number. Default: 0 for autofluo', default=0, type=int, metavar='')
    parser.add_argument('-ao', '--axis_order', help='Default: xyz. (other option: zyx)', default='xyz', metavar='')
    parser.add_argument('-x', '--xy_res', help='xy resolution in microns', default=None, type=float, metavar='')
    parser.add_argument('-z', '--z_res', help='z resolution in microns', default=None, type=float, metavar='')
    parser.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)
    return parser.parse_args()


def get_metadata_from_img(img_path, channel=0, desired_axis_order="xyz", xy_res=None, z_res=None):
    """Load image and return metadata. Metadata is saved to parameters/metadata.txt."""
    img, xy_res, z_res, x_dim, y_dim, z_dim = load_3D_img(img_path, channel, desired_axis_order, return_metadata=True, xy_res=xy_res, z_res=z_res)

    print(f'\n\t{img_path} metadata:\n\t\t{img.shape=}\n\t\t{xy_res=}\n\t\t{z_res=}\n\t\t{x_dim=}\n\t\t{y_dim=}\n\t\t{z_dim=}\n')

    # Save metadata to text file
    with open('parameters/metadata.txt', 'w') as f:
        f.write(f"Width:  {x_dim*xy_res} microns ({x_dim})\n")
        f.write(f"Height:  {y_dim*xy_res} microns ({y_dim})\n")
        f.write(f"Depth:  {z_dim*z_res} microns ({z_dim})\n")
        f.write(f"Voxel size: {xy_res}x{xy_res}x{z_res} micron^3\n")

    return img, xy_res, z_res, x_dim, y_dim, z_dim


def main():    
    get_metadata_from_img(args.input, args.channel, args.axis_order, args.xy_res, args.z_res)


if __name__ == '__main__': 
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    print_cmd_and_times(main)()