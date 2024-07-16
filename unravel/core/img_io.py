#!/usr/bin/env python3

"""
This module contains functions for loading and saving 3D images.

Main Functions:
---------------
- load_3D_img: Load a 3D image from a .czi, .nii.gz, or .tif series and return the ndarray.
- save_as_nii: Save a numpy array as a .nii.gz image.
- save_as_tifs: Save a 3D ndarray as a series of tif images.

Helper Functions:
-----------------
- extract_resolution
- load_image_metadata_from_txt
- save_metadata_to_file
- metadata
- return_3D_img
"""

import re
import cv2 
import dask.array as da
import h5py
import nibabel as nib
import numpy as np
import tifffile
import zarr
from aicspylibczi import CziFile
from concurrent.futures import ThreadPoolExecutor
from glob import glob
from lxml import etree
from pathlib import Path
from rich import print
from tifffile import imwrite 

from unravel.core.utils import print_func_name_args_times


# Load 3D image (load_3D_img()), get/save metadata, and return ndarray [with metadata]

def return_3D_img(ndarray, return_metadata=False, return_res=False, xy_res=None, z_res=None, x_dim=None, y_dim=None, z_dim=None):
    """
    Return the 3D image ndarray and optionally resolutions (xy_res, z_res) or metadata (xy_res, z_res, x_dim, y_dim, z_dim).

    Parameters
    ----------
    ndarray : ndarray
        The 3D image array.
    return_metadata : bool, optional
        Whether to return metadata. Default is False.
    return_res : bool, optional
        Whether to return resolutions. Default is False.
    xy_res : float, optional
        The resolution in the xy-plane.
    z_res : float, optional
        The resolution in the z-plane.
    x_dim : int, optional
        The size of the image in the x-dimension.
    y_dim : int, optional
        The size of the image in the y-dimension.
    z_dim : int, optional
        The size of the image in the z-dimension.

    Returns
    -------
    ndarray
        The 3D image array.
    tuple, optional
        If return_res is True, returns (ndarray, xy_res, z_res).
    tuple, optional
        If return_metadata is True, returns (ndarray, xy_res, z_res, x_dim, y_dim, z_dim).
    """
    if return_metadata:
        return ndarray, xy_res, z_res, x_dim, y_dim, z_dim
    elif return_res:
        return ndarray, xy_res, z_res
    return ndarray

def metadata(file_path, ndarray, return_res=False, return_metadata=False, xy_res=None, z_res=None, save_metadata=None):
    """
    Extract and handle metadata, including saving to a file if requested.

    Parameters
    ----------
    file_path : str
        The path to the image file.
    ndarray : ndarray
        The 3D image array.
    return_res : bool, optional
        Whether to return resolutions. Default is False.
    return_metadata : bool, optional
        Whether to return metadata. Default is False.
    xy_res : float, optional
        The resolution in the xy-plane.
    z_res : float, optional
        The resolution in the z-plane.
    save_metadata : str, optional
        Path to save metadata file. Default is None.

    Returns
    -------
    tuple
        Returns (xy_res, z_res, x_dim, y_dim, z_dim).
    """
    x_dim, y_dim, z_dim = None, None, None
    if return_res or return_metadata:
        if xy_res is None and z_res is None:
            xy_res, z_res = extract_resolution(file_path)
        x_dim, y_dim, z_dim = ndarray.shape
        if save_metadata:
            save_metadata_to_file(xy_res, z_res, x_dim, y_dim, z_dim, save_metadata=save_metadata)
    return xy_res, z_res, x_dim, y_dim, z_dim

