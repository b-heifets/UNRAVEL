#!/usr/bin/env python3

import argparse
import numpy as np
from pathlib import Path
from rich import print
from rich.live import Live
from rich.traceback import install

from argparse_utils import SuppressMetavar, SM
from unravel_config import Configuration 
from unravel_img_io import load_3D_img, resolve_path, save_as_nii
from unravel_img_tools import ilastik_segmentation
from unravel_utils import print_cmd_and_times, initialize_progress_bar, get_samples


def parse_args():
    parser = argparse.ArgumentParser(description='Uses a trained ilastik project (pixel classification) to mask the brain (better registration)', formatter_class=SuppressMetavar)
    parser.add_argument('-e', '--exp_paths', help='List of experiment dir paths w/ sample?? dirs to process.', nargs='*', default=None, action=SM)
    parser.add_argument('-p', '--pattern', help='Pattern for sample?? dirs. Use cwd if no matches.', default='sample??', action=SM)
    parser.add_argument('-d', '--dirs', help='List of sample?? dir names or paths to dirs to process', nargs='*', default=None, action=SM)
    parser.add_argument('-i', '--input', help='reg_inputs/autofl_50um.nii.gz (from prep_reg.py)', default="reg_inputs/autofl_50um.nii.gz", action=SM)
    parser.add_argument('-ilp', '--ilastik_prj', help='path/brain_mask.ilp. Default: brain_mask.ilp', default='brain_mask.ilp', action=SM)
    parser.add_argument('-r', '--reg_res', help='Resolution of autofluo input image in microns. Default: 50', default=50, type=int, action=SM)
    parser.add_argument('-l', '--ilastik_log', help='Show Ilastik log', action='store_true')
    parser.add_argument('-v', '--verbose', help='Enable verbose mode', action='store_true')
    parser.epilog = """Prereqs: 
1) Train ilastik (tissue = label 1) w/ tifs from reg_inputs/autofl_*um_tifs/*.tif (from prep_reg.py)
2) Save brain_mask.ilp in experiment directory of use -ilp

Run brain_mask.py from exp dir or a sample?? dir.

Example usage:     brain_mask.py -v 

Inputs: 
reg_inputs/autofl_50um.nii.gz
brain_mask.ilp # in exp dir

Outputs: 
reg_inputs/autofl_50um_tifs_ilastik_brain_seg/slice_????.tif series
reg_inputs/autofl_50um_brain_mask.nii.gz
reg_inputs/autofl_50um_masked.nii.gz

Next script: reg.py"""
    return parser.parse_args()


def main():
    samples = get_samples(args.dirs, args.pattern, args.exp_paths)

    progress, task_id = initialize_progress_bar(len(samples), "[red]Processing samples...")
    with Live(progress):
        for sample in samples:
            # Resolve path to sample folder
            sample_path = Path(sample).resolve() if sample != Path.cwd().name else Path.cwd()

            # Define input and output paths
            autofl_img_path = resolve_path(sample_path, path_or_pattern=args.input)
            brain_mask_output = Path(str(autofl_img_path).replace('.nii.gz', '_brain_mask.nii.gz'))
            autofl_img_masked_output = Path(str(autofl_img_path).replace('.nii.gz', '_masked.nii.gz'))
            autofl_tif_directory = str(autofl_img_path).replace('.nii.gz', '_tifs')
            seg_dir = f"{autofl_tif_directory}_ilastik_brain_seg"

            # Skip if output exists
            if autofl_img_masked_output.exists():
                print(f"\n\n    {autofl_img_masked_output} already exists. Skipping.\n")
                continue
            
            # Run ilastik segmentation
            if args.ilastik_prj == 'brain_mask.ilp': 
                ilastik_project = Path(sample_path.parent, args.ilastik_prj).resolve()
            else:
                ilastik_project = Path(args.ilastik_prj).resolve()
            ilastik_segmentation(autofl_tif_directory, ilastik_project, seg_dir, args.ilastik_log)

            # Load brain mask image
            seg_img = load_3D_img(seg_dir, "xyz")

            # Convert anything voxels to 0 if > 1 (label 1 = tissue; other labels converted to 0)
            brain_mask = np.where(seg_img > 1, 0, seg_img)

            # Save brain mask as nifti
            save_as_nii(brain_mask, brain_mask_output, args.reg_res, args.reg_res, np.uint8)

            # Load autofl image
            autofl_img = load_3D_img(autofl_img_path)

            # Apply brain mask to autofluo image
            autofl_masked = np.where(seg_img == 1, autofl_img, 0)

            # Save masked autofl image
            save_as_nii(autofl_masked, autofl_img_masked_output, args.reg_res, args.reg_res, np.uint16)

            # brain_mask(sample, args)
            progress.update(task_id, advance=1)


if __name__ == '__main__':
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    print_cmd_and_times(main)()