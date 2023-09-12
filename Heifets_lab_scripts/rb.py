#!/usr/bin/env python3

import argparse
import os
import numpy as np
import unravel_utils as unrvl
from glob import glob
from pathlib import Path
from rich import print
from scipy import ndimage
from skimage.restoration import rolling_ball
from warp_to_atlas import warp_to_atlas as warp_to_atlas_func

def parse_args():
    parser = argparse.ArgumentParser(description='Load channel(s) of *.czi (default) or ./<tif_dir(s)>/*.tif, rolling ball bkg sub, resample, reorient, and save as ./sample??_ochann_rb4_gubra_space.nii.gz')
    parser.add_argument('--dir_pattern', help='Pattern for folders in working dir to process (Default: sample??)', default='sample??', metavar='')
    parser.add_argument('--dir_list', help='Folders to process in working dir (e.g., sample01 sample02) (Default: process sample??) ', nargs='+', default=None, metavar='')
    parser.add_argument('--channels', help='.czi channel number(s) (e.g., 1 2; Default: 1)', nargs='+', default=1, type=int, metavar='')
    parser.add_argument('--chann_name', help='Name(s) of channels for saving (e.g., tdT cFos; for tifs place in ./sample??/<cFos>/; Default: ochann)', nargs='+', default="ochann", type=int, metavar='')
    parser.add_argument('-r', '--rb_radius', help='Radius of rolling ball in pixels (Default: 4)', default=4, type=int, metavar='')
    parser.add_argument('-x', '--xy_res', help='x/y voxel size in microns (Default: get via metadata)', default=None, type=float, metavar='')
    parser.add_argument('-z', '--z_res', help='z voxel size in microns (Default: get via metadata)', default=None, type=float, metavar='')
    parser.add_argument('-r', '--res', help='Resample to this resolution in microns (Default: 50)', default=50, type=int, metavar='')
    parser.add_argument('-zo', '--zoom_order', help='Order of spline interpolation. Range: 0-5. (Default: 1))', default=1, type=int, metavar='')
    parser.add_argument('-a', '--atlas_name', help='Name of atlas (Default: gubra)', default="gubra", metavar='')
    return parser.parse_args()

@unrvl.print_func_name_args_status_duration()
def rb_resample_reorient_warp(sample_dir, args=None):

    # Iterate through each channel in args.channels
    for i, channel in enumerate(args.channels):

        # Get the channel name; if multiple names provided, get the corresponding one
        channel_name = args.chann_name[i] if isinstance(args.chann_name, list) else args.chann_name

        # Check if the output file already exists
        output_path = Path(f"{sample_dir}_{channel_name}_rb{args.rb_radius}_{args.atlas_name}_space.nii.gz")
        if output_path.exists():
            print(f"\n\n  [gold3]{output_path}[/] already exists. Skipping.\n")
            return

        czi_path = glob(f"{sample_dir}/*.czi")
        if czi_path:
            img = unrvl.load_czi_channel(czi_path, channel)

            # Get voxel size from metadata
            if args.xy_res is None or args.z_res is None:
                xy_res_metadata, z_res_metadata = unrvl.xyz_res_from_czi(czi_path)

        else:
            tif_dir_path = Path(sample_dir, channel_name)
            img = unrvl.load_tif_series(tif_dir_path)

            # Get voxel size from metadata
            if args.xy_res is None or args.z_res is None:
                path_to_first_tif = glob(f"{sample_dir}/{args.tif_dir}/*.tif")[0]
                xy_res_metadata, z_res_metadata = unrvl.xyz_res_from_tif(path_to_first_tif)

        if img is None:
            print(f"\n  [red]No .czi files found and tif_dir is not specified for {sample_dir}[/]\n")
            return
        
        # Rolling ball background subtraction
        img_rb_subtracted = rolling_ball(img, radius=args.rb_radius)

        # Resample image
        args.xy_res = args.xy_res or xy_res_metadata # If xy_res is None, use xy_res_metadata
        args.z_res = args.z_res or z_res_metadata
        zf_xy = args.xy_res / args.res # Zoom factor
        zf_z = args.z_res / args.res
        img_resampled = ndimage.zoom(img_rb_subtracted, (zf_xy, zf_xy, zf_z), order=args.zoom_order)

        # Reorient image
        img_reoriented = np.flip(np.einsum('zyx->xzy', img_resampled), axis=1)

        # Warp image to atlas space
        warped_img = warp_to_atlas_func(img_reoriented, args.atlas_name, args.res)

        # Rename the saved file
        output = f"{sample_dir}_{channel_name}_rb{args.rb_radius}_{args.atlas_name}_space.nii.gz"
        os.rename(warped_img, output)


@unrvl.print_cmd_and_times
def main():
    args = parse_args()

    unrvl.process_samples_in_dir(rb_resample_reorient_warp, sample_list=args.dir_list, sample_dirs_pattern=args.dir_pattern, args=args)


if __name__ == '__main__':
    main()