def extract_resolution(img_path):
    """
    Extract resolution from image metadata.

    Parameters
    ----------
    img_path : str
        The path to the image file.

    Returns
    -------
    tuple
        Returns (xy_res, z_res) in microns.
    """
    xy_res, z_res = None, None
    if str(img_path).endswith('.czi'):
        czi = CziFile(img_path)
        xml_root = czi.meta
        scaling_info = xml_root.find(".//Scaling")
        xy_res = float(scaling_info.find("./Items/Distance[@Id='X']/Value").text) * 1e6
        z_res = float(scaling_info.find("./Items/Distance[@Id='Z']/Value").text) * 1e6
    elif str(img_path).endswith('.ome.tif') or str(img_path).endswith('.tif'):
        with tifffile.TiffFile(img_path) as tif:
            meta = tif.pages[0].tags
            ome_xml_str = meta['ImageDescription'].value
            ome_xml_root = etree.fromstring(ome_xml_str.encode('utf-8'))
            default_ns = ome_xml_root.nsmap[None]
            pixels_element = ome_xml_root.find(f'.//{{{default_ns}}}Pixels')
            xy_res = float(pixels_element.get('PhysicalSizeX'))
            z_res = float(pixels_element.get('PhysicalSizeZ'))
    elif str(img_path).endswith('.nii.gz'):
        img = nib.load(img_path)
        affine = img.affine
        xy_res = abs(affine[0, 0] * 1e3) # Convert from mm to um
        z_res = abs(affine[2, 2] * 1e3)
    elif str(img_path).endswith('.h5'):
        with h5py.File(h5py, 'r') as f:
            full_res_dataset_name = next(iter(f.keys())) # Assumes that full res data is 1st in the dataset list
            print(f"\n    Loading HDF5 dataset: {full_res_dataset_name}\n")
            dataset = f[full_res_dataset_name] 
            res = dataset.attrs['element_size_um'] # z, y, x voxel sizes in microns (ndarray)
            xy_res = res[1]
            z_res = res[0]  
    return xy_res, z_res

@print_func_name_args_times()
def load_czi(czi_path, channel=0, desired_axis_order="xyz", return_res=False, return_metadata=False, save_metadata=None, xy_res=None, z_res=None):
    """
    Load a .czi image and return the ndarray.

    Parameters
    ----------
    czi_path : str
        The path to the .czi file.
    channel : int, optional
        The channel to load. Default is 0.
    desired_axis_order : str, optional
        The desired order of the image axes. Default is 'xyz'.
    return_res : bool, optional
        Whether to return resolutions. Default is False.
    return_metadata : bool, optional
        Whether to return metadata. Default is False.
    save_metadata : str, optional
        Path to save metadata file. Default is None.
    xy_res : float, optional
        The resolution in the xy-plane.
    z_res : float, optional
        The resolution in the z-plane.

    Returns
    -------
    ndarray
        The loaded 3D image array.
    tuple, optional
        If return_res is True, returns (ndarray, xy_res, z_res).
    tuple, optional
        If return_metadata is True, returns (ndarray, xy_res, z_res, x_dim, y_dim, z_dim).
    """
    czi = CziFile(czi_path)
    ndarray = np.squeeze(czi.read_image(C=channel)[0])
    ndarray = np.transpose(ndarray, (2, 1, 0)) if desired_axis_order == "xyz" else ndarray
    xy_res, z_res, x_dim, y_dim, z_dim = metadata(czi_path, ndarray, return_res, return_metadata, xy_res, z_res, save_metadata)
    return return_3D_img(ndarray, return_metadata, return_res, xy_res, z_res, x_dim, y_dim, z_dim)
    
@print_func_name_args_times()
def load_tifs(tif_path, desired_axis_order="xyz", return_res=False, return_metadata=False, save_metadata=None, xy_res=None, z_res=None, parallel_loading=True):
    """
    Load a series of .tif images and return the ndarray.

    Parameters
    ----------
    tif_path : str
        The path to the .tif files.
    desired_axis_order : str, optional
        The desired order of the image axes. Default is 'xyz'.
    return_res : bool, optional
        Whether to return resolutions. Default is False.
    return_metadata : bool, optional
        Whether to return metadata. Default is False.
    save_metadata : str, optional
        Path to save metadata file. Default is None.
    xy_res : float, optional
        The resolution in the xy-plane.
    z_res : float, optional
        The resolution in the z-plane.
    parallel_loading : bool, optional
        Whether to load images in parallel. Default is True.

    Returns
    -------
    ndarray
        The loaded 3D image array.
    tuple, optional
        If return_res is True, returns (ndarray, xy_res, z_res).
    tuple, optional
        If return_metadata is True, returns (ndarray, xy_res, z_res, x_dim, y_dim, z_dim).
    """
    def load_single_tif(tif_file):
        """Load a single .tif file using OpenCV and return the ndarray."""
        img = cv2.imread(str(tif_file), cv2.IMREAD_UNCHANGED)
        if img is None:
            raise ValueError(f"Failed to load image: {tif_file}")
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
    xy_res, z_res, x_dim, y_dim, z_dim = metadata(tif_files[0], ndarray, return_res, return_metadata, xy_res, z_res, save_metadata)
    return return_3D_img(ndarray, return_metadata, return_res, xy_res, z_res, x_dim, y_dim, z_dim)

