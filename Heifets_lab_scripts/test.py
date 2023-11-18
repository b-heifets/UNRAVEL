#!/usr/bin/env python3

import argparse
from argparse import RawTextHelpFormatter
import numpy as np
from rich.traceback import install
from unravel_config import Configuration
from unravel_img_tools import load_3D_img
from unravel_utils import print_cmd_and_times


def parse_args():
    parser = argparse.ArgumentParser(description='Load image (.czi, .nii.gz, or tif series)  and get metadata', formatter_class=RawTextHelpFormatter)
    parser.add_argument('-i', '--input', help='path/img.czi, path/img.nii.gz, or path/tif_dir', metavar='')
    parser.add_argument('-s', '--seg', help='path/seg.czi, path/img.nii.gz, or path/tif_dir', metavar='')
    parser.add_argument('-x', '--xy_res', help='xy resolution in um', type=float, metavar='')
    parser.add_argument('-z', '--z_res', help='z resolution in um', type=float, metavar='')
    parser.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)
    return parser.parse_args()

def main():    
    if args.xy_res is None or args.z_res is None:
        img, xy_res, z_res = load_3D_img(args.input, return_res=True)
    else:
        img = load_3D_img(args.input, return_res=True)
        xy_res, z_res = args.xy_res, args.z_res

    if args.xy_res is None or args.z_res is None:
        seg, xy_res, z_res = load_3D_img(args.seg, return_res=True)
    else:
        seg = load_3D_img(args.seg, return_res=True)
        xy_res, z_res = args.xy_res, args.z_res

    
    # Binarize segmentation
    seg_bin = (seg > 0).astype(int)

    num_nonzero_voxels = np.count_nonzero(seg_bin)

    print(f'\n{num_nonzero_voxels=}\n')


    # Zero out voxels outside of the cluster and segmented cells
    IF_in_seg_img = seg_bin * img

    # Calculate the mean intensity of the non-zero voxels
    mean_intensity = np.mean(IF_in_seg_img[IF_in_seg_img > 0])
    print(f'\n    Mean: {mean_intensity}\n')


if __name__ == '__main__': 
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    print_cmd_and_times(main)()