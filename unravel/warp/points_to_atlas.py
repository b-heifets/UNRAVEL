#!/usr/bin/env python3

"""
Use ``warp_points_to_atlas`` from UNRAVEL to warp cell coordiantes in native image to atlas space.

Usage:
------
    warp_points_to_atlas -i regional_stats/<condition>_sample??_cell_centroids.csv -o points_in_atlas_space.csv -r 50 [-a path/atlas.nii.gz -dt uint16 -fri reg_outputs/autofl_50um_masked_fixed_reg_input.nii.gz -inp bSpline -zo 1 -mi -v]

Prereqs: 
    ``reg`` and ``rstats``

Input examples (path is relative to ./sample??; 1st glob match processed): 
    <asterisk>.czi, ochann/<asterisk>.tif, ochann, <asterisk>.tif, <asterisk>.h5, or <asterisk>.zarr 
"""

import ants
import argparse
import nibabel as nib
import numpy as np
import pandas as pd
from pathlib import Path
from rich import print
from rich.live import Live
from rich.traceback import install
from scipy import ndimage

from unravel.image_io.io_nii import convert_dtype
from unravel.core.argparse_utils import SM, SuppressMetavar
from unravel.core.config import Configuration
from unravel.core.img_io import load_image_metadata_from_txt
from unravel.core.img_tools import pad
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg, print_func_name_args_times, initialize_progress_bar, get_samples
from unravel.register.reg_prep import reg_prep
from unravel.warp.warp import warp


def parse_args():
    parser = argparse.ArgumentParser(formatter_class=SuppressMetavar)
    parser.add_argument('-e', '--exp_paths', help='List of experiment dir paths w/ sample?? dirs to process.', nargs='*', default=None, action=SM)
    parser.add_argument('-p', '--pattern', help='Pattern for sample?? dirs. Use cwd if no matches.', default='sample??', action=SM)
    parser.add_argument('-d', '--dirs', help='List of sample?? dir names or paths to dirs to process', nargs='*', default=None, action=SM)

    # Required arguments:
    parser.add_argument('-i', '--input', help='path/points_in_tissue_space.csv relative to ./sample??', required=True, action=SM)
    parser.add_argument('-o', '--output', help='Output filename. E.g., points_in_atlas_space.csv (saves in ./sample??/atlas_space/)', required=True, action=SM)

    # Optional arguments:
    parser.add_argument('-md', '--metadata', help='path/metadata.txt. Default: parameters/metadata.txt', default="parameters/metadata.txt", action=SM)
    parser.add_argument('-r', '--reg_res', help='Resolution of registration inputs in microns. Default: 50', default='50',type=int, action=SM)
    parser.add_argument('-mi', '--miracl', help='Mode for compatibility (accounts for tif to nii reorienting)', action='store_true', default=False)




    parser.add_argument('-a', '--atlas', help='path/atlas.nii.gz for use as the fixed image (Default: atlas/atlas_CCFv3_2020_30um.nii.gz)', default='atlas/atlas_CCFv3_2020_30um.nii.gz', action=SM)
    parser.add_argument('-fri', '--fixed_reg_in', help='Reference nii header from ``reg``. Default: reg_outputs/autofl_50um_masked_fixed_reg_input.nii.gz', default="reg_outputs/autofl_50um_masked_fixed_reg_input.nii.gz", action=SM)
    parser.add_argument('-inp', '--interpol', help='Type of interpolation (linear, bSpline [default]).', default='bSpline', action=SM)
    parser.add_argument('-v', '--verbose', help='Increase verbosity.', action='store_true', default=False)
    parser.epilog = __doc__
    return parser.parse_args()

# TODO: Add commands to .toml, guide, and toctree. 

def resample_centroids(centroids, xy_res, z_res, reg_res=50, miracl=False):
    """
    Resample [and reorient] centroids to match the image preprocessing steps.

    Args:
        centroids (np.ndarray): N x 3 array of centroid coordinates (x, y, z).
        xy_res (float): Original x/y resolution in microns.
        z_res (float): Original z resolution in microns.
        reg_res (int): Target resolution for registration in microns.
        miracl (bool): Whether to apply MIRACL reorientation.

    Returns:
        np.ndarray: Resampled and reoriented centroids.
    """
    # Convert voxel coordinates to physical space
    centroids_physical = centroids * np.array([xy_res, xy_res, z_res])

    # Calculate resampling factors
    zf_xy = xy_res / reg_res
    zf_z = z_res / reg_res

    # Resample centroids to the registration resolution
    centroids_resampled = centroids_physical / np.array([zf_xy, zf_xy, zf_z])

    # Optionally reorient centroids
    if miracl:
        # Reorient using the same logic as the reorientation function
        centroids_resampled = centroids_resampled[:, [2, 0, 1]]

    return centroids_resampled

