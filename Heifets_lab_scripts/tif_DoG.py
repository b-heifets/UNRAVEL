#!/usr/bin/env python3

import argparse
import cv2
import numpy as np
from rich import print
from rich.traceback import install

from argparse_utils import SuppressMetavar, SM


def parse_args():
    parser = argparse.ArgumentParser(description='Perform image background subtraction on a TIFF file.', formatter_class=SuppressMetavar)
    parser.add_argument('-i', '--input', help='Path to the input TIFF file.', required=True, action=SM)
    parser.add_argument('-o', '--output', help='Path to save the output TIFF file.', default=None, action=SM)
    parser.add_argument('-g1', '--sigma1', help='Sigma for the first Gaussian blur in DoG (targets noise)', default=None, required=True, type=float)
    parser.add_argument('-g2', '--sigma2', help='Sigma for the second Gaussian blur in DoG (targets signal).', default=None, required=True, type=float)
    parser.epilog = """Usage: background_subtract_tif.py -i input.tif -g1 1.0 -g2 2.0

Difference of Gaussians:
    - Sigma1 and sigma2 are the standard deviations for the first and second Gaussian blurs
    - Simga2 (the larger blur) should be ~ 1.0 to 1.5 times the radius of these features of interest
        - E.g., if nuclei have a radius of ~1.5 to 2.5 pixels, sigma2 might be 1.5 to 3.0
    - Sigma1 (the smaller blur) should be smaller than the size of the features you want to keep, ideally around the size of the noise
        - E.g., if noise is ~1 pixel in size, sigma1 might be 0.5 to 1
    - The ratio of simga2 to sigma1 should ideally be at least 1.5 to 2. This helps ensure that the blurring difference is significant enough to highlight the features of interest.
"""

    return parser.parse_args()


def load_tif(tif_path):
    '''Load a single tif file using OpenCV and return ndarray.'''
    img = cv2.imread(tif_path, cv2.IMREAD_UNCHANGED)
    if img is None:
        raise FileNotFoundError(f'Could not load the TIFF file from {tif_path}')
    return img

def difference_of_gaussians(img, sigma1, sigma2):
    '''Subtract one blurred version of the image from another to highlight edges.'''
    blur1 = cv2.GaussianBlur(img, (0, 0), sigma1)
    blur2 = cv2.GaussianBlur(img, (0, 0), sigma2)
    dog_img = cv2.subtract(blur1, blur2)
    return dog_img

def save_tif(img, output_path):
    '''Save an image as a tif file.'''
    cv2.imwrite(output_path, img)


def main():
    args = parse_args()

    # Load the image
    img = load_tif(args.tif_path)

    # Apply difference of Gaussians if sigmas are provided
    img = difference_of_gaussians(img, args.sigma1, args.sigma2)
    print(f'Applied Difference of Gaussians with sigmas {args.sigma1} and {args.sigma2}.')

    # Save the processed image
    output_path = args.output if args.output is not None else args.tif_path.replace('.tif', f'_DoG_s1{args.sigma1}_s2{args.sigma2}.tif')
    save_tif(img, output_path)


if __name__ == '__main__': 
    install()
    main()