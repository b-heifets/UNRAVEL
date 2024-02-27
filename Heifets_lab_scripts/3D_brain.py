#!/usr/bin/env python3

import argparse
import numpy as np
import pandas as pd
from pathlib import Path
from rich import print
from rich.traceback import install

from argparse_utils import SuppressMetavar, SM
from unravel_config import Configuration 
from unravel_img_io import load_3D_img, save_as_nii
from unravel_utils import print_cmd_and_times


def parse_args():
    parser = argparse.ArgumentParser(description='Prep .nii.gz and RGBA .txt for vizualization in dsi_studio', formatter_class=SuppressMetavar)
    parser.add_argument('-i', '--input', help="path/valid_cluster_index.nii.gz", required=True, action=SM)
    parser.add_argument('-m', '--mirror', help='Mirror the image in the x-axis for a bilateral representation. Default: False', action='store_true', default=False)
    parser.add_argument('-n', '--nudge', help='Nudge two pixels to the left. Default: 2 (for 25 um Gubra atlas space data)', default=2, type=int, action=SM)
    parser.add_argument('-d', '--direction', help='Default is to nudge left', default=None, choices=[None, '-'], action=SM)
    parser.add_argument('-a', '--atlas', help='path/gubra_ano_split_25um.nii.gz. Default: gubra_ano_split_25um.nii.gz', default='gubra_ano_split_25um.nii.gz', action=SM)
    parser.add_argument('-r', '--res', help='x/y/z resolution of input/atlas in microns. Default: 25', default=25, type=int, action=SM)
    parser.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)
    parser.epilog = """Example usage: dsi_lut.py -i input.csv

Outputs: 
input_WB.nii.gz (bilateral version of cluster index w/ ABA colors)

"""
    
    return parser.parse_args()


def main():
    args = parse_args()

    # Load the input NIFTI file
    img = load_3D_img(args.input)
    
    if args.mirror:
        # Mirror the image in the x-axis for a bilateral representation
        mirror_img = np.flip(img, axis=0)

        # Nudge two pixels to the left (required for data in 25 um Gubra atlas space)
        if args.nudge:
            if args.direction == '-':
                nudge = -args.nudge
            else:
                nudge = args.nudge
            mirror_img = np.roll(mirror_img, nudge, axis=0)
            mirror_img[:args.nudge, :, :] = 0 # Make sure the image does not "wrap around"

        # Combine original and mirrored images
        img = img + mirror_img

    # Binarize
    img[img > 0] = 1

    # Multiply by atlas to apply region IDs to the cluster index
    atlas_img = load_3D_img(args.atlas)
    final_data = img * atlas_img

    # Save the bilateral version of the cluster index with ABA colors
    if args.mirror:
        output = args.input.replace('.nii.gz', '_ABA_WB.nii.gz')
    else:
        output = args.input.replace('.nii.gz', '_ABA.nii.gz')
    save_as_nii(final_data, output, xy_res=args.res, z_res=args.res, data_type=atlas_img.dtype, reference=args.atlas)

    # Calculate and save histogram
    histogram, _ = np.histogram(final_data, bins=21144, range=(0, 21144))

    # Exclude the background (region 0) from the histogram
    histogram = histogram[1:]

    # Determine what regions are present based on the histogram
    present_regions = np.where(histogram > 0)[0] + 1 # Add 1 to account for the background

    # Get R, G, B values for each region
    color_map = pd.read_csv(Path(__file__).parent / 'regional_summary.csv') #(Region_ID,ID_Path,Region,Abbr,General_Region,R,G,B)

    # Determine the RGB color for bars based on the region_id
    for region_id in present_regions:
        combined_region_id = region_id if region_id < 20000 else region_id - 20000
        region_rgb = color_map[color_map['Region_ID'] == combined_region_id][['R', 'G', 'B']]

        # Convert R, G, B values to space-separated R G B A values (one line per region)
        txt_output = str(Path(args.input).parent / "rgba.txt")
        rgba_str = ' '.join(region_rgb.astype(str).values[0]) + ' 255'
        with open(txt_output, 'a') as f:
            f.write(rgba_str + '\n')
    
    print(f"\n    Output: [default bold]{txt_output}")



if __name__ == '__main__':
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    print_cmd_and_times(main)()