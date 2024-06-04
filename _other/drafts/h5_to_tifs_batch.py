#!/usr/bin/env python3

import argparse
import glob
import os
import numpy as np
from pathlib import Path
from rich import print
from rich.traceback import install
from tifffile import imwrite 

from unravel.image_io.h5_to_tifs import load_h5
from unravel.core.argparse_utils import SuppressMetavar, SM
from unravel.core.config import Configuration
from unravel.core.utils import print_cmd_and_times


def parse_args():
    parser = argparse.ArgumentParser(description='Loads h5/hdf5 image, saves as tifs. Also, saves xy and z voxel size in microns', formatter_class=SuppressMetavar)
    parser.add_argument('-p', '--pattern', help='Pattern for folders to process. If no matches, use current dir. Default: sample??', default='sample??', action=SM)
    parser.add_argument('--dirs', help='List of folders to process.', nargs='*', default=None, action=SM)
    parser.add_argument('-i', '--input', help='path/image.h5', action=SM)
    parser.add_argument('-t', '--tif_dir', help='Name of output folder for outputting tifs', action=SM)
    parser.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)
    parser.epilog = """Run script from experiment folder w/ sample?? folders or a sample?? folder.

Example usage: 
h5_to_tifs.py -i <path/image.h5> -t 488

Inputs: 
Largest *.h5 in sample?? folder
This script assumes that the first dataset in the hdf5 file has the highest resolution.

Outputs:
./<tif_dir_out>/slice_????.tif series
./parameters/metadata (text file)

Next script: 
prep_reg.sh
"""
    return parser.parse_args()

# TODO: Add logic for processing all sample folders


def find_largest_h5_file():
    """ Find and return the path to the largest .h5 file in the current directory """
    largest_file = None
    max_size = -1

    for file in glob.glob('*.h5'):
        size = os.path.getsize(file)
        if size > max_size:
            max_size = size
            largest_file = file

    return largest_file


    


def save_as_tifs(ndarray, tif_dir_out, ndarray_axis_order="xyz"):
    """Save <ndarray> as tifs in <Path(tif_dir_out)>"""
    tif_dir_out = Path(tif_dir_out)
    tif_dir_out.mkdir(parents=True, exist_ok=True)

    if ndarray_axis_order == "xyz":
        ndarray = np.transpose(ndarray, (2, 1, 0)) # Transpose to zyx (tiff expects zyx)
    for i, slice_ in enumerate(ndarray):
        slice_file_path = tif_dir_out / f"slice_{i:04d}.tif"
        imwrite(str(slice_file_path), slice_)
    print(f"    Output: [default bold]{tif_dir_out}\n")


def main():
    args = parse_args()

    if args.input: 
        h5_path = args.input
    else: 
        h5_path = find_largest_h5_file()
        if h5_path:
            print(f"\n    The largest .h5 file is: {h5_path}")
        else:
            print("\n    [red1]No .h5 files found.\n")

    # Load h5 image (highest res dataset) as ndarray and extract voxel sizes in microns
    img, xy_res, z_res = load_h5(h5_path, desired_axis_order="xyz", return_res=True)

    # Make parameters directory in the sample?? folder
    os.makedirs("parameters", exist_ok=True)

    # Save metadata to text file so resolution can be obtained by other scripts
    metadata_txt_path = Path(".", "parameters", "metadata")
    with open(metadata_txt_path, 'w') as file: 
        file.write(f'Voxel size: {xy_res}x{xy_res}x{z_res} micron^3')

    # Save as tifs 
    tifs_output_path = Path(".", args.tif_dir)
    save_as_tifs(img, tifs_output_path)


if __name__ == '__main__':
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    print_cmd_and_times(main)()