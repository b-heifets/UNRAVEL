#!/usr/bin/env python3

import argparse
import numpy as np
import os
import subprocess
from glob import glob
from pathlib import Path
from rich.live import Live
from unravel_img_tools import ilastik_segmentation, load_tifs, load_nii, save_as_nii
from unravel_utils import print_cmd_and_times, print_func_name_args_times, get_progress_bar, get_samples


def parse_args():
    parser = argparse.ArgumentParser(description='Before running brain_mask.py, train ilastik using tifs from ./sample??/reg_input/autofl_*um_tifs/*.tif (from prep_reg.py)')
    parser.add_argument('--dirs', help='List of folders to process. If not provided, --pattern used for matching dirs to process. If no matches, the current directory is used.', nargs='*', default=None, metavar='')
    parser.add_argument('-p', '--pattern', help='Pattern for folders in the working dir to process. Default: sample??', default='sample??', metavar='')
    parser.add_argument('-i', '--input', help='path/autofl.nii.gz input to mask. Default: reg_input/autofl_50um.nii.gz', default='reg_input/autofl_50um.nii.gz', metavar='')
    parser.add_argument('-td', '--tif_dir', help='path/autofl_tif_dir containing tif series for segmentation. Default: reg_input/autofl_50um_tifs', default="reg_input/autofl_50um_tifs", metavar='')
    parser.add_argument('-ilp', '--ilastik_prj', help='path/trained_ilastik_project.ilp. label 1 should = tissue. Default: reg_input/brain_mask.ilp', default='reg_input/brain_mask.ilp', metavar='')
    parser.add_argument('-o', '--output', help='Output file name. Default: autofl_50um_masked.nii.gz', default="autofl_50um_masked.nii.gz", metavar='')
    parser.add_argument('-od', '--out_dir', help='Output directory. Default: reg_input', default='reg_input', metavar='')
    parser.add_argument('-r', '--res', help='Resolution of autofluo input image in microns. Default: 50', default=50, type=int, metavar='')
    parser.add_argument('-l', '--ilastik_log', help='Show Ilastik log', action='store_true')
    parser.add_argument('-v', '--verbose', help='Enable verbose mode', action='store_true')
    parser.epilog = "Outputs: ./reg_input/autofl_50um_tifs_ilastik_brain_seg/slice_????.tif series, ./reg_input/autofl_50um_brain_mask.nii.gz, and ./reg_input/autofl_50um_masked.nii.gz"
    return parser.parse_args()


def main():
    args = parse_args()


    unrvl.process_samples_in_dir(load_img_resample_reorient_save_nii, sample_list=args.dir_list, sample_dirs_pattern=args.dir_pattern, output=output_path, args=args)


    samples = get_samples(args.dirs, args.pattern)

    decorated_ilastik_segmentation = print_func_name_args_times(ilastik_segmentation)

    progress = get_progress_bar(total_tasks=len(samples))
    task_id = progress.add_task("  [red]Processing samples...", total=len(samples))
    with Live(progress):
        for sample in samples:

            # Check if the output file already exists and skip if it does
            if args.output == None:
                args.output = Path(f"{sample}/reg_input/autofl_{args.autofl_res}um_masked.nii.gz").resolve()

            # Segment brain in autofluo image with Ilastik
            if args.tif_dir == "reg_input/autofl_50um_tifs": # default
                autofl_tif_directory = str(Path(sample, "reg_input/autofl_50um_tifs", args.tif_dir).resolve())
            else:
                autofl_tif_directory = str(Path(args.tif_dir).resolve())

            if args.ilastik_prj == 'reg_input/brain_mask.ilp': # default
                ilastik_project = str(Path(sample, args.ilastik_prj ).resolve()) 
            else:
                ilastik_project = args.ilastik_prj

            if args.out_dir == "reg_input": # default
                output_dir = str(Path(sample, args.out_dir, "autofl_50um_tifs_ilastik_brain_seg").resolve())
            else:
                output_dir = str(Path(args.out_dir).resolve())

            decorated_ilastik_segmentation(autofl_tif_directory, ilastik_project, output_dir, args.ilastik_log)

            # Load brain mask image
            seg_dir = Path(sample, f"{args.tif_dir}_ilastik_brain_seg").resolve()
            seg_img = load_tifs(seg_dir)

            # Convert anything voxels to 0 if > 1 (label 1 = tissue; other labels converted to 0)
            brain_mask = np.where(seg_img > 1, 0, seg_img)

            # Save brain mask as nifti
            base = os.path.basename(args.input)
            autofl_name, _ = os.path.splitext(base)
            autofl_name, _ = os.path.splitext(autofl_name)
            autofl_name, _ = os.path.splitext(autofl_name)
            brain_mask_path = Path(f"{sample}/reg_input/{autofl_name}_brain_mask.nii.gz").resolve()
            save_as_nii(brain_mask, brain_mask_path, args.autofl_res, args.autofl_res, args.autofl_res, np.uint8)

            # Load autofl image
            autofl_img_path = Path(f"{sample}/{args.input}").resolve()
            autofl_img = load_nii(autofl_img_path)
            autofl_img_transpose = np.transpose(autofl_img, (2, 1, 0))

            # Apply brain mask to autofluo image
            autofl_masked = np.where(seg_img == 1, autofl_img_transpose, 0)

            # Save masked autofl image
            masked_autofl_output = f"{sample}/reg_input/autofl_{args.autofl_res}um_masked.nii.gz"
            save_as_nii(autofl_masked, masked_autofl_output, args.autofl_res, args.autofl_res, args.autofl_res, np.uint16)

            progress.update(task_id, advance=1)


if __name__ == '__main__':
    from rich.traceback import install
    install()
    
    args = parse_args()
    print_cmd_and_times.verbose = args.verbose
    print_func_name_args_times.verbose = args.verbose
    
    print_cmd_and_times(main)()

### To do: look into load and save nii functions and evaluate whether it makes sense to have ndarrays as z, y, x, or x, y, z