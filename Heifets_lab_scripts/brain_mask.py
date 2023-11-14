#!/usr/bin/env python3

import argparse
import numpy as np
from argparse import RawTextHelpFormatter
from pathlib import Path
from rich import print
from rich.live import Live
from unravel_config import Configuration 
from unravel_img_tools import ilastik_segmentation, load_3D_img, save_as_nii
from unravel_utils import print_cmd_and_times, print_func_name_args_times, initialize_progress_bar, get_samples


def parse_args():
    parser = argparse.ArgumentParser(description='Uses a trained ilastik project (pixel classification workflow) to segment the brain for better registration', formatter_class=RawTextHelpFormatter)
    parser.add_argument('-p', '--pattern', help='Pattern for folders to process. If no matches, use current dir. Default: sample??', default='sample??', metavar='')
    parser.add_argument('--dirs', help='List of folders to process. Supercedes --pattern', nargs='*', default=None, metavar='')
    parser.add_argument('-i', '--input', help='autofl.nii.gz input path relative to ./ or ./sample??/. Default: reg_input/autofl_50um.nii.gz', default=None, metavar='')
    parser.add_argument('-ilp', '--ilastik_prj', help='path/trained_ilastik_project.ilp. label 1 should = tissue. Default: brain_mask.ilp (assumes ilp is in exp dir).', default='brain_mask.ilp', metavar='')
    parser.add_argument('-r', '--res', help='Resolution of autofluo input image in microns. Default: 50', default=50, type=int, metavar='')
    parser.add_argument('-l', '--ilastik_log', help='Show Ilastik log', action='store_true')
    parser.add_argument('-v', '--verbose', help='Enable verbose mode', action='store_true')
    parser.epilog = """
Before running brain_mask.py, train ilastik (tissue = label 1) using tifs from ./sample??/reg_input/autofl_*um_tifs/*.tif (from prep_reg.py).
Run brain_mask.py from the experiment directory containing sample?? folders or a sample?? folder.
inputs: ./sample??/reg_input/autofl_*um_tifs/*.tif series
outputs: ./reg_input/autofl_*um_tifs_ilastik_brain_seg/slice_????.tif series, ./reg_input/autofl_*um_brain_mask.nii.gz, and ./reg_input/autofl_*um_masked.nii.gz
next script: reg.py"""
    return parser.parse_args()

### TODO: consolidate --reg_input and --input into one argument
### TODO: removing custom --output and --tif_dir args

@print_func_name_args_times()
def brain_mask(sample, args):
    """Segment brain in autofluo image with Ilastik and apply mask."""

    # Define input and output paths
    cwd = Path(".").resolve()
    if args.input: 
        autofl_img_path = Path(sample, args.input).resolve() if sample != cwd.name else Path(args.input).resolve()
    else:
        autofl_img_path = Path(sample, "reg_input", f"autofl_{args.res}um.nii.gz").resolve() if sample != cwd.name else Path("reg_input", f"autofl_{args.res}um.nii.gz").resolve()
    brain_mask_output = Path(autofl_img_path.name.replace('.nii.gz', '_brain_mask.nii.gz'))
    autofl_img_masked_output = Path(autofl_img_path.name.replace('.nii.gz', '_masked.nii.gz'))    
    autofl_tif_directory = Path(autofl_img_path.parent, str(autofl_img_path.name).replace('.nii.gz', '_tifs'))
    seg_dir = Path(f"{autofl_tif_directory}_ilastik_brain_seg")

    # Skip processing if output exists
    if autofl_img_masked_output.exists():
        print(f"\n\n    {autofl_img_masked_output} already exists. Skipping.\n")
        return
    
    # Run ilastik segmentation
    if args.ilastik_prj == 'brain_mask.ilp': 
        ilastik_project = Path(cwd, args.ilastik_prj).resolve() if sample != cwd.name else Path(cwd.parent, args.ilastik_prj).resolve() # Assumes ilp is in exp dir
    else:
        ilastik_project = Path(args.ilastik_prj)
    ilastik_segmentation(str(autofl_tif_directory), str(ilastik_project), str(seg_dir), args.ilastik_log)

    # Load brain mask image
    seg_img = load_3D_img(seg_dir, "xyz")

    # Convert anything voxels to 0 if > 1 (label 1 = tissue; other labels converted to 0)
    brain_mask = np.where(seg_img > 1, 0, seg_img)

    # Save brain mask as nifti
    save_as_nii(brain_mask, brain_mask_output, args.res, args.res, args.res, np.uint8)

    # Load autofl image
    autofl_img = load_3D_img(autofl_img_path)

    # Apply brain mask to autofluo image
    autofl_masked = np.where(seg_img == 1, autofl_img, 0)

    # Save masked autofl image
    save_as_nii(autofl_masked, autofl_img_masked_output, args.res, args.res, args.res, np.uint16)


def main():

    samples = get_samples(args.dirs, args.pattern)
    
    if samples == ['.']:
        wd = Path.cwd()
        samples[0] = wd.name

    progress, task_id = initialize_progress_bar(len(samples), "[red]Processing samples...")
    with Live(progress):
        for sample in samples:
            brain_mask(sample, args)
            progress.update(task_id, advance=1)


if __name__ == '__main__':
    from rich.traceback import install
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    print_cmd_and_times(main)()
