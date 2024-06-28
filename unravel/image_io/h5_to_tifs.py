#!/usr/bin/env python3

"""
Use ``io_h5_to_tifs`` from UNRAVEL to load a h5/hdf5 image and save it as tifs.

Usage:
------
    io_h5_to_tifs -i path/image.h5 -t autofl

Inputs:
    - image.h5 either from -i path/image.h5 or largest <asterisk>.h5 in cwd
    - This assumes that the first dataset in the hdf5 file has the highest resolution.

Outputs:
    - ./<tif_dir_out>/slice_<asterisk>.tif series
    - ./parameters/metadata (text file)

Next command:
    - ``reg_prep`` for registration
"""

import argparse
import glob
import os
import h5py
import numpy as np
from pathlib import Path
from rich import print
from rich.traceback import install
from tifffile import imwrite 

from unravel.core.argparse_utils import SuppressMetavar, SM
from unravel.core.config import Configuration
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg


def parse_args():
    parser = argparse.ArgumentParser(formatter_class=SuppressMetavar)
    parser.add_argument('-i', '--input', help='path/image.h5', action=SM)
    parser.add_argument('-t', '--tif_dir', help='Name of output folder for outputting tifs', action=SM)
    parser.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)
    parser.epilog = __doc__
    return parser.parse_args()


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

def load_h5(hdf5_path, desired_axis_order="xyz", return_res=False):
    """Load full res image from an HDF5 file (.h5) and return ndarray
    Default: axis_order=xyz (other option: axis_order="zyx")
    Default: returns: ndarray
    If return_res=True returns: ndarray, xy_res, z_res (resolution in um)"""
    with h5py.File(hdf5_path, 'r') as f:
        full_res_dataset_name = next(iter(f.keys()))
        dataset = f[full_res_dataset_name]
        print(f"\n    Loading {full_res_dataset_name} as ndarray")
        ndarray = dataset[:]  # Load the full res image into memory (if not enough RAM, chunck data [e.g., w/ dask array])
        ndarray = np.transpose(ndarray, (2, 1, 0)) if desired_axis_order == "xyz" else ndarray
        print(f'    {ndarray.shape=}')

    if return_res:
        xy_res, z_res = metadata_from_h5(hdf5_path)
        return ndarray, xy_res, z_res
    else:
        return ndarray
    
def metadata_from_h5(hdf5_path):
    """Returns tuple with xy_voxel_size and z_voxel_size in microns from full res HDF5 image"""
    with h5py.File(hdf5_path, 'r') as f:
        # Extract full res HDF5 dataset
        full_res_dataset_name = next(iter(f.keys())) # Assumes that full res data is 1st in the dataset list
        dataset = f[full_res_dataset_name] # Slice the list of datasets
        print(f"    {dataset}")

        # Extract x, y, and z voxel sizes
        res = dataset.attrs['element_size_um'] # z, y, x voxel sizes in microns (ndarray)
        xy_res = res[1]
        z_res = res[0]  
        print(f"    {xy_res=}")
        print(f"    {z_res=}\n")
    return xy_res, z_res

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


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

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

    # Save metadata to text file so resolution can be obtained by other commands/modules
    metadata_txt_path = Path(".", "parameters", "metadata")
    with open(metadata_txt_path, 'w') as file: 
        file.write(f'Voxel size: {xy_res}x{xy_res}x{z_res} micron^3')

    # Save as tifs 
    tifs_output_path = Path(".", args.tif_dir)
    save_as_tifs(img, tifs_output_path)

    verbose_end_msg()
    

if __name__ == '__main__':
    main()