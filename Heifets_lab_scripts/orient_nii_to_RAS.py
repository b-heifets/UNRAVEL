#!/usr/bin/env python3

import argparse
from pathlib import Path
import nibabel as nib
from rich.traceback import install
from unravel_config import Configuration
from unravel_utils import print_cmd_and_times, print_func_name_args_times


def parse_args():
    parser = argparse.ArgumentParser(description='Reorient .nii.gz to RAS standard if needed')
    parser.add_argument('-i', '--input', help='path/img.nii.gz', metavar='')
    parser.add_argument('-o', '--output', help='path/img.nii.gz. Default: path/img_RAS.nii.gz', metavar='')
    parser.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)
    return parser.parse_args()


print_func_name_args_times()
def reorient_to_RAS(image_path):
    # Load the image
    img = nib.load(image_path)

    # Get the current orientation
    current_orientation = nib.aff2axcodes(img.affine)
    print(f"Current orientation: {current_orientation}")

    # Check if the image is in RAS orientation
    if current_orientation != ('R', 'A', 'S'):
        print("Reorienting to RAS...")
        # Reorient the image to RAS
        ras_img = nib.as_closest_canonical(img)
        return ras_img
    else:
        print("Image is already in RAS orientation.")
        return img


def main():    

    # Reorient according to NIfTI convention    
    img = reorient_to_RAS(args.input)

    # Save reoriented .nii.gz
    if args.output:
        output = args.output
    else: 
        output = str(args.input).replace(".nii.gz", "_RAS.nii.gz")
    nib.save(img, output)


if __name__ == '__main__': 
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    print_cmd_and_times(main)()