@print_func_name_args_times()
def load_nii(nii_path, desired_axis_order="xyz", return_res=False, return_metadata=False, save_metadata=None, xy_res=None, z_res=None):
    """
    Load a .nii.gz image and return the ndarray.

    Parameters
    ----------
    nii_path : str
        The path to the .nii.gz file.
    desired_axis_order : str, optional
        The desired order of the image axes. Default is 'xyz'.
    return_res : bool, optional
        Whether to return resolutions. Default is False.
    return_metadata : bool, optional
        Whether to return metadata. Default is False.
    save_metadata : str, optional
        Path to save metadata file. Default is None.
    xy_res : float, optional
        The resolution in the xy-plane (use if res is not specified in the metadata).
    z_res : float, optional
        The resolution in the z-plane.

    Returns
    -------
    ndarray
        The loaded 3D image array.
    tuple, optional
        If return_res is True, returns (ndarray, xy_res, z_res).
    tuple, optional
        If return_metadata is True, returns (ndarray, xy_res, z_res, x_dim, y_dim, z_dim).
    """
    nii = nib.load(nii_path)
    data_type = nii.header.get_data_dtype()
    ndarray = np.asanyarray(nii.dataobj).astype(data_type)
    ndarray = np.squeeze(ndarray)
    ndarray = np.transpose(ndarray, (2, 1, 0)) if desired_axis_order == "zyx" else ndarray

    res_specified = True if xy_res is not None else False
    if res_specified:
        original_xy_res = xy_res
        original_z_res = z_res

    xy_res, z_res, x_dim, y_dim, z_dim = metadata(nii_path, ndarray, return_res, return_metadata, save_metadata=save_metadata)

    if res_specified:
        xy_res = original_xy_res
        z_res = original_z_res

    return return_3D_img(ndarray, return_metadata, return_res, xy_res, z_res, x_dim, y_dim, z_dim)

@print_func_name_args_times()
def load_nii_subset(nii_path, xmin, xmax, ymin, ymax, zmin, zmax):
    """
    Load a spatial subset of a .nii.gz file and return an ndarray.

    Parameters
    ----------
    nii_path : str
        The path to the .nii.gz file.
    xmin, xmax, ymin, ymax, zmin, zmax : int
        The spatial coordinates defining the subset.

    Returns
    -------
    ndarray
        The loaded subset of the 3D image.
    """
    proxy_img = nib.load(nii_path)    
    subset_array = proxy_img.dataobj[xmin:xmax, ymin:ymax, zmin:zmax]
    return np.squeeze(subset_array)

