#!/usr/bin/env python3

""" 
This module contains functions processing 3D images: 
    - resample: Resample a 3D ndarray.
    - reorient_axes: Reorient an ndarray for registration or warping to atlas space
    - pixel_classification: Segment tif series with Ilastik.
    - pad: Pad an ndarray by a specified percentage.
    - reorient_ndarray: Reorient a 3D ndarray based on the 3 letter orientation code (using the letters RLAPSI).
    - reorient_ndarray2: Reorient a 3D ndarray based on the 3 letter orientation code (using the letters RLAPSI).
    - rolling_ball_subtraction_opencv_parallel: Subtract background from a 3D ndarray using OpenCV.
    - label_IDs: Prints label IDs > min_voxel_count (and optionally their sizes) in a 3D ndarray.
    - find_bounding_box: Finds the bounding box of all clusters or a specific cluster in a cluster index ndarray and optionally writes to file.
"""


import os
import cv2 
import nibabel as nib
import numpy as np
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from rich import print
from scipy import ndimage
from scipy.ndimage import rotate

from unravel.core.img_io import nii_to_ndarray
from unravel.core.utils import match_files, print_func_name_args_times

@print_func_name_args_times()
def resample(ndarray, xy_res, z_res, target_res=None, target_dims=None, scale=None, zoom_order=1):
    """Resample a 3D ndarray using target resolution, dimensions, or scale.

    Parameters
    ----------
    ndarray : np.ndarray
        Input 3D array to resample.
    xy_res : float
        Current resolution in the x and y dimensions (e.g., in microns).
    z_res : float
        Current resolution in the z dimension (e.g., in microns).
    target_res : float or tuple of float, optional
        Target resolution for resampling. If a single float, it is assumed to be isotropic (same for x, y, and z). If a tuple/list of three floats, it is assumed to be anisotropic (different for x/y vs. z).
    target_dims : tuple of int, optional
        Target dimensions for resampling (x, y, z). If provided, it overrides target_res.
    scale : float or list of float, optional
        Scaling factor for resampling. If a single float, it scales all dimensions equally. If a list of three floats, it scales each dimension independently.
    zoom_order : int, optional
        SciPy zoom order for interpolation. Default is 1 (linear interpolation). Use 0 for nearest-neighbor interpolation.

    Returns
    -------
    np.ndarray
        Resampled 3D array.

    Notes
    -----
    - This function assumes that the axes of the ndarray are ordered as (x, y, z).
    - The units of measurement should match for xy_res, z_res, and target_res.
    """
    if scale is not None:
        scale = np.atleast_1d(scale)
        if len(scale) == 1:
            zoom_factors = [scale[0]] * 3
        elif len(scale) == 3:
            zoom_factors = scale
        else:
            raise ValueError("Scale must be a float or list of 3 floats.")
    elif target_dims is not None:
        zoom_factors = [new / old for new, old in zip(target_dims, ndarray.shape)]
    elif target_res is not None:
        target_res = np.atleast_1d(target_res)
        if len(target_res) == 1:
            target_res = [target_res[0]] * 3
        elif len(target_res) != 3:
            raise ValueError("target_res must be a float or a list of 3 floats.")
        zoom_factors = [xy_res / target_res[0], xy_res / target_res[1], z_res / target_res[2]]
    else:
        raise ValueError("Must provide either scale, target_res, or target_dims.")

    return ndimage.zoom(ndarray, zoom_factors, order=zoom_order)

@print_func_name_args_times()
def reorient_axes(ndarray):
    """Reorient resampled ndarray for registration or warping to atlas space 
    (mimics orientation change from MIRACL's tif to .nii.gz conversion)"""
    img_reoriented = np.einsum('zyx->xzy', ndarray)
    return np.transpose(img_reoriented, (2, 1, 0))

@print_func_name_args_times()
def reverse_reorient_axes(ndarray):
    """Reorient an ndarray by rotating and flipping to correct axis order for image conversion.

    Rotates 90 degrees to the right and flips horizontally.
    
    This can reverse the reorientation done by reorient_axes().
    """
    rotated_img = rotate(ndarray, -90, reshape=True, axes=(0, 1)) # Rotate 90 degrees to the right
    flipped_img = np.fliplr(rotated_img) # Flip horizontally
    return flipped_img

@print_func_name_args_times()
def pixel_classification(tif_dir, ilastik_project, output_dir, ilastik_executable=None):
    """Segment tif series with Ilastik using pixel classification."""

    if ilastik_executable is None:
        print("\n    [red1]Ilastik executable path not provided. Please provide the path to the Ilastik executable.\n")
        return

    try:
        tif_list = match_files('*.tif', base_path=tif_dir)
    except ValueError:
        print(f"\n    [red1]No TIF files found in {tif_dir}.\n")
        return
    
    cmd = [
        ilastik_executable, # Path to ilastik executable as a string
        '--headless',
        '--project', str(ilastik_project),
        '--export_source', 'Simple Segmentation',
        '--output_format', 'tif',
        '--output_filename_format', f'{str(output_dir)}/{{nickname}}.tif'
    ] + tif_list
    print("\n    Running Ilastik with command:\n", ' '.join(cmd[:10]), ' '.join(tif_list[:3]), f'[default bold]...\n')
    result = subprocess.run(cmd, capture_output=True, text=True, shell=(os.name == 'nt'))
    if result.returncode != 0:
        print("\n    Ilastik failed with error:\n", result.stderr)
    else:
        print("    Ilastik completed successfully.")

