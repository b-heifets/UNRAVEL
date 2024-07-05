#!/usr/bin/env python3

"""
Use ``reg_prep`` from UNRAVEL to load a full resolution autofluo image and resamples to a lower resolution for registration.

Usage:
------
    reg_prep -i <asterisk>.czi [-e <list of paths to exp dirs>] [-v]

Run command from the experiment directory w/ sample?? folder(s), a sample?? folder, or provide -e or -d arguments.

Input examples (path is relative to ./sample??; 1st glob match processed): 
    <asterisk>.czi, autofluo/<asterisk>.tif series, autofluo, <asterisk>.tif, or <asterisk>.h5 

Outputs: 
    ./sample??/reg_inputs/autofl_<asterisk>um.nii.gz
    ./sample??/reg_inputs/autofl_<asterisk>um_tifs/<asterisk>.tif series (used for training ilastik for ``seg_brain_mask``) 

Next command: 
    ``seg_copy_tifs`` for ``seg_brain_mask`` or ``reg``
"""

import argparse
import numpy as np
from pathlib import Path
from rich import print
from rich.live import Live
from rich.traceback import install

from unravel.core.argparse_utils import SuppressMetavar, SM
from unravel.core.config import Configuration
from unravel.core.img_io import load_3D_img, resolve_path, save_as_tifs, save_as_nii
from unravel.core.img_tools import resample, reorient_for_raw_to_nii_conv
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg, initialize_progress_bar, get_samples, print_func_name_args_times
from unravel.segment.copy_tifs import copy_specific_slices


def parse_args():
    parser = argparse.ArgumentParser(formatter_class=SuppressMetavar)
    parser.add_argument('-e', '--exp_paths', help='List of experiment dir paths w/ sample?? dirs to process.', nargs='*', default=None, action=SM)
    parser.add_argument('-p', '--pattern', help='Pattern for sample?? dirs. Use cwd if no matches.', default='sample??', action=SM)
    parser.add_argument('-d', '--dirs', help='List of sample?? dir names or paths to dirs to process', nargs='*', default=None, action=SM)
    parser.add_argument('-i', '--input', help='Full res image input path relative (rel_path) to ./sample??', required=True, action=SM)
    parser.add_argument('-c', '--channel', help='.czi channel number. Default: 0 for autofluo', default=0, type=int, action=SM)
    parser.add_argument('-o', '--output', help='Output path. Default: reg_inputs/autofl_50um.nii.gz', default="reg_inputs/autofl_50um.nii.gz", action=SM)
    parser.add_argument('-x', '--xy_res', help='x/y voxel size in microns of the input image. Default: get via metadata', default=None, type=float, action=SM)
    parser.add_argument('-z', '--z_res', help='z voxel size in microns of the input image. Default: get via metadata', default=None, type=float, action=SM)
    parser.add_argument('-r', '--reg_res', help='Resample input to this res in um for reg. Default: 50', default=50, type=int, action=SM)
    parser.add_argument('-zo', '--zoom_order', help='Order for resampling (scipy.ndimage.zoom). Default: 1', default=1, type=int, action=SM)
    parser.add_argument('-td', '--target_dir', help='path/target_dir name to copy specific slices for seg_brain_mask (see usage)', default=None, action=SM)
    parser.add_argument('-s', '--slices', help='List of slice numbers to copy, e.g., 0000 0400 0800', nargs='*', type=str, default=[])
    parser.add_argument('-mi', '--miracl', help="Include reorientation step to mimic MIRACL's tif to .nii.gz conversion", action='store_true', default=False)
    parser.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)
    parser.epilog = __doc__
    return parser.parse_args()

# TODO: Remove args.target_dir since this can be done with ``seg_copy_tifs``


@print_func_name_args_times()
def reg_prep(ndarray, xy_res, z_res, reg_res, zoom_order, miracl):
    """Prepare the autofluo image for ``reg`` or mimic preprocessing  for ``vstats_prep``.
    
    Args:
        - ndarray (np.ndarray): full res 3D autofluo image.
        - xy_res (float): x/y resolution in microns of ndarray.
        - z_res (float): z resolution in microns of ndarray.
        - reg_res (int): Resample input to this resolution in microns for ``reg``.
        - zoom_order (int): Order for resampling (scipy.ndimage.zoom).
        - miracl (bool): Include reorientation step to mimic MIRACL's tif to .nii.gz conversion.
        
    Returns:
        - img_resampled (np.ndarray): Resampled image."""

    # Resample autofluo image (for registration)
    img_resampled = resample(ndarray, xy_res, z_res, reg_res, zoom_order=zoom_order)

    # Optionally reorient autofluo image (mimics MIRACL's tif to .nii.gz conversion)
    if miracl: 
        img_resampled = reorient_for_raw_to_nii_conv(img_resampled)

    return img_resampled


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    if args.target_dir is not None:
        # Create the target directory for copying the selected slices for ``seg_brain_mask``
        target_dir = Path(args.target_dir)
        target_dir.mkdir(exist_ok=True, parents=True)

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
                continue
            
            # Define input image path
            img_path = resolve_path(sample_path, args.input)

            # Load full res autofluo image [and xy and z voxel size in microns]
            img, xy_res, z_res = load_3D_img(img_path, args.channel, "xyz", return_res=True, xy_res=args.xy_res, z_res=args.z_res)

            # Prepare the autofluo image for registration
            img_resampled = reg_prep(img, xy_res, z_res, args.reg_res, args.zoom_order, args.miracl)

            # Save the prepped autofluo image as tif series (for ``seg_brain_mask``)
            tif_dir = Path(str(output).replace('.nii.gz', '_tifs'))
            tif_dir.mkdir(parents=True, exist_ok=True)
            save_as_tifs(img_resampled, tif_dir, "xyz")

            # Save the prepped autofl image (for ``reg`` if skipping ``seg_brain_mask`` and for applying the brain mask)
            save_as_nii(img_resampled, output, args.reg_res, args.reg_res, np.uint16)

            if args.target_dir is not None:
                # Copy specific slices to the target directory
                tif_dir = str(output).replace('.nii.gz', '_tifs')
                copy_specific_slices(sample_path, tif_dir, target_dir, args.slices)

            progress.update(task_id, advance=1)

    verbose_end_msg()
    

if __name__ == '__main__':
    main()