@print_func_name_args_times() 
def load_h5(hdf5_path, desired_axis_order="xyz", return_res=False, return_metadata=False, save_metadata=None, xy_res=None, z_res=None):
    """
    Load full resolution image from an HDF5 file (.h5) and return the ndarray.

    Parameters
    ----------
    hdf5_path : str
        The path to the .h5 file.
    desired_axis_order : str, optional
        The desired order of the image axes. Default is 'xyz'.
    return_res : bool, optional
        Whether to return resolutions. Default is False.
    return_metadata : bool, optional
        Whether to return metadata. Default is False.
    save_metadata : str, optional
        Path to save metadata file. Default is None.
    xy_res : float, optional
        The resolution in the xy-plane.
    z_res : float, optional
        The resolution in the z-plane.

    Returns
    -------
    ndarray
        The loaded 3D image array.
    tuple, optional
        If return_res is True, returns (ndarray, xy_res, z_res).
    tuple, optional
        If return_metadata is True, returns (ndarray, xy_res, z_res, x_dim, y_dim, z_dim).
    """
    with h5py.File(hdf5_path, 'r') as f:
        full_res_dataset_name = next(iter(f.keys())) # Assumes first dataset = full res image
        dataset = f[full_res_dataset_name]
        print(f"\n    Loading {full_res_dataset_name} as ndarray")
        ndarray = dataset[:]  # Load the full res image into memory (if not enough RAM, chunck data [e.g., w/ dask array])
        ndarray = np.transpose(ndarray, (2, 1, 0)) if desired_axis_order == "xyz" else ndarray
        xy_res, z_res, x_dim, y_dim, z_dim = metadata(hdf5_path, ndarray, return_res, return_metadata, save_metadata=save_metadata)
    return return_3D_img(ndarray, return_metadata, return_res, xy_res, z_res, x_dim, y_dim, z_dim)

@print_func_name_args_times()
def load_zarr(zarr_path, desired_axis_order="xyz"):
    """
    Load a .zarr image and return the ndarray.

    Parameters
    ----------
    zarr_path : str
        The path to the .zarr file.
    desired_axis_order : str, optional
        The desired order of the image axes. Default is 'xyz'.

    Returns
    -------
    ndarray
        The loaded 3D image array.
    """
    zarr_dataset = zarr.open(zarr_path, mode='r')
    ndarray = np.array(zarr_dataset)
    ndarray = np.transpose(ndarray, (2, 1, 0)) if desired_axis_order == "xyz" else ndarray
    return ndarray

def resolve_path(upstream_path, path_or_pattern, make_parents=True, is_file=True):
    """
    Returns full path or Path(upstream_path, path_or_pattern) and optionally creates parent directories.

    Parameters
    ----------
    upstream_path : str
        The base path.
    path_or_pattern : str
        The relative path or glob pattern.
    make_parents : bool, optional
        Whether to create parent directories if they don't exist. Default is True.
    is_file : bool, optional
        Whether the path is a file. Default is True.

    Returns
    -------
    Path or None
        The resolved path or None if not found.
    """
    if Path(path_or_pattern).is_absolute():
        if is_file:
            Path(path_or_pattern).parent.mkdir(parents=True, exist_ok=True)
        else:
            Path(path_or_pattern).mkdir(parents=True, exist_ok=True)
        return Path(path_or_pattern)
    
    full_path = Path(upstream_path, path_or_pattern)
    if full_path.exists():
        return full_path

    glob_matches = sorted(full_path.parent.glob(full_path.name))
    if glob_matches:
        return glob_matches[0]  # Return the first match

    # Make parent dirs for future output
    if make_parents:
        if is_file:
            full_path.parent.mkdir(parents=True, exist_ok=True)
        else:
            full_path.mkdir(parents=True, exist_ok=True)
        return full_path

    return None

def save_metadata_to_file(xy_res, z_res, x_dim, y_dim, z_dim, save_metadata='parameters/metadata.txt'):
    """
    Save metadata to a text file.

    Parameters
    ----------
    xy_res : float
        The resolution in the xy-plane.
    z_res : float
        The resolution in the z-plane.
    x_dim : int
        The size of the image in the x-dimension.
    y_dim : int
        The size of the image in the y-dimension.
    z_dim : int
        The size of the image in the z-dimension.
    save_metadata : str, optional
        Path to save metadata file. Default is 'parameters/metadata.txt'.
    """
    save_metadata = Path(save_metadata)
    save_metadata.parent.mkdir(parents=True, exist_ok=True)
    if not save_metadata.exists():
        with save_metadata.open('w') as f:
            f.write(f"Width:  {x_dim*xy_res} microns ({x_dim})\n")
            f.write(f"Height:  {y_dim*xy_res} microns ({y_dim})\n")
            f.write(f"Depth:  {z_dim*z_res} microns ({z_dim})\n")
            f.write(f"Voxel size: {xy_res}x{xy_res}x{z_res} micron^3\n")    

