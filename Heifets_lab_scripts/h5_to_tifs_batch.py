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
    parser.add_argument('-o', '--output', help='Name of folder for outputing tifs in ./ or ./sample??/', metavar='')
    parser.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)
    parser.epilog = """
Run hdf5.py from the experiment directory containing sample?? folders or a sample?? folder.
inputs: ./hdf5/*.h5 or ./sample??/hdf5/*.h5 match (put only largest h5 file here)
outputs: .[/sample??]/tif_dir/slice_????.tif series and .[/sample??]/parameters/metadata
next script: prep_reg.sh"""
    return parser.parse_args()


@print_func_name_args_times()
def prep_reg(sample, args):
    """Preps inputs for brain_mask.py and atlas registration (reg.py)"""

    # Define outputs 
    cwd = Path(".").resolve()
    sample_path = Path(sample).resolve() if sample != cwd.name else cwd

    if args.output: 
        output_path = Path(sample_path, args.output).resolve().parent
        autofl_img_output_name = Path(args.output).name
    else:
        output_path = Path(sample_path, "reg_input").resolve()
        autofl_img_output_name = f"autofl_{args.res}um.nii.gz"
    autofl_img_output = Path(output_path, autofl_img_output_name)

    # Skip processing if output exists
    if autofl_img_output.exists():
        print(f"\n\n    {autofl_img_output} already exists. Skipping.\n")
        return

    # Load autofluo image and optionally get resolutions
    try:
        img_path = sample_path if glob(f"{sample_path}/*.czi") else Path(sample_path, args.label).resolve()
        if args.xy_res is None or args.z_res is None:
            img, xy_res, z_res = load_3D_img(img_path, args.channel, "xyz", return_res=True)
        else:
            img = load_3D_img(img_path, args.channel, "xyz")
            xy_res, z_res = args.xy_res, args.z_res
        if not isinstance(xy_res, float) or not isinstance(z_res, float):
            raise ValueError(f"Metadata not extractable from {img_path}. Rerun w/ --xy_res and --z_res")
    except (FileNotFoundError, ValueError) as e:
        print(f"\n    [red bold]Error: {e}\n    Skipping {sample}.\n")
        return

    # Resample and reorient image
    img_reoriented = resample_reorient(img, xy_res, z_res, args.res, zoom_order=args.zoom_order)

    # Save autofl image as tif series (for brain_mask.py)
    tif_dir_output = Path(str(autofl_img_output).replace('.nii.gz', '_tifs')) # e.g., ./sample01/reg_input/autofl_50um_tifs
    tif_dir_output.mkdir(parents=True, exist_ok=True)
    save_as_tifs(img_reoriented, tif_dir_output, "xyz")

    # Save autofl image (for reg.py if skipping brain_mask.py and for applying the brain mask)
    save_as_nii(img_reoriented, autofl_img_output, args.res, args.res, np.uint16)
    return


def main():
    samples = get_samples(args.dirs, args.pattern)

    if samples == ['.']:
        samples[0] = Path.cwd().name
    
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