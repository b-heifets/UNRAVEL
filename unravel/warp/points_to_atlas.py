#!/usr/bin/env python3

"""
Use ``warp_points_to_atlas`` from UNRAVEL to convert cell centroids in native space to an image matching the fixed registration input and then warp it to atlas space.

Usage:
------
    warp_points_to_atlas -i regional_stats/<asterisk>_sample??_cell_centroids.csv [-a atlas/atlas_CCFv3_2020_30um.nii.gz] [-r 50] [-af reg_inputs/autofl_50um.nii.gz] [-fri reg_outputs/autofl_50um_masked_fixed_reg_input.nii.gz] [-inp nearestNeighbor] [-thr 20000] [-uthr 20000] [-md parameters/metadata.txt] [-mi -v]

Prereqs: 
    ``reg`` and ``rstats``

Outputs:
    - ./sample??/atlas_space/<args.input name>
    - ./sample??/atlas_space/<args.input name --> .nii.gz>

Notes:
    - If the input CSV has a 'count' column, use ``utils_points_compressor`` to unpack the points before running this script.
"""

import argparse
import nibabel as nib
import numpy as np
import pandas as pd
from pathlib import Path
from rich import print
from rich.live import Live
from rich.traceback import install

from unravel.core.argparse_utils import SM, SuppressMetavar
from unravel.core.config import Configuration
from unravel.core.img_io import load_image_metadata_from_txt, nii_to_ndarray, nii_voxel_size
from unravel.core.img_tools import reorient_for_raw_to_nii_conv, reverse_reorient_for_raw_to_nii_conv
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg, initialize_progress_bar, get_samples
from unravel.image_io.img_to_points import img_to_points
from unravel.image_tools.resample_points import resample_and_convert_points
from unravel.warp.to_atlas import to_atlas


def parse_args():
    parser = argparse.ArgumentParser(formatter_class=SuppressMetavar)
    # Arguments for batch processing sample directories:
    parser.add_argument('-e', '--exp_paths', help='List of experiment dir paths w/ sample?? dirs to process.', nargs='*', default=None, action=SM)
    parser.add_argument('-p', '--pattern', help='Pattern for sample?? dirs. Use cwd if no matches.', default='sample??', action=SM)
    parser.add_argument('-d', '--dirs', help='List of sample?? dir names or paths to dirs to process', nargs='*', default=None, action=SM)

    # Required arguments:
    parser.add_argument('-i', '--input', help='regional_stats/<Condition>_sample??_cell_centroids.csv (w/ columns: x, y, z, Region_ID) from ``rstats`` (first glob match processed)', required=True, action=SM)

    # Optional arguments:
    parser.add_argument('-a', '--atlas', help='path/atlas.nii.gz or template matching moving image (Default: atlas/atlas_CCFv3_2020_30um.nii.gz)', default='atlas/atlas_CCFv3_2020_30um.nii.gz', action=SM)
    parser.add_argument('-fri', '--fixed_reg_in', help='Reference nii header from ``reg``. Default: reg_outputs/autofl_50um_masked_fixed_reg_input.nii.gz', default="reg_outputs/autofl_50um_masked_fixed_reg_input.nii.gz", action=SM)
    parser.add_argument('-inp', '--interpol', help='Type of interpolation (e.g., nearestNeighbor [default] or linear).', default='nearestNeighbor', action=SM)
    parser.add_argument('-af', '--autofl_img', help='reg_inputs/autofl_50um.nii.gz from ``reg_prep`` (reference for `resample_and_convert_points()`)', default="reg_inputs/autofl_50um.nii.gz", action=SM)
    parser.add_argument('-thr', '--thresh', help='Exclude region IDs below this threshold (e.g., 20000 to obtain left hemisphere data)', type=float, action=SM)
    parser.add_argument('-uthr', '--upper_thr', help='Exclude region IDs above this threshold (e.g., 20000 to obtain right hemisphere data)', type=float, action=SM)
    parser.add_argument('-md', '--metadata', help='path/metadata.txt. Default: parameters/metadata.txt', default="parameters/metadata.txt", action=SM)
    parser.add_argument('-mi', '--miracl', help='Mode for compatibility (accounts for tif to nii reorienting)', action='store_true', default=False)
    parser.add_argument('-v', '--verbose', help='Increase verbosity.', action='store_true', default=False)
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
            
            sample_path = Path(sample).resolve() if sample != Path.cwd().name else Path.cwd()

            # Load resolutions from metadata
            metadata_path = sample_path / args.metadata
            xy_res, z_res, _, _, _ = load_image_metadata_from_txt(metadata_path)
            if xy_res is None:
                print("    [red1]./sample??/parameters/metadata.txt is missing. Generate w/ io_metadata")
                import sys ; sys.exit()
            current_res = (xy_res, xy_res, z_res)

            # Load the csv with cell centroids in full resolution tissue space
            csv_path = next(sample_path.glob(str(args.input)), None)

            # Define main output path
            output_img_path = sample_path / "atlas_space" / str(csv_path.name).replace(".csv", ".nii.gz")
            output_img_path.parent.mkdir(exist_ok=True, parents=True)
            if output_img_path.exists():
                print(f"\n\n    {output_img_path} already exists. Skipping.\n")
                continue

            # Load reg_inputs/autofl_50um.nii.gz from ``reg_prep`` for shape and target resolution
            autofl_path = sample_path / args.autofl_img
            autofl_nii = nib.load(autofl_path)
            ref_img = nii_to_ndarray(autofl_nii)
            target_res = nii_voxel_size(autofl_nii)

            # Optionally reorient autofluo image
            if args.miracl:  # autofl_nii = clar_allen_reg/clar_res0.05.nii.gz
                ref_img = reverse_reorient_for_raw_to_nii_conv(ref_img)

            # Resample and convert points to an image matching reg_inputs/autofl_50um.nii.gz
            _, points_resampled_img = resample_and_convert_points(args.input, current_res, target_res, ref_img, args.thresh, args.upper_thr)

            # Optionally reorient autofluo image (mimics MIRACL's tif to .nii.gz conversion)
            if args.miracl: 
                points_resampled_img = reorient_for_raw_to_nii_conv(points_resampled_img)

            # Use function from img_to_points to convert the resampled image to a points DataFrame
            points_resampled_ndarray = img_to_points(points_resampled_img)
            points_resampled_df = pd.DataFrame(points_resampled_ndarray, columns=['x', 'y', 'z'])

            # Save the resampled points to a CSV file
            csv_output_path = autofl_path.parent / "points" / str(csv_path.name)
            csv_output_path.parent.mkdir(exist_ok=True, parents=True)
            points_resampled_df.to_csv(csv_output_path, index=False)
            print(f"\n    Points saved to: {csv_output_path}\n")

            # Warp native image to atlas space (Padded warp() input image with points saved to <reg_outputs>/warp_inputs/<output>.nii.gz)
            if np.max(points_resampled_img) > 0:
                dtype = 'uint16' if np.max(points_resampled_img) > 255 else 'uint8'
        
            to_atlas(sample_path, points_resampled_img, args.fixed_reg_in, args.atlas, output_img_path, args.interpol, dtype=dtype)

            progress.update(task_id, advance=1)

    verbose_end_msg()


if __name__ == '__main__':
    main()