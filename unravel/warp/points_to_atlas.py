#!/usr/bin/env python3

"""
Use ``warp_points_to_atlas`` from UNRAVEL to warp cell coordiantes in native image to atlas space.

Usage:
------
    warp_points_to_atlas -i regional_stats/<condition>_sample??_cell_centroids.csv -o points_in_atlas_space.csv [-a atlas/atlas_CCFv3_2020_30um.nii.gz] [-r 50] [-af reg_inputs/autofl_50um.nii.gz] [-fri reg_outputs/autofl_50um_masked_fixed_reg_input.nii.gz] [-inp nearestNeighbor] [-thr 20000] [-uthr 20000] [-md parameters/metadata.txt] [-mi -v]

Prereqs: 
    ``reg`` and ``rstats``

Output:
    - ./sample??/atlas_space/next(glob(args.input)).replace(".csv", ".nii.gz")

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
from unravel.core.img_io import load_image_metadata_from_txt
from unravel.core.img_tools import pad, reorient_for_raw_to_nii_conv, reverse_reorient_for_raw_to_nii_conv
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg, print_func_name_args_times, initialize_progress_bar, get_samples
from unravel.warp.to_atlas import to_atlas


def parse_args():
    parser = argparse.ArgumentParser(formatter_class=SuppressMetavar)
    parser.add_argument('-e', '--exp_paths', help='List of experiment dir paths w/ sample?? dirs to process.', nargs='*', default=None, action=SM)
    parser.add_argument('-p', '--pattern', help='Pattern for sample?? dirs. Use cwd if no matches.', default='sample??', action=SM)
    parser.add_argument('-d', '--dirs', help='List of sample?? dir names or paths to dirs to process', nargs='*', default=None, action=SM)

    # Required arguments:
    parser.add_argument('-i', '--input', help='regional_stats/<Condition>_sample??_cell_centroids.csv (w/ columns: x, y, z, Region_ID) from ``rstats`` (first glob match processed)', required=True, action=SM)

    # Optional arguments:
    parser.add_argument('-a', '--atlas', help='path/atlas.nii.gz or template matching moving image (Default: atlas/atlas_CCFv3_2020_30um.nii.gz)', default='atlas/atlas_CCFv3_2020_30um.nii.gz', action=SM)
    parser.add_argument('-fri', '--fixed_reg_in', help='Reference nii header from ``reg``. Default: reg_outputs/autofl_50um_masked_fixed_reg_input.nii.gz', default="reg_outputs/autofl_50um_masked_fixed_reg_input.nii.gz", action=SM)
    parser.add_argument('-inp', '--interpol', help='Type of interpolation (e.g., nearestNeighbor [default] or linear).', default='nearestNeighbor', action=SM)
    parser.add_argument('-r', '--reg_res', help='Resolution of registration inputs in microns. Default: 50', default='50',type=int, action=SM)
    parser.add_argument('-af', '--autofl_img', help='reg_inputs/autofl_50um.nii.gz (from ``reg_prep``)', default="reg_inputs/autofl_50um.nii.gz", action=SM)
    parser.add_argument('-thr', '--thresh', help='Exclude region IDs below this threshold (e.g., 20000 to obtain left hemisphere data)', type=float, action=SM)
    parser.add_argument('-uthr', '--upper_thresh', help='Exclude region IDs above this threshold (e.g., 20000 to obtain right hemisphere data)', type=float, action=SM)
    parser.add_argument('-md', '--metadata', help='path/metadata.txt. Default: parameters/metadata.txt', default="parameters/metadata.txt", action=SM)
    parser.add_argument('-mi', '--miracl', help='Mode for compatibility (accounts for tif to nii reorienting)', action='store_true', default=False)
    parser.add_argument('-v', '--verbose', help='Increase verbosity.', action='store_true', default=False)
    parser.epilog = __doc__
    return parser.parse_args()

# TODO: Add commands to .toml, guide, and toctree. 


@print_func_name_args_times()
def centroids_to_img(centroids_ndarray, img_shape):
    """Convert x, y, z centroids (voxel, physical, or resampled coordinates) to a ndarray with the same shape as the input image."""
    coords_img = np.zeros(img_shape, dtype='uint8')

    # For each centroid, add 1 to the corresponding voxel in the image
    for x, y, z in centroids_ndarray.astype(int):
        if 0 <= x < img_shape[0] and 0 <= y < img_shape[1] and 0 <= z < img_shape[2]:
            coords_img[x, y, z] += 1
            # Check the sum and change the data type if needed
            if coords_img[x, y, z] == 255:
                coords_img = coords_img.astype('uint16')

    return coords_img

def pad(ndarray, pad_width=0.15):
    """Pads ndarray by 15% of voxels on all sides"""
    pad_factor = 1 + 2 * pad_width
    pad_width_x = round(((ndarray.shape[0] * pad_factor) - ndarray.shape[0]) / 2)
    pad_width_y = round(((ndarray.shape[1] * pad_factor) - ndarray.shape[1]) / 2)
    pad_width_z = round(((ndarray.shape[2] * pad_factor) - ndarray.shape[2]) / 2)
    return np.pad(ndarray, ((pad_width_x, pad_width_x), (pad_width_y, pad_width_y), (pad_width_z, pad_width_z)), mode='constant')

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

            # Load the csv with cell centroids in full resolution tissue space
            csv_path = next(sample_path.glob(str(args.input)), None)
            centroids_df = pd.read_csv(csv_path)  # Voxel coordinates start at 0

            output = sample_path / "atlas_space" / str(csv_path.name).replace(".csv", ".nii.gz")
            output.parent.mkdir(exist_ok=True, parents=True)
            if output.exists():
                print(f"\n\n    {output} already exists. Skipping.\n")
                continue

            # Remove centroids that are outside the brain (i.e., 'Region_ID' == 0)
            centroids_df = centroids_df[centroids_df['Region_ID'] != 0]

            # Filter centroids based on thresholding the 'Region_ID' column
            if args.thresh:
                centroids_df = centroids_df[centroids_df['Region_ID'] >= args.thresh]
            elif args.upper_thresh:
                centroids_df = centroids_df[centroids_df['Region_ID'] <= args.upper_thresh]

            # Drop the 'Region_ID' column
            centroids_df = centroids_df.drop(columns=['Region_ID'])

            # Convert centroids to numpy array and set the dtype to float
            centroids_ndarray = centroids_df.to_numpy()

            # Add a 1 voxel offset since the coordinates are 0-based
            centroids_ndarray += 1

            # Convert voxel coordinates to physical space
            centroids_ndarray_physical = centroids_ndarray * np.array([xy_res, xy_res, z_res])

            # Voxelization: 
            # Resampling determines which 50-micron voxel each physical point falls into. 
            # This can result in multiple nearby points being grouped into the same voxel, reducing the apparent density of data points.
            centroids_ndarray_resampled = centroids_ndarray_physical / args.reg_res

            # Load output image from ``reg_prep`` (e.g., reg_inputs/autofl_50um.nii.gz) to get shape
            nii = nib.load(sample_path / args.autofl_img)
            autofl_img = np.asanyarray(nii.dataobj, dtype=nii.header.get_data_dtype()).squeeze()
            if args.miracl:
                autofl_img_orig_orient = reverse_reorient_for_raw_to_nii_conv(autofl_img)  # clar_allen_reg/clar_res0.05.nii.gz
                img_shape = autofl_img_orig_orient.shape
            else:
                img_shape = autofl_img.shape

            # Create an image with the same shape as reg_inputs/autofl_50um.nii.gz
            resampled_coords_img = centroids_to_img(centroids_ndarray_resampled, img_shape)

            # Optionally reorient autofluo image (mimics MIRACL's tif to .nii.gz conversion)
            if args.miracl: 
                resampled_coords_img = reorient_for_raw_to_nii_conv(resampled_coords_img)

            # Warp native image to atlas space
            if np.max(resampled_coords_img) > 0:
                dtype = 'uint16' if np.max(resampled_coords_img) > 255 else 'uint8'
            to_atlas(sample_path, resampled_coords_img, args.fixed_reg_in, args.atlas, output, args.interpol, dtype=dtype)

            progress.update(task_id, advance=1)

    verbose_end_msg()


if __name__ == '__main__':
    main()