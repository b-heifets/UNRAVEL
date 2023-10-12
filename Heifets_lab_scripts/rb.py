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
from warp_to_atlas import warp_to_atlas

def parse_args():
    parser = argparse.ArgumentParser(description='Load channel(s) of *.czi (default) or ./<tif_dir(s)>/*.tif, rolling ball bkg sub, resample, reorient, and save as ./sample??_ochann_rb4_gubra_space.nii.gz')
    parser.add_argument('--dir_pattern', help='Pattern for folders in working dir to process (Default: sample??)', default='sample??', metavar='')
    parser.add_argument('--dir_list', help='Folders to process in working dir (e.g., sample01 sample02) (Default: process sample??) ', nargs='+', default=None, metavar='')
    parser.add_argument('--channels', help='.czi channel number(s) (e.g., 1 2; Default: 1)', nargs='+', default=1, type=int, metavar='')
    parser.add_argument('--chann_name', help='Name(s) of channels for saving (e.g., tdT cFos; for tifs place in ./sample??/<cFos>/; Default: ochann)', nargs='+', default="ochann", metavar='')
    parser.add_argument('-o', '--output', help='Output file name (Default: sample??_ochann_rb4_gubra_space.nii.gz)', default=None, metavar='')
    parser.add_argument('-rb', '--rb_radius', help='Radius of rolling ball in pixels (Default: 4)', default=4, type=int, metavar='')
    parser.add_argument('-x', '--xy_res', help='x/y voxel size in microns (Default: get via metadata)', default=None, type=float, metavar='')
    parser.add_argument('-z', '--z_res', help='z voxel size in microns (Default: get via metadata)', default=None, type=float, metavar='')
    parser.add_argument('-r', '--res', help='Resample to this resolution in microns (Default: 25)', default=25, type=int, metavar='')
    parser.add_argument('-zo', '--zoom_order', help='Order of spline interpolation. Range: 0-5. (Default: 1))', default=1, type=int, metavar='')
    parser.add_argument('-a', '--atlas_name', help='Name of atlas (Default: gubra)', default="gubra", metavar='')
    parser.add_argument('-t', '--tif_dir', help='Name of folder with raw autofluo tifs (alternate input image)', default=None, metavar='')
    return parser.parse_args()

@unrvl.print_func_name_args_times()
def rb_resample_reorient_warp(sample_dir, args=None):

    # Iterate through each channel in args.channels
    for i, channel in enumerate(args.channels):

        # Get the channel name; if multiple names provided, get the corresponding one
        channel_name = args.chann_name[i] if isinstance(args.chann_name, list) else args.chann_name

        # Check if the output file already exists
        output_path = Path(f"{sample_dir}_{channel_name}_rb{args.rb_radius}_{args.atlas_name}_space.nii.gz")
        if output_path.exists():
            print(f"\n\n  [gold3]{output_path}[/] already exists. Skipping.\n")
            continue # Skip to next channel

        czi_files = glob(f"{sample_dir}/*.czi")
        if czi_files:
            czi_path = Path(czi_files[0]).resolve()
            img = unrvl.load_czi_channel(czi_path, channel)

            if args.xy_res is None or args.z_res is None:
                xy_res_metadata, z_res_metadata = unrvl.xyz_res_from_czi(czi_path)

        elif args.tif_dir:
            tif_dir_path = Path(sample_dir, args.tif_dir)
            tif_files = glob(f"{tif_dir_path}/*.tif")

            if not tif_files:
                print(f"\n  [red]No .tif files found in {tif_dir_path}/. Skipping this directory.")
                continue 

            path_to_first_tif = tif_files[0]
            img = unrvl.load_tifs(tif_dir_path)

            if args.xy_res is None or args.z_res is None:
                xy_res_metadata, z_res_metadata = unrvl.xyz_res_from_tif(path_to_first_tif)

        if img is None:
            print(f"\n  [red]No .czi file found and tif_dir is not specified\n")
            return
                
        # Rolling ball background subtraction
        img_bkg = rolling_ball(img, radius=args.rb_radius, nansafe=True) # returns the estimated background
        rb_bkg_sub_img = img - img_bkg

        # Convert to 

        # Resample image
        # Resample CLARITY to Allen resolution
        # ResampleImage 3 ${inimg} ${res_vox} 0.025x0.025x0.025 0
        print(f"\n  [default]Image shape: {img.shape}\n  Channel: {channel}\n")
        args.xy_res = args.xy_res or xy_res_metadata # If xy_res is None, use xy_res_metadata
        args.z_res = args.z_res or z_res_metadata
        zf_xy = args.xy_res / args.res # Zoom factor
        zf_z = args.z_res / args.res
        resampled_rb_img = ndimage.zoom(rb_bkg_sub_img, (zf_xy, zf_xy, zf_z), order=args.zoom_order)

        # Reorient image
        # Orient CLARITY to standard orientation
        # PermuteFlipImageOrientationAxes 3 ${res_vox} ${swp_vox}  1 2 0  0 0 0

        # Orient CLARITY to standard orientation
        # c3d ${swp_vox} -orient ${orttagclar} -pad 15% 15% 0 -interpolation ${ortintclar} -type ${orttypeclar} -o ${ortclar}
        reoriented_rb_img = np.flip(np.einsum('zyx->xzy', resampled_rb_img), axis=1)

        # Get original dim
        # org_dim=`PrintHeader ${ortclar} 2`

        # Resample to original resolution
        # ResampleImage 3 ${org_clar} ${res_org_clar} ${org_dim} 1

        # Copy original transform
        # c3d ${res_org_clar} ${ortclar} -copy-transform -type ${orttypeclar} -o ${cp_clar}

        # Combine deformation fields and transformations 
        # antsApplyTransforms -d 3 -r ${init_allen} -t ${antswarp} [ ${antsaff}, 1 ] -o [ ${comb_def}, 1 ]

        # "Applying ants deformations to CLARITY data" 
        # antsApplyTransforms -d 3 -r ${allenref} -i ${cp_clar} -n Bspline -t [ ${initform}, 1 ] ${comb_def} -o ${wrpclar}


        # Warp image to atlas space
        warped_img = warp_to_atlas(reoriented_rb_img, args.atlas_name, args.res)

        # Rename the saved file
        output = f"{sample_dir}_{channel_name}_rb{args.rb_radius}_{args.atlas_name}_space.nii.gz"
        os.rename(warped_img, output)


@unrvl.print_cmd_and_times
def main():
    args = parse_args()

    # Ensure args.channels and args.chann_name are always lists
    if not isinstance(args.channels, list):
        args.channels = [args.channels]
    if not isinstance(args.chann_name, list):
        args.chann_name = [args.chann_name]

    unrvl.process_samples_in_dir(rb_resample_reorient_warp, sample_list=args.dir_list, sample_dirs_pattern=args.dir_pattern, args=args)


if __name__ == '__main__':
    main()