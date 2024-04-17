#!/usr/bin/env python3

import argparse
import nibabel as nib
import numpy as np
from pathlib import Path
from rich import print
from rich.live import Live
from rich.traceback import install
from scipy.ndimage import zoom

from argparse_utils import SuppressMetavar, SM
from unravel_config import Configuration
from unravel_img_io import load_image_metadata_from_txt, save_as_zarr, save_as_nii
from unravel_img_tools import reverse_reorient_for_raw_to_nii_conv, unpad_img
from unravel_utils import get_samples, initialize_progress_bar, print_cmd_and_times, print_func_name_args_times
from warp import warp


def parse_args():
    parser = argparse.ArgumentParser(description='Warp img.nii.gz from atlas space to tissue space and scale to full resolution', formatter_class=SuppressMetavar)
    parser.add_argument('-e', '--exp_paths', help='List of experiment dir paths w/ sample?? dirs to process.', nargs='*', default=None, action=SM)
    parser.add_argument('-p', '--pattern', help='Pattern for sample?? dirs. Use cwd if no matches.', default='sample??', action=SM)
    parser.add_argument('-d', '--dirs', help='List of sample?? dir names or paths to dirs to process', nargs='*', default=None, action=SM)
    parser.add_argument('-m', '--moving_img', help='path/image.nii.gz to warp from atlas space', required=True, action=SM)
    parser.add_argument('-fri', '--fixed_reg_in', help='Fixed input for registration (reg.py). Default: autofl_50um_masked_fixed_reg_input.nii.gz', default="autofl_50um_masked_fixed_reg_input.nii.gz", action=SM)
    parser.add_argument('-i', '--interpol', help='Interpolator for ants.apply_transforms (nearestNeighbor, multiLabel [default], linear, bSpline)', default="multiLabel", action=SM)
    parser.add_argument('-o', '--output', help='Save as rel_path/native_image.zarr (fast) or rel_path/native_image.nii.gz if provided', default=None, action=SM)
    parser.add_argument('-md', '--metadata', help='path/metadata.txt. Default: ./parameters/metadata.txt', default="./parameters/metadata.txt", action=SM)
    parser.add_argument('-ro', '--reg_outputs', help="Name of folder w/ outputs from registration. Default: reg_outputs", default="reg_outputs", action=SM)
    parser.add_argument('-zo', '--zoom_order', help='SciPy zoom order for scaling to full res. Default: 0 (nearest-neighbor)', default='0',type=int, action=SM)
    parser.add_argument('-mi', '--miracl', help='Mode for compatibility (accounts for tif to nii reorienting)', action='store_true', default=False)
    parser.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)
    parser.epilog = """
Prereq: ./parameters/metadata.txt (prep_reg.py or metadata.py)

Usage: to_native6.py -m <path/image_to_warp_from_atlas_space.nii.gz> -o <native>/native_<img>.zarr"""
    return parser.parse_args()


@print_func_name_args_times()
def scale_to_full_res(ndarray, full_res_dims, zoom_order=0):
    """Scale ndarray to match x, y, z dimensions provided as ndarray (order=0 is nearest-neighbor). Returns scaled ndarray."""
    zoom_factors = (full_res_dims[0] / ndarray.shape[0], full_res_dims[1] / ndarray.shape[1], full_res_dims[2] / ndarray.shape[2])
    scaled_img = zoom(ndarray, zoom_factors, order=zoom_order) 
    return scaled_img

@print_func_name_args_times()
def to_native(sample_path, reg_outputs, fixed_reg_in, moving_img_path, metadata_rel_path, miracl, zoom_order, interpol, output=None):
    """Warp image from atlas space to tissue space and scale to full resolution"""

    # Warp the moving image to tissue space
    reg_outputs_path = sample_path / reg_outputs
    warp_outputs_dir = reg_outputs_path / "warp_outputs" 
    warp_outputs_dir.mkdir(exist_ok=True, parents=True)
    warped_nii_path = str(warp_outputs_dir / str(Path(moving_img_path).name).replace(".nii.gz", "_in_tissue_space.nii.gz"))
    if not Path(warped_nii_path).exists():
        print(f'\n    Warping the moving image to tissue space\n')
        fixed_img_for_reg_path = str(reg_outputs_path / fixed_reg_in)
        warp(reg_outputs_path, moving_img_path, fixed_img_for_reg_path, warped_nii_path, inverse=False, interpol=interpol)

    # Lower bit depth to match atlas space image
    warped_nii = nib.load(warped_nii_path)
    moving_nii = nib.load(moving_img_path)
    warped_img = np.asanyarray(warped_nii.dataobj, dtype=moving_nii.header.get_data_dtype()).squeeze()

    # Trim padding from warped image and scale to full resolution
    warped_img = unpad_img(warped_img, pad_width=0.15)

    # Reorient if needed
    if miracl: 
        warped_img = reverse_reorient_for_raw_to_nii_conv(warped_img)

    # Load resolutions and dimensions of full res image for scaling 
    metadata_path = sample_path / metadata_rel_path
    xy_res, z_res, x_dim, y_dim, z_dim = load_image_metadata_from_txt(metadata_path)
    if xy_res is None:
        print("    [red1]./sample??/parameters/metadata.txt is missing. Generate w/ metadata.py")
        import sys ; sys.exit()
    original_dimensions = np.array([x_dim, y_dim, z_dim])

    # Scale to full resolution
    native_img = scale_to_full_res(warped_img, original_dimensions, zoom_order=zoom_order)
    
    # Save as .nii.gz or .zarr
    if output is not None:
        if str(output).endswith(".zarr"):
            save_as_zarr(native_img, output)
        elif str(output).endswith(".nii.gz"):
            save_as_nii(native_img, output, xy_res, z_res, native_img.dtype)

    return native_img


def main():
    samples = get_samples(args.dirs, args.pattern, args.exp_paths)

    progress, task_id = initialize_progress_bar(len(samples), "[red]Processing samples...")
    with Live(progress):
        for sample in samples:
            
            sample_path = Path(sample).resolve() if sample != Path.cwd().name else Path.cwd()

            if args.output is not None:
                output = sample_path / args.output
            else:
                output = None
            
            to_native(sample_path, args.reg_outputs, args.fixed_reg_in, args.moving_img, args.metadata, args.miracl, args.zoom_order, args.interpol, output=output)

            progress.update(task_id, advance=1)


if __name__ == '__main__':
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    print_cmd_and_times(main)()