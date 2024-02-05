#!/usr/bin/env python3

""" This module contains functions for loading, saving, and processing 3D images. 

The main functions are:
- load_3D_img: Load a 3D image from a .czi, .nii.gz, or .tif series and return the ndarray.
    - Supported file types: .czi, .ome.tif series, .tif series, .nii.gz, .h5:
    - Loading functions (load_czi, load_tifs, load_nii, load_h5) return the ndarray and optionally resolutions and/or metadata.
    - Parameters:
        - desired_axis_order=xyz (other option: "zyx")
        - If return_res=True returns: ndarray, xy_res, z_res (resolution = voxel size in microns)
        - If return_metadata=True returns: ndarray, xy_res, z_res, x_dim, y_dim, z_dim (image dimensions)
        - If save_metadata=True saves metadata to parameters/metadata.txt
    - Helper functions: resolve_path, extract_resolution, load_image_metadata_from_txt, save_metadata_to_file, handle_metadata, return_3D_img
- Functions for saving ndarrays:
    - save_as_nii: Save a numpy array as a .nii.gz image.
    - save_as_tifs: Save a 3D ndarray as a series of tif images.
- Image processing functions:
    - resample: Resample a 3D ndarray.
    - resample_reorient: Resample and reorient an ndarray for registration or warping to atlas space.
    - ilastik_segmentation: Segment tif series with Ilastik.
    - pad_image: Pad an ndarray by a specified percentage.
    - reorient_ndarray: Reorient a 3D ndarray based on the 3 letter orientation code (using the letters RLAPSI).
    - reorient_ndarray2: Reorient a 3D ndarray based on the 3 letter orientation code (using the letters RLAPSI).
    - rolling_ball_subtraction_opencv_parallel: Subtract background from a 3D ndarray using OpenCV.
    - cluster_IDs: Prints cluster IDs for clusters > minextent voxels.
    - find_bounding_box: Finds the bounding box of all clusters or a specific cluster in a cluster index ndarray and optionally writes to file.
"""

import re
import cv2 
import h5py
import nibabel as nib
import numpy as np
import subprocess
import tifffile
from aicspylibczi import CziFile
from concurrent.futures import ThreadPoolExecutor
from glob import glob
from lxml import etree
from pathlib import Path
from rich import print
from scipy import ndimage
from tifffile import imwrite 
from unravel_utils import print_func_name_args_times


# Load 3D image (load_3D_img()), get/save metadata, and return ndarray [with metadata]
def return_3D_img(ndarray, return_metadata=False, return_res=False, xy_res=None, z_res=None, x_dim=None, y_dim=None, z_dim=None):
    """Return the 3D image ndarray and optionally resolutions (xy_res, z_res) or metadata (xy_res, z_res, x_dim, y_dim, z_dim). """
    if return_metadata:
        return ndarray, xy_res, z_res, x_dim, y_dim, z_dim
    elif return_res:
        return ndarray, xy_res, z_res
    return ndarray

def handle_metadata(file_path, ndarray, return_res=False, return_metadata=False, xy_res=None, z_res=None, save_metadata=False):
    """Extract and handle metadata, including saving to a file if requested. Returns: xy_res, z_res, x_dim, y_dim, z_dim"""
    if return_res or return_metadata:
        if xy_res is None and z_res is None:
            xy_res, z_res = extract_resolution(file_path)
        x_dim, y_dim, z_dim = ndarray.shape
        if save_metadata:
            save_metadata_to_file(xy_res, z_res, x_dim, y_dim, z_dim, save_metadata="parameters/metadata.txt")
    return xy_res, z_res, x_dim, y_dim, z_dim

@print_func_name_args_times()
def extract_resolution(file_path):
    """Extract resolution from image metadata. Returns xy_res, z_res in microns."""
    if str(file_path).endswith('.czi'):
        xml_root = file_path.meta
        scaling_info = xml_root.find(".//Scaling")
        xy_res = float(scaling_info.find("./Items/Distance[@Id='X']/Value").text) * 1e6
        z_res = float(scaling_info.find("./Items/Distance[@Id='Z']/Value").text) * 1e6
    elif str(file_path).endswith('.ome.tif') or str(file_path).endswith('.tif'):
        with tifffile.TiffFile(file_path) as tif:
            meta = tif.pages[0].tags
            ome_xml_str = meta['ImageDescription'].value
            ome_xml_root = etree.fromstring(ome_xml_str.encode('utf-8'))
            default_ns = ome_xml_root.nsmap[None]
            pixels_element = ome_xml_root.find(f'.//{{{default_ns}}}Pixels')
            xy_res = float(pixels_element.get('PhysicalSizeX'))
            z_res = float(pixels_element.get('PhysicalSizeZ'))
    elif str(file_path).endswith('.nii.gz'):
        img = nib.load(file_path)
        affine = img.affine
        xy_res = abs(affine[0, 0] * 1e3) # Convert from mm to um
        z_res = abs(affine[2, 2] * 1e3)
    elif str(file_path).endswith('.h5'):
        with h5py.File(h5py, 'r') as f:
            full_res_dataset_name = next(iter(f.keys())) # Assumes that full res data is 1st in the dataset list
            print(f"\n    Loading HDF5 dataset: {full_res_dataset_name}\n")
            dataset = f[full_res_dataset_name] 
            res = dataset.attrs['element_size_um'] # z, y, x voxel sizes in microns (ndarray)
            xy_res = res[1]
            z_res = res[0]  
    return xy_res, z_res

