#!/usr/bin/env python3

import argparse
import nibabel as nib
import numpy as np
import unravel_utils as unrvl
from aicspylibczi import CziFile
from glob import glob
from metadata import get_metadata_from_czi
from pathlib import Path
from rich import print
from scipy import ndimage
from tifffile import imread, imwrite


def parse_args():
    parser = argparse.ArgumentParser(description='Load channel of *.czi (default) or ./<tif_dir>/*.tif, resample, reorient, and save as ./niftis/<img>.nii.gz')
    parser.add_argument('--dir_pattern', help='Pattern for folders in working dir to process (Default: sample??)', default='sample??', metavar='')
    parser.add_argument('--dir_list', help='Folders to process in working dir (e.g., sample01 sample02) (Default: process sample??) ', nargs='+', default=None, metavar='')
    parser.add_argument('-t', '--tif_dir', help='Name of folder with autofluo tifs', default=None, metavar='')
    parser.add_argument('-c', '--channel', help='Channel number (Default: 0 for 1st channel [usually autofluo])', default=0, type=int, metavar='')
    parser.add_argument('-x', '--xy_res', help='x/y voxel size in microns (Default: get via metadata)', default=None, type=float, metavar='')
    parser.add_argument('-z', '--z_res', help='z voxel size in microns (Default: get via metadata)', default=None, type=float, metavar='')
    parser.add_argument('-r', '--res', help='Resample to this resolution in microns (Default: 50)', default=50, type=int, metavar='')
    parser.add_argument('-zo', '--zoom_order', help='Order of spline interpolation. Range: 0-5. (Default: 1))', default=1, type=int, metavar='')
    return parser.parse_args()


@unrvl.print_func_name_args_status_duration()
def resample_reorient(sample_dir, args=None):

    # Load autofluo image
    czi_path = glob(f"{sample_dir}/*.czi")    
    if czi_path:
        czi_path = czi_path[0]
        czi = CziFile(czi_path)
        img = czi.read_image(C=args.channel)[0]
        img = np.squeeze(img)
        img = np.transpose(img, (2, 1, 0))
    elif args.tif_dir:
        tif_path = glob(f"{sample_dir}/{args.tif_dir}/*.tif")
        if tif_path:
            img = np.stack([imread(tif) for tif in args.tif_paths], axis=-1)
        else:
            print(f"[red]No .tif files found in {args.tif_dir}[/]")
            return
    else:
        print(f"[red]No .czi files found and tif_dir is not specified for {sample_dir}[/]")
        return

    # Resample image
    if args.xy_res is None or args.z_res is None:
        _, _, _, xy_res_metadata, _, z_res_metadata = get_metadata_from_czi(czi_path)
        args.xy_res = args.xy_res or xy_res_metadata
        args.z_res = args.z_res or z_res_metadata

    zf_xy = args.xy_res / args.res
    zf_z = args.z_res / args.res
    img_resampled = ndimage.zoom(img, (zf_xy, zf_xy, zf_z), order=args.zoom_order)

    # Reorient image
    img_reoriented = np.flip(np.einsum('zyx->xzy', img_resampled), axis=1)

    # Save image as tif series (for brain_mask.py)
    tif_dir = Path(sample_dir, "reg_input", f"autofl_{args.res}um_tifs")
    tif_dir.mkdir(parents=True, exist_ok=True)
    for i, slice_ in enumerate(img_reoriented):
        slice_file_path = tif_dir / f"slice_{i:04d}.tif"
        imwrite(str(slice_file_path), slice_)
    print(f"\n  Output: [default bold]{tif_dir}[/]\n")
    

@unrvl.print_cmd_and_times
def main():
    args = parse_args()

    # Define output path relative to sample folder
    output_path = Path("reg_input", f"autofl_{args.res}um_tifs")

    # Process all samples in working dir or only those specified. 
    # If running script from in a sample folder, just process that sample.
    unrvl.process_samples_in_dir(resample_reorient, sample_list=args.dir_list, sample_dirs_pattern=args.dir_pattern, output=output_path, args=args)


if __name__ == '__main__':
    main()


### To do: import metadata function for tifs. Add metadata function to unravel_utils.py