def resample_centroids(centroids, xy_res, z_res, reg_res=50, miracl=False):
    """
    Resample [and reorient] centroids to match the image preprocessing steps.

    Args:
        centroids (np.ndarray): N x 3 array of centroid coordinates (x, y, z).
        xy_res (float): Original x/y resolution in microns.
        z_res (float): Original z resolution in microns.
        reg_res (int): Target resolution for registration in microns.
        miracl (bool): Whether to apply MIRACL reorientation.

    Returns:
        np.ndarray: Resampled and reoriented centroids.
    """
    # Convert voxel coordinates to physical space
    centroids_physical = centroids * np.array([xy_res, xy_res, z_res])

    # Calculate scaling factors
    scale_xy = reg_res / xy_res  # Resample to the registration resolution
    scale_z = reg_res / z_res

    # Resample centroids to the registration resolution
    centroids_resampled = centroids_physical * np.array([scale_xy, scale_xy, scale_z])

    # Optionally reorient centroids
    if miracl:
        # Reorient using the same logic as the reorientation function
        centroids_resampled = centroids_resampled[:, [2, 0, 1]]

    return centroids_resampled

def centroids_to_nii(centroids_resampled, reg_res, sample_path):
    """
    Create a 3D binary mask from resampled centroids and save it as a NIfTI image.

    Args:
        centroids_resampled (np.ndarray): Resampled centroid coordinates.
        reg_res (float): Resolution in microns used for registration.
        sample_path (Path): Path to save the NIfTI image.
    """
    # Ensure that centroids are non-negative and within expected bounds
    max_coords = centroids_resampled.max(axis=0)
    img_shape = (int(max_coords[0] / reg_res) + 1, int(max_coords[1] / reg_res) + 1, int(max_coords[2] / reg_res) + 1)

    # Create a 3D binary image
    img = np.zeros(img_shape, dtype='uint8')

    # Set the centroid coordinates to 1 in the image
    for x, y, z in (centroids_resampled / reg_res).astype(int):
        if 0 <= x < img_shape[0] and 0 <= y < img_shape[1] and 0 <= z < img_shape[2]:
            img[x, y, z] = 1

    # Define affine transformation for the NIfTI image
    affine = np.diag([reg_res, reg_res, reg_res, 1.0])

    # Create and save the NIfTI image
    img_nii = nib.Nifti1Image(img, affine)
    img_nii.set_data_dtype(np.uint8)
    img_path = Path(sample_path) / 'centroids.nii.gz'
    nib.save(img_nii, str(img_path))
    print(f"Image saved at {img_path}")


def pad(ndarray, pad_width=0.15):
    """Pads ndarray by 15% of voxels on all sides"""
    pad_factor = 1 + 2 * pad_width
    pad_width_x = round(((ndarray.shape[0] * pad_factor) - ndarray.shape[0]) / 2)
    pad_width_y = round(((ndarray.shape[1] * pad_factor) - ndarray.shape[1]) / 2)
    pad_width_z = round(((ndarray.shape[2] * pad_factor) - ndarray.shape[2]) / 2)
    return np.pad(ndarray, ((pad_width_x, pad_width_x), (pad_width_y, pad_width_y), (pad_width_z, pad_width_z)), mode='constant')

@print_func_name_args_times()
def transform_points(points_csv, transformlist, output_csv, whichtoinvert=None):
    """Apply transformations to points using ANTsPy (https://antspy.readthedocs.io/en/latest/_modules/ants/registration/apply_transforms.html)"""
    # Load points
    points = pd.read_csv(points_csv)  # columns: x, y, z

    # Apply transformations
    transformed_points = ants.apply_transforms_to_points(3, points, transformlist, whichtoinvert)

    # Save transformed points
    transformed_points.to_csv(output_csv, index=False)

