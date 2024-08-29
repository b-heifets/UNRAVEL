#!/usr/bin/env python3

"""
Use ``io_nii_to_tifs`` from UNRAVEL to convert an image.nii.gz to tif series in an output_dir.

Usage:
------
    io_nii_to_tifs -i path/image.nii.gz -o path/output_dir [-v]
"""

import os
import nibabel as nib
import numpy as np
import tifffile as tif
from rich.traceback import install

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM

from unravel.core.config import Configuration
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-i', '--input', help='image.nii.gz', required=True, action=SM)
    reqs.add_argument('-o', '--output_dir', help='Name of output folder', required=True, action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()

def nii_to_tifs(nii_path, output_dir):
    # Load the NIfTI file
    nii_image = nib.load(nii_path)
    data = nii_image.get_fdata(dtype=np.float32)

    # Ensure the output directory exists
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Iterate through the slices of the image and save each as a .tif
    for i in range(data.shape[2]):
        slice_ = data[:, :, i]
        slice_ = np.rot90(slice_, 1)  # '1' indicates one 90-degree rotation counter-clockwise
        slice_ = np.flipud(slice_) # Flip vertically
        tif.imwrite(os.path.join(output_dir, f'slice_{i:04d}.tif'), slice_) #not opening in FIJI as one stack


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()
    
    nii_to_tifs(args.input, args.output_dir)

    verbose_end_msg()


if __name__ == '__main__':
    main()