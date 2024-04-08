#!/usr/bin/env python3

import argparse
import numpy as np
from pathlib import Path
from rich import print
from rich.live import Live
from rich.traceback import install

from argparse_utils import SuppressMetavar, SM
from unravel_config import Configuration 
from unravel_img_io import load_3D_img, resolve_path, save_as_tifs, save_as_nii
from unravel_img_tools import resample, reorient_for_raw_to_nii_conv
from unravel_utils import print_cmd_and_times, initialize_progress_bar, get_samples

def parse_args():
    parser = argparse.ArgumentParser(description='Loads full resolution autofluo image and resamples to 50 um for registration', formatter_class=SuppressMetavar)
    parser.add_argument('-e', '--exp_paths', help='List of experiment dir paths w/ sample?? dirs to process.', nargs='*', default=None, action=SM)
    parser.add_argument('-p', '--pattern', help='Pattern for sample?? dirs. Use cwd if no matches.', default='sample??', action=SM)
    parser.add_argument('-d', '--dirs', help='List of sample?? dir names or paths to dirs to process', nargs='*', default=None, action=SM)
    parser.add_argument('-i', '--input', help='Full res image input path relative (rel_path) to ./sample??', required=True, action=SM)
    parser.add_argument('-c', '--channel', help='.czi channel number. Default: 0 for autofluo', default=0, type=int, action=SM)
    parser.add_argument('-o', '--output', help='Output path. Default: reg_inputs/autofl_50um.nii.gz', default="reg_inputs/autofl_50um.nii.gz", action=SM)
    parser.add_argument('-x', '--xy_res', help='x/y voxel size in microns. Default: get via metadata', default=None, type=float, action=SM)
    parser.add_argument('-z', '--z_res', help='z voxel size in microns. Default: get via metadata', default=None, type=float, action=SM)
    parser.add_argument('-m', '--metad_path', help='path/metadata.txt. Default: parameters/metadata.txt', default="parameters/metadata.txt", action=SM)
    parser.add_argument('-r', '--reg_res', help='Resample input to this res in um for reg.py. Default: 50', default=50, type=int, action=SM)
    parser.add_argument('-zo', '--zoom_order', help='Order for resampling (scipy.ndimage.zoom). Default: 1', default=1, type=int, action=SM)
    parser.add_argument('-mi', '--miracl', help="Include reorientation step to mimic MIRACL's tif to .nii.gz conversion", action='store_true', default=False)
    parser.add_argument('-v', '--verbose', help='Increase verbosity.', action='store_true', default=False)
    parser.epilog = """Run script from the experiment directory w/ sample?? folder(s)
or run from a sample?? folder.

Example usage:     prep_reg.py -i *.czi -v

Input examples (path is relative to ./sample??; 1st glob match processed): 
*.czi, autofluo/*.tif series, autofluo, *.tif, or *.h5 

Outputs: 
.[/sample??]/reg_inputs/autofl_*um.nii.gz
.[/sample??]/reg_inputs/autofl_*um_tifs/*.tif series (used for training ilastik for brain_mask.py)

Next script: brain_mask.py or reg.py"""
    return parser.parse_args()


def main():
    samples = get_samples(args.dirs, args.pattern, args.exp_paths)
    
    progress, task_id = initialize_progress_bar(len(samples), "[red]Processing samples...")
    with Live(progress):
        for sample in samples:

            # Resolve path to sample folder
            sample_path = Path(sample).resolve() if sample != Path.cwd().name else Path.cwd()

            # Define output
            output = resolve_path(sample_path, args.output, make_parents=True)
            if output.exists():
                print(f"\n\n    {output.name} already exists. Skipping.\n")
                return

            # Define input image path
            img_path = resolve_path(sample_path, path_or_pattern=args.input)

            # Resolve path to metadata file
            metadata_path = resolve_path(sample_path, path_or_pattern=args.metad_path, make_parents=True)

            # Load autofluo image [and xy and z voxel size in microns]
            img, xy_res, z_res = load_3D_img(img_path, args.channel, "xyz", return_res=True, xy_res=args.xy_res, z_res=args.z_res, save_metadata=metadata_path)

            # Resample autofluo image (for registration)
            img_resampled = resample(img, xy_res, z_res, args.reg_res, zoom_order=args.zoom_order)

            # Optionally reorient autofluo image (mimics MIRACL's tif to .nii.gz conversion)
            if args.miracl: 
                img_resampled = reorient_for_raw_to_nii_conv(img_resampled)

            # Save autofluo image as tif series (for brain_mask.py)
            tif_dir = Path(str(output).replace('.nii.gz', '_tifs'))
            tif_dir.mkdir(parents=True, exist_ok=True)
            save_as_tifs(img_resampled, tif_dir, "xyz")

            # Save autofl image (for reg.py if skipping brain_mask.py and for applying the brain mask)
            save_as_nii(img_resampled, output, args.reg_res, args.reg_res, np.uint16)

            progress.update(task_id, advance=1)


if __name__ == '__main__':
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    print_cmd_and_times(main)()
