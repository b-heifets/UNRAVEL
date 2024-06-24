#!/usr/bin/env python3

import argparse
import h5py
from rich import print
from rich.traceback import install

from unravel.core.argparse_utils import SuppressMetavar, SM
from unravel.core.config import Configuration
from unravel.core.img_io import load_3D_img
from unravel.core.utils import print_cmd_and_times, print_func_name_args_times

def parse_args():
    parser = argparse.ArgumentParser(description='Convert images to HDF5 format for ilastik processing.', formatter_class=SuppressMetavar)
    parser.add_argument('-i', '--input', required=True, help='Input image file path (.czi, .nii.gz, .tif)', action=SM)
    parser.add_argument('-o', '--output', required=True, help='Output HDF5 file path', action=SM)
    parser.add_argument('-v', '--verbose', help='Increase verbosity.', action='store_true', default=False)
    return parser.parse_args()

@print_func_name_args_times()
def save_image_as_hdf5(ndarray, output):
    with h5py.File(output, 'w') as f:
        f.create_dataset('data', data=ndarray, compression="lzf")
        if args.verbose:
            print(f"Image saved to HDF5 dataset: {output}")


def main():
    args = parse_args()

    img = load_3D_img(args.input, desired_axis_order="zyx") # Ensure the image is in the correct axis order for ilastik

    if args.output: 
        output = args.output
    elif args.input.endswith('.czi'):
        output = args.input.replace('.czi', '.h5')
    elif args.input.endswith('.nii.gz'):
        output = args.input.replace('.nii.gz', '.h5')
    elif args.input.endswith('.tif'):
        output = args.input.replace('.tif', '.h5')
    elif args.input.endswith('.zarr'):
        output = args.input.replace('.zarr', '.h5')

    save_image_as_hdf5(img, output)


if __name__ == '__main__':
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    print_cmd_and_times(main)()