@print_func_name_args_times()
def load_czi(czi_path, channel, desired_axis_order="xyz", return_res=False, return_metadata=False, save_metadata=None, xy_res=None, z_res=None):
    """Loads image.czi channel. Returns the ndarray [and res: (xy_res, z_res) or metadata: (xy_res, z_res, x_dim, y_dim, z_dim)]."""
    ndarray = np.squeeze(czi_path.read_image(C=channel)[0])
    ndarray = np.transpose(ndarray, (2, 1, 0)) if desired_axis_order == "xyz" else ndarray
    xy_res, z_res, x_dim, y_dim, z_dim = handle_metadata(czi_path, ndarray, return_res, return_metadata, xy_res, z_res, save_metadata)
    return return_3D_img(ndarray, return_metadata, return_res, xy_res, z_res, x_dim, y_dim, z_dim)
    
@print_func_name_args_times()
def load_tifs(tif_path, desired_axis_order="xyz", return_res=False, return_metadata=False, save_metadata=None, xy_res=None, z_res=None, parallel_loading=True):
    """Loads tif series [in parallel]. Returns the ndarray [and res: (xy_res, z_res) or metadata: (xy_res, z_res, x_dim, y_dim, z_dim)]."""
    def load_single_tif(tif_file):
        """Load a single tif file using OpenCV and return ndarray."""
        img = cv2.imread(str(tif_file), cv2.IMREAD_UNCHANGED)
        return img
    tif_files = sorted(Path(tif_path).parent.glob("*.tif"))
    if parallel_loading:
        with ThreadPoolExecutor() as executor:
            tifs_stacked = list(executor.map(load_single_tif, tif_files))
    else:
        tifs_stacked = []
        for tif_file in tif_files:
            tifs_stacked.append(load_single_tif(tif_file))
    ndarray = np.stack(tifs_stacked, axis=0)
    ndarray = np.transpose(ndarray, (2, 1, 0)) if desired_axis_order == "xyz" else ndarray
    xy_res, z_res, x_dim, y_dim, z_dim = handle_metadata(tif_files[0], ndarray, return_res, return_metadata, xy_res, z_res, save_metadata)
    return return_3D_img(ndarray, return_metadata, return_res, xy_res, z_res, x_dim, y_dim, z_dim)

@print_func_name_args_times()
def load_nii(nii_path, desired_axis_order="xyz", return_res=False, return_metadata=False, save_metadata=None):
    """Load a .nii.gz image and return the ndarray. Returns the ndarray [and res: (xy_res, z_res) or metadata: (xy_res, z_res, x_dim, y_dim, z_dim)]."""
    img = nib.load(nii_path)
    data_dtype = img.header.get_data_dtype()
    ndarray = np.asanyarray(img.dataobj).astype(data_dtype)
    ndarray = np.squeeze(ndarray)
    ndarray = np.transpose(ndarray, (2, 1, 0)) if desired_axis_order == "zyx" else ndarray
    xy_res, z_res, x_dim, y_dim, z_dim = handle_metadata(nii_path, ndarray, return_res, return_metadata, save_metadata=save_metadata)
    return return_3D_img(ndarray, return_metadata, return_res, xy_res, z_res, x_dim, y_dim, z_dim)
    
def load_h5(hdf5_path, desired_axis_order="xyz", return_res=False, return_metadata=False, save_metadata=None):
    """Load full res image from an HDF5 image (.h5). Returns the ndarray [and res: (xy_res, z_res) or metadata: (xy_res, z_res, x_dim, y_dim, z_dim)]."""
    with h5py.File(hdf5_path, 'r') as f:
        full_res_dataset_name = next(iter(f.keys())) # Assumes first dataset = full res image
        dataset = f[full_res_dataset_name]
        print(f"\n    Loading {full_res_dataset_name} as ndarray")
        ndarray = dataset[:]  # Load the full res image into memory (if not enough RAM, chunck data [e.g., w/ dask array])
        ndarray = np.transpose(ndarray, (2, 1, 0)) if desired_axis_order == "xyz" else ndarray
        xy_res, z_res, x_dim, y_dim, z_dim = handle_metadata(hdf5_path, ndarray, return_res, return_metadata, save_metadata=save_metadata)
    return return_3D_img(ndarray, return_metadata, return_res, xy_res, z_res, x_dim, y_dim, z_dim)
    