@print_func_name_args_times()
def pad(ndarray, pad_percent=0.25):
    """Pads ndarray by a specified percentage.

    Parameters:
    -----------
    ndarray : numpy.ndarray
        Input 3D ndarray to pad.

    pad_percent : float
        Percentage of padding to add to each dimension. Default: 0.25 (25%%).

    Returns:
    --------
    padded_ndarray : numpy.ndarray
        Padded 3D ndarray.
    """
    pad_factor = 1 + 2 * pad_percent
    pad_width_x = round(((ndarray.shape[0] * pad_factor) - ndarray.shape[0]) / 2)
    pad_width_y = round(((ndarray.shape[1] * pad_factor) - ndarray.shape[1]) / 2)
    pad_width_z = round(((ndarray.shape[2] * pad_factor) - ndarray.shape[2]) / 2)
    return np.pad(ndarray, ((pad_width_x, pad_width_x), (pad_width_y, pad_width_y), (pad_width_z, pad_width_z)), mode='constant')

@print_func_name_args_times()
def reorient_ndarray(data, orientation_string):
    """Reorient a 3D ndarray based on the 3 letter orientation code (using the letters RLAPSI). Assumes initial orientation is RAS (NIFTI convention)."""
    
    # Orientation reference for RAS system
    ref_orient = "RAS" # R=Right, A=Anterior, S=Superior (conventional orientation of NIFTI images)

    # Ensure valid orientation_string
    if not set(orientation_string).issubset(set(ref_orient + "LIP")):
        raise ValueError("Invalid orientation code. Must be a 3-letter code consisting of RLAPSI.")
    if len(orientation_string) != 3:
        raise ValueError("Invalid orientation code. Must be a 3-letter code consisting of RLAPSI.")

    # Compute the permutation indices and flips
    permutation = [ref_orient.index(orient) for orient in orientation_string]
    flips = [(slice(None, None, -1) if orient in "LIP" else slice(None)) for orient in orientation_string]

    # Reorient the data using numpy's advanced indexing
    reoriented_data = data[flips[0], flips[1], flips[2]]
    reoriented_data = np.transpose(reoriented_data, permutation)

    return reoriented_data

@print_func_name_args_times()
def reorient_ndarray2(ndarray, orientation_string):
    """Reorient a 3D ndarray based on the 3 letter orientation code (using the letters RLAPSI). Assumes initial orientation is RAS (NIFTI convention)."""

    # Define the anatomical direction mapping. The first letter is the direction of the first axis, etc.
    direction_map = {
        'R': 0, 'L': 0,
        'A': 1, 'P': 1,
        'I': 2, 'S': 2
    }

    # Define the flip direction
    flip_map = {
        'R': True, 'L': False,
        'A': False, 'P': True,
        'I': True, 'S': False
    }

    # Orientation reference for RAS system
    ref_orient = "RAS"

    # Ensure valid orientation_string
    if not set(orientation_string).issubset(set(ref_orient + "LIP")):
        raise ValueError("Invalid orientation code. Must be a 3-letter code consisting of RLAPSI.")
    if len(orientation_string) != 3:
        raise ValueError("Invalid orientation code. Must be a 3-letter code consisting of RLAPSI.")

    # Determine new orientation based on the code
    new_axes_order = [direction_map[c] for c in orientation_string]

    # Reorder the axes
    reoriented_volume = np.transpose(ndarray, axes=new_axes_order)

    # Flip axes as necessary
    for idx, c in enumerate(orientation_string):
        if flip_map[c]:
            reoriented_volume = np.flip(reoriented_volume, axis=idx)

    return reoriented_volume


####### Rolling ball background subraction #######

def process_slice(slice, struct_element):
    """Subtract background from <slice> using OpenCV."""
    smoothed_slice = cv2.morphologyEx(slice, cv2.MORPH_OPEN, struct_element)
    return slice - smoothed_slice

@print_func_name_args_times()
def rolling_ball_subtraction_opencv_parallel(ndarray, radius, threads=8):
    """Subtract background from <ndarray> using OpenCV. 
    Uses multiple threads to process slices in parallel.
    Radius is the radius of the rolling ball in pixels.
    Returns ndarray with background subtracted.
    """
    struct_element = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2*radius+1, 2*radius+1)) # 2D disk
    bkg_subtracted_img = np.empty_like(ndarray) # Preallocate the result array
    num_cores = min(len(ndarray), threads) # Number of available CPU cores
    with ThreadPoolExecutor(max_workers=num_cores) as executor: # Process slices in parallel
        # Map the process_slice function to each slice in ndarray and store the result in result. Each process_slice call gets a slice and the struct_element as arguments.
        # executor.map() returns an iterator with the results of each process_slice call. The iterator is consumed and the results are stored in result.
        # ndarray is a list of slices
        # [struct_element]*len(ndarray) is a list of struct_elements of length len(ndarray)
        for i, background_subtracted_slice in enumerate(executor.map(process_slice, ndarray, [struct_element]*len(ndarray))): 
            bkg_subtracted_img[i] = background_subtracted_slice
    return bkg_subtracted_img