def load_image_metadata_from_txt(metadata="./parameters/metadata*"):
    """
    Load metadata from a text file.

    Parameters
    ----------
    metadata : str, optional
        The path or pattern to the metadata file. Default is './parameters/metadata*'.

    Returns
    -------
    tuple
        Returns (xy_res, z_res, x_dim, y_dim, z_dim) or (None, None, None, None, None) if file not found.
    """
    file_paths = glob(str(metadata))
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
        return None, None, None, None, None
    return xy_res, z_res, x_dim, y_dim, z_dim

@print_func_name_args_times()
def load_3D_img(img_path, channel=0, desired_axis_order="xyz", return_res=False, return_metadata=False, xy_res=None, z_res=None, save_metadata=None): 
    """
    Load a 3D image from various file formats and return the ndarray.

    Parameters
    ----------
    img_path : str
        The path to the image file.
    channel : int, optional
        The channel to load. Default is 0.
    desired_axis_order : str, optional
        The desired order of the image axes. Default is 'xyz'.
    return_res : bool, optional
        Whether to return resolutions. Default is False.
    return_metadata : bool, optional
        Whether to return metadata. Default is False.
    xy_res : float, optional
        The resolution in the xy-plane.
    z_res : float, optional
        The resolution in the z-plane.
    save_metadata : str, optional
        Path to save metadata file. Default is None.

    Returns
    -------
    ndarray
        The loaded 3D image array.
    tuple, optional
        If return_res is True, returns (ndarray, xy_res, z_res).
    tuple, optional
        If return_metadata is True, returns (ndarray, xy_res, z_res, x_dim, y_dim, z_dim).
    """

    # If file_path points to dir containing tifs, resolve path to first .tif
    img_path = Path(img_path)

    if img_path.is_dir():
        sorted_files = sorted(img_path.glob(f"*.tif"))
        if sorted_files: 
            img_path = next(iter(sorted_files), None) 

    if not img_path.exists():
        raise FileNotFoundError(f"No compatible image files found in {img_path}. Supported file types: .czi, .ome.tif, .tif, .nii.gz, .h5, .zarr")
    
    if str(img_path).endswith('.czi'):
        print(f"\n    [default]Loading channel {channel} from {img_path} (channel 0 is the first channel)")
    else: 
        print(f"\n    [default]Loading {img_path}")

    # Load image based on file type and optionally return resolutions and dimensions
    try:
        if str(img_path).endswith('.czi'):
            return load_czi(img_path, channel, desired_axis_order, return_res, return_metadata, save_metadata, xy_res, z_res)
        elif str(img_path).endswith('.ome.tif') or str(img_path).endswith('.tif'):
            return load_tifs(img_path, desired_axis_order, return_res, return_metadata, save_metadata, xy_res, z_res, parallel_loading=True)
        elif str(img_path).endswith('.nii.gz'):
            return load_nii(img_path, desired_axis_order, return_res, return_metadata, save_metadata, xy_res, z_res)
        elif str(img_path).endswith('.h5'):
            return load_h5(img_path, desired_axis_order, return_res, return_metadata, save_metadata, xy_res, z_res)
        elif str(img_path).endswith('.zarr'):
            return load_zarr(img_path, desired_axis_order)
        else:
            raise ValueError(f"Unsupported file type: {img_path.suffix}. Supported file types: .czi, .ome.tif, .tif, .nii.gz, .h5")
    except (FileNotFoundError, ValueError) as e:
        print(f"\n    [red bold]Error: {e}\n")
        import sys ; sys.exit()


# Save images
def load_nii_orientation(input_nii_path):
    """
    Load a .nii.gz file and return its orientation (affine matrix).

    Parameters
    ----------
    input_nii_path : str
        The path to the .nii.gz file.

    Returns
    -------
    ndarray
        The affine matrix of the .nii.gz file.
    """
    nii = nib.load(str(input_nii_path))
    return nii.affine

