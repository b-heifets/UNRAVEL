#!/usr/bin/env python3

import argparse
import nibabel as nib
import numpy as np

def parse_args():
    parser = argparse.ArgumentParser(description='Print list of IDs for clusters > X voxels')
    parser.add_argument('-i', '--input', help='path/input_img.nii.gz', required=True, metavar='')
    parser.add_argument('-s', '--print_sizes', help='Optionally print cluster IDs and sizes if flag is provided', action='store_true')
    parser.add_argument('-m', '--minextent', help='Min cluster size in voxels (Default: 100)', default=100, metavar='', type=int)
    return parser.parse_args()

def uniq_intensities(image, minextent, print_sizes=False):
    # Load the image
    img = nib.load(image)
    data = img.get_fdata()

    # Get unique intensities and their counts
    unique_intensities, counts = np.unique(data[data > 0], return_counts=True)

    # Filter clusters based on size
    clusters_above_minextent = [intensity for intensity, count in zip(unique_intensities, counts) if count >= minextent]
    
    # Print cluster IDs
    for idx, cluster_id in enumerate(clusters_above_minextent):
        if print_sizes:
            print(f"ID: {int(cluster_id)}, Size: {counts[idx]}")
        else:
            print(int(cluster_id), end=' ')
    if not print_sizes:
        print()

def main():
    args = parse_args()
    uniq_intensities(args.input, args.minextent, args.print_sizes)

if __name__ == '__main__':
    main()
