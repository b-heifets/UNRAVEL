#!/usr/bin/env python3

import argparse
import nibabel as nib
import numpy as np
import unravel_utils as unrvl
from aicspylibczi import CziFile
from fnmatch import fnmatch
from glob import glob
from metadata import get_metadata_from_czi
from pathlib import Path
from rich import print
from scipy import ndimage
from tqdm import tqdm


def parse_args():
    parser = argparse.ArgumentParser(description='Load channel of *.czi, resample, reorient, and save as ./niftis/<img>.nii.gz')
    parser.add_argument('-sd', '--sample_dirs', help='Pattern for folders in working dir to process (Default: sample??)', default='sample??', metavar='')
    parser.add_argument('-sl', '--sample_list', help='Folders to process in working dir (e.g., sample01 sample02) (Default: process sample??) ', nargs='+', default=None, metavar='')
    parser.add_argument('-o', '--output', help='img.nii.gz (default: clar_res0.05.nii.gz)', default="clar_res0.05.nii.gz", metavar='')
    parser.add_argument('-c', '--channel', help='Channel number (Default: 0 for 1st channel [usually autofluo])', default=0, type=int, metavar='')
    parser.add_argument('-x', '--xy_res', help='x/y voxel size in microns (Default: get via metadata)', default=None, type=float, metavar='')
    parser.add_argument('-z', '--z_res', help='z voxel size in microns (Default: get via metadata)', default=None, type=float, metavar='')
    parser.add_argument('-r', '--res', help='Resample to this resolution in microns (Default: 50)', default=50, type=int, metavar='')
    parser.add_argument('-zo', '--zoom_order', help='Order of spline interpolation. Range: 0-5. (Default: 1))', default=1, type=int, metavar='')
    return parser.parse_args()

@unrvl.function_decorator()
def process_sample(sample_dir, args=None, **kwargs):
    czi_path = glob(f"{sample_dir}/*.czi")
    if not czi_path:
        print(f"[red]No .czi files found in {sample_dir}[/]")
        return
    
    czi_path = czi_path[0]
    czi = CziFile(czi_path)
    img = czi.read_image(C=args.channel)[0]
    img = np.squeeze(img)
    img = np.transpose(img, (2, 1, 0))

    if args.xy_res is None or args.z_res is None:
        _, _, _, xy_res_metadata, _, z_res_metadata = get_metadata_from_czi(czi_path)
        args.xy_res = args.xy_res or xy_res_metadata
        args.z_res = args.z_res or z_res_metadata

    zf_xy = args.xy_res / args.res
    zf_z = args.z_res / args.res
    img_resampled = ndimage.zoom(img, (zf_xy, zf_xy, zf_z), order=args.zoom_order)

    img_reoriented = np.flip(np.rot90(img_resampled, axes=(1, 0)), axis=1)
    nifti_dir = Path(sample_dir, "niftis")
    nifti_dir.mkdir(exist_ok=True)
    nifti_path = nifti_dir / args.output

    affine = np.eye(4) * (args.res / 1000)
    affine[3, 3] = 1
    nifti_img = nib.Nifti1Image(img_reoriented, affine)
    nifti_img.header.set_data_dtype(np.int16)
    nib.save(nifti_img, str(nifti_path))

@unrvl.print_cmd_and_times
def main():
    args = parse_args()
    samples_to_process = args.sample_list if args.sample_list else [d.name for d in Path('.').iterdir() if d.is_dir() and fnmatch(d.name, args.sample_dirs)]
    print(f"\n  [bright_black]Processing these folders: {samples_to_process}[/]\n")

    for sample in tqdm(samples_to_process, desc="  ", ncols=100, dynamic_ncols=True, unit="dir", leave=True):
        print(f"\n\n\n  Processing: [gold3]{sample}[/]")
        process_sample(sample, args)

if __name__ == '__main__':
    main()

# To do:
# If no czi, process tif series (e.g., data from UltraII microscope)