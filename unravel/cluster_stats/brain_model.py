#!/usr/bin/env python3

import argparse
import nibabel as nib
import numpy as np
import pandas as pd
from pathlib import Path
from rich import print
from rich.traceback import install

from unravel.core.argparse_utils import SuppressMetavar, SM
from unravel.core.config import Configuration 
from unravel.core.utils import print_cmd_and_times
from voxel_stats.mirror import mirror


def parse_args():
    parser = argparse.ArgumentParser(description='Prep .nii.gz and RGBA .txt for vizualization in dsi_studio', formatter_class=SuppressMetavar)
    parser.add_argument('-i', '--input', help="path/img.nii.gz (e.g., valid cluster index)", required=True, action=SM)
    parser.add_argument('-m', '--mirror', help='Mirror the image in the x-axis for a bilateral representation. Default: False', action='store_true', default=False)
    parser.add_argument('-ax', '--axis', help='Axis to flip the image along. Default: 0', default=0, type=int, action=SM)
    parser.add_argument('-s', '--shift', help='Number of voxels to shift content after flipping. Default: 2', default=2, type=int, action=SM)
    parser.add_argument('-sa', '--split_atlas', help='path/gubra_ano_split_25um.nii.gz. Default: gubra_ano_split_25um.nii.gz', default='gubra_ano_split_25um.nii.gz', action=SM)
    parser.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)
    parser.epilog = """Example usage: 3D_brain.py -i input.csv

The input image will be binarized and multiplied by the split atlas to apply region IDs.

Outputs: 
img_WB.nii.gz (bilateral version of cluster index w/ ABA colors)

"""
    
    return parser.parse_args()


def main():
    args = parse_args()

    if args.mirror:
        output = args.input.replace('.nii.gz', '_ABA_WB.nii.gz')
    else:
        output = args.input.replace('.nii.gz', '_ABA.nii.gz')
        
    txt_output = args.input.replace('.nii.gz', '_rgba.txt')

    if Path(output).exists() and Path(txt_output).exists():
        print(f'{output} and {Path(txt_output).name} exist. Skipping.')
        return
        

    # Load the input NIFTI file
    nii = nib.load(args.input)
    img = np.asanyarray(nii.dataobj, dtype=nii.header.get_data_dtype()).squeeze()

    # Make a bilateral version of the cluster index
    if args.mirror:
        mirror_img = mirror(img, axis=args.axis, shift=args.shift)

        # Combine original and mirrored images
        img = img + mirror_img

    # Binarize
    img[img > 0] = 1

    # Multiply by atlas to apply region IDs to the cluster index
    atlas_nii = nib.load(args.split_atlas)
    atlas_img = np.asanyarray(atlas_nii.dataobj, dtype=atlas_nii.header.get_data_dtype()).squeeze()
    final_data = img * atlas_img

    # Save the bilateral version of the cluster index with ABA colors

    nib.save(nib.Nifti1Image(final_data, atlas_nii.affine, atlas_nii.header), output)

    # Calculate and save histogram
    histogram, _ = np.histogram(final_data, bins=21144, range=(0, 21144))

    # Exclude the background (region 0) from the histogram
    histogram = histogram[1:]

    # Determine what regions are present based on the histogram
    present_regions = np.where(histogram > 0)[0] + 1 # Add 1 to account for the background

    # Get R, G, B values for each region
    color_map = pd.read_csv(Path(__file__).parent.parent / 'unravel' / 'csvs' / 'regional_summary.csv') #(Region_ID,ID_Path,Region,Abbr,General_Region,R,G,B)

    # Delete rgba.txt if it exists (used for coloring the regions in DSI Studio)
    
    if Path(txt_output).exists():
        Path(txt_output).unlink()

    # Determine the RGB color for bars based on the region_id
    for region_id in present_regions:
        combined_region_id = region_id if region_id < 20000 else region_id - 20000
        region_rgb = color_map[color_map['Region_ID'] == combined_region_id][['R', 'G', 'B']]

        # Convert R, G, B values to space-separated R G B A values (one line per region)
        rgba_str = ' '.join(region_rgb.astype(str).values[0]) + ' 255'

        # Save the RGBA values to a .txt file
        with open(txt_output, 'a') as f:
            f.write(rgba_str + '\n')


if __name__ == '__main__':
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    print_cmd_and_times(main)()