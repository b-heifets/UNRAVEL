#!/usr/bin/env python3

import argparse
import numpy as np
import os
import subprocess
import unravel_utils as unrvl
from glob import glob
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(description='Before running brain_mask.py, train ilastik using tifs from ./sample??/niftis/autofl_50um/*.tif (from prep_reg.sh)')
    parser.add_argument('--dir_pattern', help='Pattern for folders in working dir to process (Default: sample??)', default='sample??', metavar='')
    parser.add_argument('--dir_list', help='Folders to process in working dir (e.g., sample01 sample02) (Default: process sample??) ', nargs='+', default=None, metavar='')
    parser.add_argument('-ilp', '--ilastik_prj', help='path/trained_ilastik_project.ilp (label 1 should = tissue; Default: brain_mask.ilp)', default='brain_mask.ilp', metavar='')
    parser.add_argument('-td', '--tif_dir', help='path/autofl_tif_dir (Default: reg_input/autofl_50um_tifs)', default="reg_input/autofl_50um_tifs", metavar='')
    parser.add_argument('-afi', '--autofl_img', help='Autofl.nii.gz to mask (Default: reg_input/autofl_50um.nii.gz)', default='reg_input/autofl_50um.nii.gz', metavar='')
    parser.add_argument('-afr', '--autofl_res', help='Resolution of input in microns (Default: 50)', default=50, type=int, metavar='')
    parser.add_argument('-v', '--verbose', help='Enable verbose mode', action='store_true')
    return parser.parse_args()


def resolve_path(base_path, default_path, arg_path):
    if arg_path == default_path:
        return str((base_path / default_path).resolve())
    else:
        return str(Path(arg_path).resolve())


@unrvl.print_func_name_args_times
def load_img_resample_reorient_save_nii(sample_dir, args=None):

    # Segment brain in autofluo image with Ilastik
    sample_dir_path = Path(sample_dir)
    autofl_tif_directory = resolve_path(sample_dir_path, "reg_input/autofl_50um_tifs", args.tif_dir)
    autofl_tif_list = glob(f"{autofl_tif_directory}/*.tif")
    ilastik_project = resolve_path(sample_dir_path, 'brain_mask.ilp', args.ilastik_prj)
    seg_output_dir=f'{sample_dir_path}/reg_input/autofl_50um_tifs_ilastik_brain_seg'
    cmd = [
        'run_ilastik.sh',
        '--headless',
        '--project', ilastik_project,
        '--export_source', 'Simple Segmentation',
        '--output_format', 'tif',
        '--output_filename_format', f'{seg_output_dir}/{{nickname}}.tif',
    ] + autofl_tif_list

    seg_output_dir_path = Path(f'{sample_dir_path}/reg_input/autofl_50um_tifs_ilastik_brain_seg').resolve()
    if not seg_output_dir_path.exists():
        if args.verbose:
            subprocess.run(cmd)
        else:
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    # Load brain mask image
    seg_dir = Path(sample_dir_path, f"{args.tif_dir}_ilastik_brain_seg").resolve()
    seg_img = unrvl.load_tifs(seg_dir)

    # Convert anything voxels to 0 if > 1 (label 1 = tissue; other labels converted to 0)
    brain_mask = np.where(seg_img > 1, 0, seg_img)
    
    # Save brain mask as nifti
    base = os.path.basename(args.autofl_img)
    autofl_name, _ = os.path.splitext(base)
    autofl_name, _ = os.path.splitext(autofl_name)
    autofl_name, _ = os.path.splitext(autofl_name)
    brain_mask_path = Path(f"{sample_dir_path}/reg_input/{autofl_name}_brain_mask.nii.gz").resolve()
    unrvl.save_as_nii(brain_mask, brain_mask_path, args.autofl_res, args.autofl_res, args.autofl_res, np.uint8)

    # Load autofl image
    autofl_img_path = Path(f"{sample_dir_path}/{args.autofl_img}").resolve()
    autofl_img = unrvl.load_nii(autofl_img_path)
    autofl_img_transpose = np.transpose(autofl_img, (2, 1, 0)) # to make shape z, y, x

    # Apply brain mask to autofluo image
    autofl_masked = np.where(seg_img == 1, autofl_img_transpose, 0)

    # Save masked autofl image
    masked_autofl_output = f"{sample_dir_path}/reg_input/autofl_{args.autofl_res}um_masked.nii.gz"
    unrvl.save_as_nii(autofl_masked, masked_autofl_output, args.autofl_res, args.autofl_res, args.autofl_res, np.uint16)
    

@unrvl.print_cmd_and_times
def main():
    args = parse_args()

    output_path = Path("reg_input/autofl_{args.autofl_res}um_masked.nii.gz")

    unrvl.process_samples_in_dir(load_img_resample_reorient_save_nii, sample_list=args.dir_list, sample_dirs_pattern=args.dir_pattern, output=output_path, args=args)


if __name__ == '__main__':
    main()

### To do: look into load and save nii functions and evaluate whether it makes sense to have ndarrays as z, y, x, or x, y, z