print_func_name_args_times()
def label_IDs(ndarray, min_voxel_count=1, print_IDs=False, print_sizes=False):
    """
    This finds and prints unique intensities in the ndarry with more than min_voxel_count voxels (does not check for connectedness).

    Optionally, it also prints the number of voxels for each label ID (intensity).

    Parameters
    ----------
    ndarray : numpy.ndarray
        Input array with integer intensities.
    min_voxel_count : int, optional
        Minimum size threshold for each intensity in voxels. Labels smaller than this
        threshold are ignored. Default is 1.
    print_IDs : bool, optional
        If True, print the IDs of labels above the minimum size threshold. Default is False.
    print_sizes : bool, optional
        If True, print both the IDs and sizes of label IDs above the minimum size threshold.
        Default is False.

    Returns
    -------
    list of int
        List of unique label IDs (intensities) that meet the minimum size threshold.

    Examples
    --------
    >>> import numpy as np
    >>> array = np.array([[0, 1, 1], [0, 2, 2], [3, 3, 3]])
    >>> cluster_IDs(array, min_voxel_count=2)
    [1, 2, 3]

    >>> cluster_IDs(array, min_voxel_count=2, print_IDs=True)
    1 2 3

    >>> cluster_IDs(array, min_voxel_count=2, print_sizes=True)
    ID: 1, Size: 2
    ID: 2, Size: 2
    ID: 3, Size: 3
    """

    # Get unique intensities and their counts
    unique_intensities, counts = np.unique(ndarray[ndarray > 0], return_counts=True)

    # Filter clusters based on size
    clusters_above_minextent = [intensity for intensity, count in zip(unique_intensities, counts) if count >= min_voxel_count]
    
    # Print cluster IDs
    if print_sizes:
        print(f"\nID,Size")
    for idx, cluster_id in enumerate(clusters_above_minextent):
        if print_sizes:
            print(f"{int(cluster_id)},{counts[idx]}")
        elif print_IDs:
            print(int(cluster_id), end=' ')
    if print_IDs: # Removes trailing %
        print()
    
    clusters = [int(cluster_id) for cluster_id in clusters_above_minextent]

    return clusters

print_func_name_args_times()
def find_bounding_box(ndarray, cluster_ID=None, output_file_path=None):
    """
    Finds the bounding box of all clusters or a specific cluster in a cluster index ndarray and optionally writes to file.

    Parameters:
        ndarray: 3D numpy array to search within.
        cluster_ID (int): Cluster intensity to find bbox for. If None, return bbox for all clusters.
        output_file_path (str): File path to write the bounding box.
    """
    
    # Initialize views based on whether we are looking for a specific cluster_ID or any cluster
    if cluster_ID is not None:
        # Find indices where ndarray equals cluster_ID for each dimension
        views = [np.where(ndarray == int(cluster_ID))[i] for i in range(3)]
    else:
        # Find indices where ndarray has any value (greater than 0) for each dimension
        views = [np.any(ndarray, axis=i) for i in range(3)]

    # Initialize min and max indices
    min_max_indices = []

    # Find min and max indices for each dimension
    for i, view in enumerate(views):
        if cluster_ID is not None:
            indices = views[i]
        else:
            indices = np.where(view)[0]

        # Check if there are any indices found
        if len(indices) > 0:
            min_index = int(min(indices))
            max_index = int(max(indices) + 1)
        else:
            # Handle empty array case by setting min and max to zero
            min_index = 0
            max_index = 0

        min_max_indices.append((min_index, max_index))

    # Unpack indices for easier referencing
    xmin, xmax, ymin, ymax, zmin, zmax = [idx for dim in min_max_indices for idx in dim]

    # Write to file if specified
    if output_file_path:
        with open(output_file_path, "w") as file:
            file.write(f"{xmin}:{xmax}, {ymin}:{ymax}, {zmin}:{zmax}")

    return xmin, xmax, ymin, ymax, zmin, zmax

print_func_name_args_times()
def crop(ndarray, bbox: str):
    """Crop an ndarray to the specified bounding box (xmin:xmax, ymin:ymax, zmin:zmax)"""
    # Split the bounding box string into coordinates
    bbox_coords = bbox.split(',')
    xmin, xmax = [int(x) for x in bbox_coords[0].split(':')]
    ymin, ymax = [int(y) for y in bbox_coords[1].split(':')]
    zmin, zmax = [int(z) for z in bbox_coords[2].split(':')]

    # Crop and return the ndarray
    return ndarray[xmin:xmax, ymin:ymax, zmin:zmax]