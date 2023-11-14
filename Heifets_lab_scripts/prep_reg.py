#!/usr/bin/env python3

import argparse
import numpy as np
from argparse import RawTextHelpFormatter
from glob import glob
from pathlib import Path
from rich import print
from rich.live import Live
from rich.traceback import install
from unravel_config import Configuration 
from unravel_img_tools import load_3D_img, resample_reorient, save_as_tifs, save_as_nii
from unravel_utils import print_cmd_and_times, print_func_name_args_times, initialize_progress_bar, get_samples


def parse_args():
    parser = argparse.ArgumentParser(description='Loads autofluo image, resamples, reorients, saves as .nii.gz and tifs', formatter_class=RawTextHelpFormatter)
    parser.add_argument('-p', '--pattern', help='Pattern for folders to process. If no matches, use current dir. Default: sample??', default='sample??', metavar='')
    parser.add_argument('--dirs', help='List of folders to process. Overrides --pattern', nargs='*', default=None, metavar='')
    parser.add_argument('-c', '--channel', help='.czi channel number. Default: 0 for autofluo', default=0, type=int, metavar='')
    parser.add_argument('-cn', '--chann_name', help='Name of folder in w/ raw autofluo tifs. Default: autofl_tifs. In ./sample??/ or ./', default="autofl_tifs", metavar='')
    parser.add_argument('-o', '--output', help='NIfTI output path relative to ./ or ./sample??/. Default: reg_input/autofl_*um.nii.gz', default=None, metavar='')
    parser.add_argument('-x', '--xy_res', help='x/y voxel size in microns. Default: get via metadata', default=None, type=float, metavar='')
    parser.add_argument('-z', '--z_res', help='z voxel size in microns. Default: get via metadata', default=None, type=float, metavar='')
    parser.add_argument('-r', '--res', help='Resample to this resolution in microns. Default: 50', default=50, type=int, metavar='')
    parser.add_argument('-zo', '--zoom_order', help='Order of spline interpolation (scipy.ndimage.zoom). Range: 0-5. Default: 1', default=1, type=int, metavar='')
    parser.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)
    parser.epilog = """
Run prep_reg.py from the experiment directory containing sample?? folders or a sample?? folder.
inputs: first ./*.czi or ./sample??/*.czi match. Otherwise, ./<chann_name>/*.tif series
outputs: .[/sample??]/reg_input/autofl_*um.nii.gz and .[/sample??]/reg_input/autofl_*um_tifs/*.tif series
next script: brain_mask.py or reg.py"""
    return parser.parse_args()


@print_func_name_args_times()
def prep_reg(sample, args):
    """Preps inputs for brain_mask.py and atlas registration (reg.py)"""

    # Skip processing if output exists
    autofl_img_output = Path(sample, args.output) if args.output else Path(sample, "reg_input", f"autofl_{args.res}um.nii.gz").resolve()
    if autofl_img_output.exists():
        print(f"\n\n    {autofl_img_output} already exists. Skipping.\n")
        return # Skip to next sample
    
    # Load autofluo image and optionally get resolutions
    try:
        img_path = Path(sample).resolve() if glob(f"{sample}/*.czi") else Path(sample, args.chann_name).resolve()
        if args.xy_res is None or args.z_res is None:
            img, xy_res, z_res = load_3D_img(img_path, args.channel, "xyz", return_res=True)
        else:
            img = load_3D_img(img_path, args.channel, "xyz")
            xy_res, z_res = args.xy_res, args.z_res
    except (FileNotFoundError, ValueError) as e:
        print(f"\n    [red bold]Error: {e}\n    Skipping sample {sample}.\n")
        return

    # Resample and reorient image
    img_reoriented = resample_reorient(img, xy_res, z_res, args.res, zoom_order=args.zoom_order)

    # Save autofl image as tif series (for brain_mask.py)
    tif_dir_output = Path(autofl_img_output.parent, str(autofl_img_output.name).replace('.nii.gz', '_tifs')) # e.g., ./sample01/reg_input/autofl_50um_tifs
    tif_dir_output.mkdir(parents=True, exist_ok=True)
    save_as_tifs(img_reoriented, tif_dir_output, "xyz")

    # Save autofl image (for reg.py if skipping brain_mask.py and for applying the brain mask)
    save_as_nii(img_reoriented, autofl_img_output, args.res, args.res, np.uint16)
    return


def main():
    samples = get_samples(args.dirs, args.pattern)
    progress, task_id = initialize_progress_bar(len(samples), "[red]Processing samples...")
    with Live(progress):
        for sample in samples:
            prep_reg(sample, args)
            progress.update(task_id, advance=1)


if __name__ == '__main__':
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    print_cmd_and_times(main)()