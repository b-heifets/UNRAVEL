#!/usr/bin/env python3

"""
Use ``img_rb`` from UNRAVEL to perform rolling ball background subtraction on a TIFF file.

Usage:
------
    img_rb -i input.tif -rb 4 

Rolling ball subtraction:
    - Radius should be ~ 1.0 to 2.0 times the size of the features of interest
    - Larger radii will remove more background, but may also remove some of the features of interest
    - Smaller radii will remove less background, but may leave some background noise

To do: 
    - Add support for other image types and 3D images
"""

import argparse
import cv2
import numpy as np
from rich import print
from rich.traceback import install

from unravel.core.argparse_utils import SuppressMetavar, SM
from unravel.core.config import Configuration
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg


def parse_args():
    parser = argparse.ArgumentParser(formatter_class=SuppressMetavar)
    parser.add_argument('-i', '--input', help='Path to the input TIFF file.', required=True, action=SM)
    parser.add_argument('-o', '--output', help='Path to save the output TIFF file.', default=None, action=SM)
    parser.add_argument('-rb', '--rb_radius', help='Radius of rolling ball in pixels.', default=None, type=int, action=SM)
    parser.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)
    parser.epilog = __doc__
    return parser.parse_args()

# TODO: Add support for other image types and 3D images. 

def load_tif(tif_path):
    '''Load a single tif file using OpenCV and return ndarray.'''
    img = cv2.imread(tif_path, cv2.IMREAD_UNCHANGED)
    if img is None:
        raise FileNotFoundError(f'Could not load the TIFF file from {tif_path}')
    return img

def rolling_ball_subtraction(img, radius):
    '''Subtract background from image using a rolling ball algorithm.'''
    kernel_size = 2 * radius + 1
    struct_element = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size)) # 2D disk
    background = cv2.morphologyEx(img, cv2.MORPH_OPEN, struct_element)
    subtracted_img = cv2.subtract(img, background)
    return subtracted_img

def save_tif(img, output_path):
    '''Save an image as a tif file.'''
    cv2.imwrite(output_path, img)


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    # Load the image
    img = load_tif(args.input)

    # Apply rolling ball subtraction
    img = rolling_ball_subtraction(img, args.rb_radius)
    print(f'Applied rolling ball subtraction with radius {args.rb_radius}.')

    # Save the processed image
    output_path = args.output if args.output is not None else args.input.replace('.tif', f'_rb{args.rb_radius}.tif')
    save_tif(img, output_path)

    verbose_end_msg()


if __name__ == '__main__':
    main()