@print_func_name_args_times()
def save_as_nii(ndarray, output, xy_res=1000, z_res=1000, data_type=np.float32, reference=None):
    """
    Save a numpy array as a .nii.gz image with the option to retain the orientation of an input .nii.gz file.

    Parameters
    ----------
    ndarray : ndarray
        The numpy array to save.
    output : str
        Output file path.
    xy_res : float, optional
        XY resolution in microns. Default is 1000.
    z_res : float, optional
        Z resolution in microns. Default is 1000.
    data_type : data-type, optional
        Data type for the NIFTI image. Default is np.float32.
    reference : str or ndarray, optional
        Either an affine matrix or a path to a .nii.gz file to retain its orientation. Default is None.

    Returns
    -------
    None
    """
    output = Path(output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    
    # Check if reference is an affine matrix or a path
    if reference is not None:
        if isinstance(reference, np.ndarray):
            affine = reference
        elif isinstance(reference, (str, Path)):
            affine = load_nii_orientation(reference)
        else:
            raise ValueError("Reference must be either an affine matrix or a file path.")
    else:
        # Create the affine matrix with the appropriate resolutions (converting microns to mm)
        affine = np.diag([xy_res / 1000, xy_res / 1000, z_res / 1000, 1]) # RAS orientation
    
    # Create and save the NIFTI image
    nifti_img = nib.Nifti1Image(ndarray, affine)
    nifti_img.header.set_data_dtype(data_type)
    nib.save(nifti_img, str(output))    
    print(f"\n    Output: [default bold]{output}")

@print_func_name_args_times()
def save_as_tifs(ndarray, tif_dir_out, ndarray_axis_order="xyz"):
    """
    Save an ndarray as a series of .tif images.

    Parameters
    ----------
    ndarray : ndarray
        The 3D image array to save.
    tif_dir_out : str
        The directory to save the .tif files.
    ndarray_axis_order : str, optional
        The order of the ndarray axes. Default is 'xyz'.

    Returns
    -------
    None
    """
    # Ensure tif_dir_out is a Path object, not a string
    tif_dir_out = Path(tif_dir_out)
    tif_dir_out.mkdir(parents=True, exist_ok=True)
    
    if ndarray_axis_order == "xyz":
        ndarray = np.transpose(ndarray, (2, 1, 0)) # Transpose to zyx (tiff expects zyx)
        
    for i, slice_ in enumerate(ndarray):
        slice_file_path = tif_dir_out / f"slice_{i:04d}.tif"
        imwrite(str(slice_file_path), slice_)
    print(f"\n    Output: [default bold]{tif_dir_out}")

@print_func_name_args_times()
def save_as_zarr(ndarray, output_path, ndarray_axis_order="xyz"):
    """
    Save an ndarray to a .zarr file.

    Parameters
    ----------
    ndarray : ndarray
        The 3D image array to save.
    output_path : str
        The path to save the .zarr file.
    ndarray_axis_order : str, optional
        The order of the ndarray axes. Default is 'xyz'.

    Returns
    -------
    None
    """
    if ndarray_axis_order == "xyz":
        ndarray = np.transpose(ndarray, (2, 1, 0))
    dask_array = da.from_array(ndarray, chunks='auto')
    compressor = zarr.Blosc(cname='lz4', clevel=9, shuffle=zarr.Blosc.BITSHUFFLE)
    dask_array.to_zarr(output_path, compressor=compressor, overwrite=True)
    print(f"\n    Output: [default bold]{output_path}")

@print_func_name_args_times()
def save_as_h5(ndarray, output_path, ndarray_axis_order="xyz"):
    """
    Save an ndarray to an HDF5 file (.h5).

    Parameters
    ----------
    ndarray : ndarray
        The 3D image array to save.
    output_path : str
        The path to save the .h5 file.
    ndarray_axis_order : str, optional
        The order of the ndarray axes. Default is 'xyz'.

    Returns
    -------
    None
    """
    if ndarray_axis_order == "xyz":
        ndarray = np.transpose(ndarray, (2, 1, 0))
    with h5py.File(output_path, 'w') as f:
        f.create_dataset('data', data=ndarray, compression="lzf")