def resolve_path(file_path, extensions):
    """Returns the path to the first matching file in dir or file itself if it matches the extensions."""
    path = Path(file_path)
    if path.is_dir():
        for extension in extensions:
            sorted_files = sorted(path.glob(f"*{extension}"))
            first_match = next(iter(sorted_files), None)
            if first_match:
                return first_match
    else:
        # If it's a file, check if it matches any of the extensions
        for extension in extensions:
            if str(path).endswith(extension):
                return path
    return None

def resolve_relative_path(sample_path, rel_path_or_glob_pattern):
    """Resolve and return the path to a file or directory relative to the given sample_path.
    If the file or directory does not exist, return the first glob match within the sample_path.
    If no matches are found, return None."""
    
    # Check if the exact path exists
    exact_path = Path(sample_path, rel_path_or_glob_pattern)
    if exact_path.exists():
        return exact_path

    # If not, attempt to find a match using glob pattern
    glob_matches = sorted(Path(sample_path).glob(rel_path_or_glob_pattern))
    if glob_matches:
        return glob_matches[0]  # Return the first match

    return None

@print_func_name_args_times()
def load_3D_img(file_path, channel=0, desired_axis_order="xyz", return_res=False, return_metadata=False, xy_res=None, z_res=None, save_metadata=None): 
    """Load <file_path> (.czi, .nii.gz, or .tif).
    file_path can be path to image file or dir (uses first *.czi, *.tif, or *.nii.gz match)
    Default: desired_axis_order=xyz (other option: axis_order="zyx")
    Default: returns: ndarray
    If return_res=True returns: ndarray, xy_res, z_res (resolution in um)
    """ 

    # Resolve the file path to the first matching file
    path = resolve_path(file_path, ['.czi', '.tif', '.nii.gz'])
    if not Path(path).exists():
        raise FileNotFoundError(f"No compatible image files found in {file_path}. Supported file types: .czi, .tif, .nii.gz")
    
    if str(path).endswith('.czi'):
        print(f"\n    [default]Loading channel {channel} from {path} (channel 0 is the first channel)")
    else: 
        print(f"\n    [default]Loading {path}")

    # Load image based on file type and optionally return resolutions
    try:
        if str(path).endswith('.czi'):
            czi = CziFile(path)
            return load_czi(czi, channel, desired_axis_order, return_res, return_metadata, save_metadata, xy_res, z_res)
        elif str(path).endswith('.ome.tif') or str(path).endswith('.tif'):
            return load_tifs(path, desired_axis_order, return_res, return_metadata, save_metadata, xy_res, z_res, parallel_loading=True)
        elif str(path).endswith('.nii.gz'):
            return load_nii(path, desired_axis_order, return_res, return_metadata, save_metadata, xy_res, z_res)
        elif str(path).endswith('.h5'):
            return load_h5(path, desired_axis_order, return_res, return_metadata, save_metadata, xy_res, z_res)
        else:
            raise ValueError(f"Unsupported file type: {path.suffix}. Supported file types: .czi, .ome.tif, .tif, .nii.gz, .h5")
    except (FileNotFoundError, ValueError) as e:
        print(f"\n    [red bold]Error: {e}\n")
        import sys ; sys.exit()

def save_metadata_to_file(xy_res, z_res, x_dim, y_dim, z_dim, save_metadata='parameters/metadata.txt'):
    """Save metadata to .txt file"""
    save_metadata = Path(save_metadata)
    save_metadata.parent.mkdir(parents=True, exist_ok=True)
    if not save_metadata.exists():
        with save_metadata.open('w') as f:
            f.write(f"Width:  {x_dim*xy_res} microns ({x_dim})\n")
            f.write(f"Height:  {y_dim*xy_res} microns ({y_dim})\n")
            f.write(f"Depth:  {z_dim*z_res} microns ({z_dim})\n")
            f.write(f"Voxel size: {xy_res}x{xy_res}x{z_res} micron^3\n")    