@print_func_name_args_times()
def points_to_atlas(sample_path, csv_path, fixed_reg_in, atlas, output, interpol, dtype='uint16'):
    """Warp the image to atlas space using ANTsPy.
    
    Args:
        - sample_path (Path): Path to the sample directory.
        - csv_path (Path): Path to the points CSV file.
        - fixed_reg_in (str): Name of the fixed image for registration.
        - atlas (str): Path to the atlas.
        - output (str): Path to the output.
        - interpol (str): Type of interpolation (linear, bSpline, nearestNeighbor, multiLabel).
        - dtype (str): Desired dtype for output (e.g., uint8, uint16). Default: uint16"""
    # Pad the image
    img = pad(img, pad_width=0.15)

    # Create NIfTI, set header info, and save the input for warp()
    fixed_reg_input = sample_path / fixed_reg_in
    reg_outputs_path = fixed_reg_input.parent
    warp_inputs_dir = reg_outputs_path / "warp_inputs"
    warp_inputs_dir.mkdir(exist_ok=True, parents=True)
    warp_input_path = str(warp_inputs_dir / output.name)
    print(f'\n    Setting header info and saving the input for warp() here: {warp_input_path}\n')
    img = img.astype(np.float32) # Convert the fixed image to FLOAT32 for ANTsPy
    fixed_reg_input_nii = nib.load(fixed_reg_input)
    img_nii = nib.Nifti1Image(img, fixed_reg_input_nii.affine.copy(), fixed_reg_input_nii.header)
    img_nii.set_data_dtype(np.float32) 
    nib.save(img_nii, warp_input_path)

    # Warp the image to atlas space
    print(f'\n    Warping image to atlas space\n')
    warp(reg_outputs_path, warp_input_path, atlas, output, inverse=True, interpol=interpol)

    # Optionally lower the dtype of the output if the desired dtype is not float32
    if dtype.lower() != 'float32':
        output_nii = nib.load(output)
        output_img = output_nii.get_fdata(dtype=np.float32)
        output_img = convert_dtype(output_img, dtype, scale_mode='none')
        output_nii = nib.Nifti1Image(output_img, output_nii.affine.copy(), output_nii.header)
        output_nii.header.set_data_dtype(dtype)
        nib.save(output_nii, output)


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

            output = sample_path / "atlas_space" / args.output
            output.parent.mkdir(exist_ok=True, parents=True)
            if output.exists():
                print(f"\n\n    {output} already exists. Skipping.\n")
                continue

            # Load resolutions from metadata
            metadata_path = sample_path / args.metadata
            xy_res, z_res, _, _, _ = load_image_metadata_from_txt(metadata_path)
            if xy_res is None:
                print("    [red1]./sample??/parameters/metadata.txt is missing. Generate w/ io_metadata")
                import sys ; sys.exit()

            # Load the csv with cell centroids in full resolution tissue space
            csv_path = sample_path / args.input
            centroids_df = pd.read_csv(csv_path, usecols=['x', 'y', 'z'])

            # Convert centroids to numpy array and set the dtype to float
            centroids = centroids_df.to_numpy(dtype='float')

            # Resample [and reorient] centroids to match the image preprocessing steps
            centroids_resampled = resample_centroids(centroids, xy_res, z_res, args.reg_res, args.miracl)

            # Save the resampled centroids as a NIfTI image
            centroids_to_nii(centroids_resampled, args.reg_res, sample_path)


            # # Resample the rb_img to the resolution of registration (and optionally reorient for compatibility with MIRACL)
            # img = reg_prep(img, xy_res, z_res, args.reg_res, args.zoom_order, args.miracl)

            # # Warp native image to atlas space
            # points_to_atlas(sample_path, csv_path, args.fixed_reg_in, args.atlas, output, args.interpol, dtype='uint16')

            progress.update(task_id, advance=1)

    verbose_end_msg()


if __name__ == '__main__':
    main()



# def reg_prep(ndarray, xy_res, z_res, reg_res, zoom_order, miracl):
#     """Prepare the autofluo image for ``reg`` or mimic preprocessing  for ``vstats_prep``.
    
#     Args:
#         - ndarray (np.ndarray): full res 3D autofluo image.
#         - xy_res (float): x/y resolution in microns of ndarray.
#         - z_res (float): z resolution in microns of ndarray.
#         - reg_res (int): Resample input to this resolution in microns for ``reg``.
#         - zoom_order (int): Order for resampling (scipy.ndimage.zoom).
#         - miracl (bool): Include reorientation step to mimic MIRACL's tif to .nii.gz conversion.
        
#     Returns:
#         - img_resampled (np.ndarray): Resampled image."""

#     # Resample autofluo image (for registration)
#     img_resampled = resample(ndarray, xy_res, z_res, reg_res, zoom_order=zoom_order)

#     # Optionally reorient autofluo image (mimics MIRACL's tif to .nii.gz conversion)
#     if miracl: 
#         img_resampled = reorient_for_raw_to_nii_conv(img_resampled)

#     return img_resampled

# def resample(ndarray, xy_res, z_res, res, zoom_order=1):
#     """Resample a 3D ndarray
    
#     Parameters:
#         ndarray: 3D ndarray to resample
#         xy_res: x/y voxel size in microns (for the original image)
#         z_res: z voxel size in microns
#         res: resolution in microns for the resampled image
#         zoom_order: SciPy zoom order for resampling the native image. Default: 1 (bilinear interpolation)"""
#     zf_xy = xy_res / res # Zoom factor
#     zf_z = z_res / res
#     img_resampled = ndimage.zoom(ndarray, (zf_xy, zf_xy, zf_z), order=zoom_order)
#     return img_resampled

# @print_func_name_args_times()
# def reorient_for_raw_to_nii_conv(ndarray):
#     """Reorient resampled ndarray for registration or warping to atlas space 
#     (legacy mode mimics MIRACL's tif to .nii.gz conversion)"""
#     img_reoriented = np.einsum('zyx->xzy', ndarray)
#     return np.transpose(img_reoriented, (2, 1, 0))