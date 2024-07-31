#!/usr/bin/env python3

"""
Use ``seg_brain_mask`` from UNRAVEL to run a trained ilastik project (pixel classification) to mask the brain (often better registration).

Usage:
------
    seg_brain_mask -ie <path/ilastik_executable> -ilp <path/brain_mask.ilp> [-i reg_inputs/autofl_50um.nii.gz] [-r 50] [-v] 

Prereqs: 
    - Train ilastik (tissue = label 1) w/ tifs from reg_inputs/autofl_<asterisk>um_tifs/<asterisk>.tif (from ``reg_prep``)
    - Save brain_mask.ilp in experiment directory of use -ilp

Inputs: 
    - reg_inputs/autofl_<asterisk>um.nii.gz
    - brain_mask.ilp # in exp dir

Outputs: 
    - reg_inputs/autofl_<asterisk>um_tifs_ilastik_brain_seg/slice_<asterisk>.tif series
    - reg_inputs/autofl_<asterisk>um_brain_mask.nii.gz (can be used for ``reg`` and ``vstats_z_score``)
    - reg_inputs/autofl_<asterisk>um_masked.nii.gz

Next command: 
    - ``reg``
"""

import argparse
import numpy as np
from pathlib import Path
from rich import print
from rich.live import Live
from rich.traceback import install

from unravel.core.argparse_utils import SuppressMetavar, SM
from unravel.core.config import Configuration 
from unravel.core.img_io import load_3D_img, resolve_path, save_as_nii
from unravel.core.img_tools import pixel_classification
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg, initialize_progress_bar, get_samples


def parse_args():
    parser = argparse.ArgumentParser(formatter_class=SuppressMetavar)
    parser.add_argument('-e', '--exp_paths', help='List of experiment dir paths w/ sample?? dirs to process.', nargs='*', default=None, action=SM)
    parser.add_argument('-p', '--pattern', help='Pattern for sample?? dirs. Use cwd if no matches.', default='sample??', action=SM)
    parser.add_argument('-d', '--dirs', help='List of sample?? dir names or paths to dirs to process', nargs='*', default=None, action=SM)
    parser.add_argument('-ie', '--ilastik_exe', help='path/ilastik_executable.', required=True, action=SM)
    parser.add_argument('-ilp', '--ilastik_prj', help='path/brain_mask.ilp. Default: brain_mask.ilp', default='brain_mask.ilp', action=SM)
    parser.add_argument('-i', '--input', help='reg_inputs/autofl_50um.nii.gz (from ``reg_prep``)', default="reg_inputs/autofl_50um.nii.gz", action=SM)
    parser.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)
    parser.epilog = __doc__
    return parser.parse_args()


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

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
            pixel_classification(autofl_tif_directory, ilastik_project, seg_dir, args.ilastik_exe)

            # Load brain mask image
            seg_img = load_3D_img(seg_dir, "xyz")

            # Convert anything voxels to 0 if > 1 (label 1 = tissue; other labels converted to 0)
            brain_mask = np.where(seg_img > 1, 0, seg_img)

            # # Load autofl image
            autofl_img, xy_res, z_res = load_3D_img(autofl_img_path, return_res=True)

            # Save brain mask as nifti
            save_as_nii(brain_mask, brain_mask_output, xy_res, z_res, np.uint8)

            # Apply brain mask to autofluo image
            autofl_masked = np.where(seg_img == 1, autofl_img, 0)

            # Save masked autofl image
            save_as_nii(autofl_masked, autofl_img_masked_output, xy_res, z_res, np.uint16)

            # brain_mask(sample, args)
            progress.update(task_id, advance=1)

    verbose_end_msg()
    

if __name__ == '__main__':
    main()