def load_image_metadata_from_txt():
    """Loads ./parameters/metadata* and returns xy_res, z_res, x_dim, y_dim, z_dim | None if file not found."""
    file_paths = glob('parameters/metadata*')
    if file_paths:
        with open(file_paths[0], 'r') as file:
            for line in file:
                dim_match = re.compile(r'(Width|Height|Depth):\s+[\d.]+ microns \((\d+)\)').search(line)
                if dim_match:
                    dim = dim_match.group(1)
                    dim_res = float(dim_match.group(2))
                    if dim == 'Width':
                        x_dim = int(dim_res)
                    elif dim == 'Height':
                        y_dim = int(dim_res)
                    elif dim == 'Depth':
                        z_dim = int(dim_res)

                voxel_match = re.compile(r'Voxel size: ([\d.]+)x([\d.]+)x([\d.]+) micron\^3').search(line)
                if voxel_match:
                    xy_res = float(voxel_match.group(1))
                    z_res = float(voxel_match.group(3))
    else:
        return None
    return xy_res, z_res, x_dim, y_dim, z_dim


####### Save images #######

@print_func_name_args_times()
def save_as_nii(ndarray, output, xy_res, z_res, data_type):
    """Save a numpy array as a .nii.gz image."""

    output = Path(output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    
    # Create the affine matrix with the appropriate resolutions (converting microns to mm)
    affine = np.diag([xy_res / 1000, xy_res / 1000, z_res / 1000, 1])
    
    # Create and save the NIFTI image
    nifti_img = nib.Nifti1Image(ndarray, affine)
    nifti_img.header.set_data_dtype(data_type)
    nib.save(nifti_img, str(output))    
    print(f"\n    Output: [default bold]{output}")


@print_func_name_args_times()
def save_as_tifs(ndarray, tif_dir_out, ndarray_axis_order="xyz"):
    """Save <ndarray> as tifs in <Path(tif_dir_out)>"""
    tif_dir_out.mkdir(parents=True, exist_ok=True)
    if ndarray_axis_order == "xyz":
        ndarray = np.transpose(ndarray, (2, 1, 0)) # Transpose to zyx (tiff expects zyx)
    for i, slice_ in enumerate(ndarray):
        slice_file_path = tif_dir_out / f"slice_{i:04d}.tif"
        imwrite(str(slice_file_path), slice_)
    print(f"\n    Output: [default bold]{tif_dir_out}")


####### Image processing #######

@print_func_name_args_times()
def resample(ndarray, xy_res, z_res, res, zoom_order=1):
    """Resample a 3D ndarray"""
    zf_xy = xy_res / res # Zoom factor
    zf_z = z_res / res
    img_resampled = ndimage.zoom(ndarray, (zf_xy, zf_xy, zf_z), order=zoom_order)
    return img_resampled

@print_func_name_args_times()
def resample_reorient(ndarray, xy_res, z_res, res, zoom_order=1): # Mimics MIRACL's tif to .nii.gz conversion
    """Resample and reorient an ndarray for registration or warping to atlas space."""
    img_resampled = resample(ndarray, xy_res, z_res, res, zoom_order=1)
    img_reoriented = np.einsum('zyx->xzy', img_resampled)
    img_reoriented = np.transpose(img_reoriented, (2, 1, 0))
    return img_reoriented

@print_func_name_args_times()
def ilastik_segmentation(tif_dir, ilastik_project, output_dir, ilastik_log=None, args=None):
    """Segment tif series with Ilastik."""
    tif_dir = str(Path(tif_dir).resolve())
    tif_list = sorted(glob(f"{tif_dir}/*.tif"))
    ilastik_project = str(Path(ilastik_project).resolve())
    output_dir = str(Path(output_dir).resolve())
    output_dir_Path = Path(output_dir).resolve()
    cmd = [
        'run_ilastik.sh',
        '--headless',
        '--project', ilastik_project,
        '--export_source', 'Simple Segmentation',
        '--output_format', 'tif',
        '--output_filename_format', f'{output_dir}/{{nickname}}.tif',
    ] + tif_list
    if not output_dir_Path.exists():
        if ilastik_log == None:
            subprocess.run(cmd)
        else:
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

@print_func_name_args_times()
def pad_image(ndarray, pad_width=0.15):
    """Pads ndarray by 15% of voxels on all sides"""
    pad_width = int(pad_width * ndarray.shape[0])
    padded_img = np.pad(ndarray, [(pad_width, pad_width)] * 3, mode='constant')
    return padded_img

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
def cluster_IDs(ndarray, min_extent=100, print_IDs=False, print_sizes=False):
    """Prints cluster IDs [and sizes] for clusters > minextent voxels"""

    # Get unique intensities and their counts
    unique_intensities, counts = np.unique(ndarray[ndarray > 0], return_counts=True)

    # Filter clusters based on size
    clusters_above_minextent = [intensity for intensity, count in zip(unique_intensities, counts) if count >= min_extent]
    
    # Print cluster IDs
    for idx, cluster_id in enumerate(clusters_above_minextent):
        if print_sizes:
            print(f"ID: {int(cluster_id)}, Size: {counts[idx]}")
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