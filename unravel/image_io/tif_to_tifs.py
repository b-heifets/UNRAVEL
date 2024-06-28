#!/usr/bin/env python3

"""
Use ``io_tif_to_tifs`` from UNRAVEL to load a 3D .tif image and save it as tifs.

Usage:
------
    io_tif_to_tifs -i <path/image.tif> -t 488

Inputs: 
    - image.tif # either from -i path/image.tif or largest <asterisk>.tif in cwd

Outputs:
    - ./<tif_dir_out>/slice_<asterisk>.tif series
    - ./parameters/metadata (text file)

Next command: 
    ``reg_prep`` for registration
"""

import argparse
import glob
import os
import numpy as np
from pathlib import Path
from rich import print
from rich.traceback import install
from tifffile import imwrite
import tifffile 

from unravel.core.argparse_utils import SuppressMetavar, SM
from unravel.core.config import Configuration
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg


def parse_args():
    parser = argparse.ArgumentParser(description='Loads 3D .tif image, saves as tifs. Also, saves xy and z voxel size in microns', formatter_class=SuppressMetavar)
    parser.add_argument('-i', '--input', help='path/image.tif', action=SM)
    parser.add_argument('-t', '--tif_dir', help='Name of output folder for outputting tifs', action=SM)
    parser.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)
    parser.epilog = __doc__
    return parser.parse_args()


def find_largest_tif_file():
    """ Find and return the path to the largest .tif file in the current directory """
    largest_file = None
    max_size = -1

    for file in glob.glob('*.tif'):
        size = os.path.getsize(file)
        if size > max_size:
            max_size = size
            largest_file = file

    return largest_file

def load_3D_tif(tif_path, desired_axis_order="xyz", return_res=False):
    """Load full res image from a 3D .tif and return ndarray
    Default: axis_order=xyz (other option: axis_order="zyx")
    Default: returns: ndarray
    If return_res=True returns: ndarray, xy_res, z_res (resolution in um)"""
    with tifffile.TiffFile(tif_path) as tif:
        print(f"\n    Loading {tif_path} as ndarray")
        ndarray = tif.asarray() # Load image into memory (if not enough RAM, chunck data [e.g., w/ dask array])
        ndarray = np.transpose(ndarray, (2, 1, 0)) if desired_axis_order == "xyz" else ndarray
        print(f'    {ndarray.shape=}')

    if return_res:
        xy_res, z_res = metadata_from_3D_tif(tif_path)
        return ndarray, xy_res, z_res
    else:
        return ndarray
    
def metadata_from_3D_tif(tif_path):
    """Returns tuple with xy_voxel_size and z_voxel_size in microns from a 3D .tif"""

    with tifffile.TiffFile(tif_path) as tif:
        # Get the first page of the tif file where the metadata is usually stored
        first_page = tif.pages[0]
        
        # Access the tags dictionary directly
        tags_dict = first_page.tags
        
        # Look for the XResolution tag (tag number 282) # 'XResolution': (numerator, denominator)
        if 282 in tags_dict:
            res_numerator, res_denominator = tags_dict[282].value
            
            # Calculate the resolution in pixels per micron
            resolution = res_numerator / res_denominator

            # Calculate x/y voxel size in microns
            xy_res = 1 / resolution
        else:
            raise ValueError("XResolution tag not found in file.")
        
        # Extract z-step size in microns
        imagej_metadata = tif.imagej_metadata        
        if imagej_metadata and 'spacing' in imagej_metadata:
            z_res = imagej_metadata['spacing']
        else:
            raise ValueError("Z-spacing information not found in ImageJ metadata.")

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
        tif_path = args.input
    else:
        print("\n    [red1]Please provide a path/image.tif for the -t option\n")
        import sys ; sys.exit()

    # Load .tif image (highest res dataset) as ndarray and extract voxel sizes in microns
    img, xy_res, z_res = load_3D_tif(tif_path, desired_axis_order="xyz", return_res=True)

    # Make parameters directory in the sample?? folder
    os.makedirs("parameters", exist_ok=True)

    # Save metadata to text file so resolution can be obtained by other commands/modules
    metadata_txt_path = Path(".", "parameters", "metadata")
    with open(metadata_txt_path, 'w') as file: 
        file.write(f"Voxel size: {xy_res:.4f}x{xy_res:.4f}x{z_res:.4f} µm^3")

    # Save as tifs 
    if args.tif_dir is None:
        print("    [red1]The tif_dir argument was not provided. Please specify the directory.")
        import sys ; sys.exit()
    else:
        tifs_output_path = Path(".", args.tif_dir)
    
    save_as_tifs(img, tifs_output_path)

    verbose_end_msg()


if __name__ == '__main__':
    main()