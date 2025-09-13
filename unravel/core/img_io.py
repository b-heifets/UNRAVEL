#!/usr/bin/env python3

"""
This module contains functions for loading and saving 3D images.

Main Functions:
---------------
- load_3D_img: Load a 3D image from a .czi, .nii.gz, or .tif series and return the ndarray.
- save_3D_img: Save a 3D image as a .nii.gz, .tif series, .h5, or .zarr file.

Helper Functions:
-----------------
- extract_resolution
- load_image_metadata_from_txt
- save_metadata_to_file
- metadata
- return_3D_img
"""

import json
import os
import re
import cv2 
import dask.array as da
import h5py
import nibabel as nib
import numpy as np
import tifffile
import xml.etree.ElementTree as ET
import zarr
from aicspylibczi import CziFile
from concurrent.futures import ThreadPoolExecutor
from glob import glob
from lxml import etree
from pathlib import Path
from rich import print

from unravel.core.utils import match_files, print_func_name_args_times


# TODO: save_as_nii() add logic for using the reference image for dtype (e.g., if reference is provided and dtype is None, use reference dtype)
# TODO: Add support for extracting metadata from .zarr files.

@print_func_name_args_times()
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
            if "ImageDescription" in meta:
                ome_xml_str = meta["ImageDescription"].value
                try:
                    ome_xml_str = meta['ImageDescription'].value
                    ome_xml_root = etree.fromstring(ome_xml_str.encode('utf-8'))
                    default_ns = ome_xml_root.nsmap[None]
                    pixels_element = ome_xml_root.find(f'.//{{{default_ns}}}Pixels')
                    xy_res = float(pixels_element.get('PhysicalSizeX'))
                    z_res = float(pixels_element.get('PhysicalSizeZ'))
                except Exception as e:
                    print(f"⚠️  Could not parse OME-XML from {img_path}. Not extracting resolution. Error: {e}")
                    xy_res, z_res = None, None
            else:
                print(f"⚠️  No ImageDescription tag in {img_path}")
                xy_res, z_res = None, None
    elif str(img_path).endswith('.nii.gz'):
        nii = nib.load(img_path)
        res = nii.header.get_zooms() # (x, y, z) in mm
        xy_res = res[0] * 1000 # Convert from mm to um
        z_res = res[2] * 1000
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

    if ndarray.ndim == 4:
        print(f"\n[red1].czi channel {channel} has 4 axes. Please stitch tiles from {Path(czi_path).name}\n")
        import sys ; sys.exit()

    ndarray = np.transpose(ndarray, (2, 1, 0)) if desired_axis_order == "xyz" else ndarray
    xy_res, z_res, x_dim, y_dim, z_dim = metadata(czi_path, ndarray, return_res, return_metadata, xy_res, z_res, save_metadata)
    return return_3D_img(ndarray, return_metadata, return_res, xy_res, z_res, x_dim, y_dim, z_dim)
    
@print_func_name_args_times()
def load_tifs(tif_dir_path, desired_axis_order="xyz", return_res=False, return_metadata=False, save_metadata=None, xy_res=None, z_res=None, parallel_loading=True):
    """
    Load a series of .tif images and return the ndarray.

    Parameters
    ----------
    tif_dir_path : str
        The path to the directory containing the .tif files.
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
    tif_files = match_files('*.tif', base_path=tif_dir_path)
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

def load_3D_tif(tif_path, desired_axis_order="xyz", return_res=False, return_metadata=False, save_metadata=None, xy_res=None, z_res=None):
    """
    Load a 3D .ome.tif or .tif image and return the ndarray.

    Parameters
    ----------
    tif_path : str
        The path to the .ome.tif file.
    desired_axis_order : str, optional
        The desired order of the image axes. Default is 'xyz'.
    return_res : bool, optional
        Whether to return resolutions (works for .ome.tif). Default is False.

    Returns
    -------
    ndarray
        The loaded 3D image array.
    tuple, optional
        If return_res is True, returns (ndarray, xy_res, z_res).
    """
    with tifffile.TiffFile(tif_path) as tif:
        print(f"\n    Loading {tif_path} as ndarray")
        ndarray = tif.asarray()  # Load the image into memory
        ndarray = np.transpose(ndarray, (2, 1, 0)) if desired_axis_order == "xyz" else ndarray
        x_dim, y_dim, z_dim = ndarray.shape

        # If resolution is requested, extract it from OME-XML metadata
        if xy_res is None or z_res is None:
            first_page = tif.pages[0]
            description = first_page.tags[270].value
            try:
                # Remove the OME comment header to parse XML correctly
                ome_xml = description.split('-->')[-1].strip()
                root = ET.fromstring(ome_xml)

                # Find the Pixels element and get PhysicalSizeX and PhysicalSizeZ
                pixels = root.find(".//{http://www.openmicroscopy.org/Schemas/OME/2016-06}Pixels")
                xy_res = float(pixels.attrib['PhysicalSizeX'])
                z_res = float(pixels.attrib['PhysicalSizeZ'])

            except (ET.ParseError, KeyError, TypeError) as e:
                raise ValueError(f"\n    Unable to parse OME-XML metadata: {e}\n")
            
        if save_metadata is not None:
            save_metadata_to_file(xy_res, z_res, x_dim, y_dim, z_dim, save_metadata=save_metadata)

    return return_3D_img(ndarray, return_metadata, return_res, xy_res, z_res, x_dim, y_dim, z_dim)

def nii_path_or_nii(nii):
    """Helper function to load a NIfTI image if it's a path. Returns the NIfTI image object.
    
    Parameters:
    -----------
    nii : str, Path, or nib.Nifti1Image
        Path to the NIfTI image file or a Nifti1Image object.

    Returns:
    --------
    nib.Nifti1Image
        The NIfTI image object.
    """
    if isinstance(nii, nib.Nifti1Image):
        return nii
    elif isinstance(nii, (str, Path)) and Path(nii).exists():
        return nib.load(nii)
    else:
        raise FileNotFoundError(f"\nInput file not found: {nii}\n")

@print_func_name_args_times()
def nii_to_ndarray(nii):
    """Load a NIfTI image and return as a 3D ndarray.

    Parameters:
    -----------
    nii : str, Path, or nib.Nifti1Image
        Path to the NIfTI image file or a Nifti1Image object.

    Returns:
    --------
    ndarray : ndarray
        The 3D image array.
    """
    nii = nii_path_or_nii(nii)
    ndarray = np.asanyarray(nii.dataobj, dtype=nii.header.get_data_dtype()).squeeze()
    return ndarray

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

    Notes
    -----
    - If xy_res and z_res are provided, they will be used instead of the values from the metadata.
    """
    ndarray = nii_to_ndarray(nii_path)
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
def load_zarr(zarr_path, channel=0, desired_axis_order="xyz", return_res=False,  return_metadata=False, save_metadata=None, xy_res=None, z_res=None, level=None, verbose=False):
    """
    Load a channel and level of a Zarr image, optionally returning voxel resolution.

    Parameters
    ----------
    zarr_path : str or Path
        Path to .zarr directory.
    channel : int, optional
        Channel index to load (for 4D data). If None, loads all channels.
    desired_axis_order : str, optional
        Desired output axis order (default: "xyz").
    return_res : bool, optional
        If True, returns voxel resolution in mm (xy_res, z_res) along with the image.
    save_metadata : str, optional
        Path to save metadata file. Default is None.
    xy_res : float, optional
        Resolution in the xy-plane (in microns). If None, will be extracted from metadata.
    z_res : float, optional
        Resolution in the z-plane (in microns). If None, will be extracted from metadata.
    level : str or int, optional
        Resolution level to load (default: highest).
    verbose : bool
        Print debug output.

    Returns
    -------
    ndarray
        3D numpy array from the zarr store, with shape (z, y, x) or (z, x, y) depending on desired_axis_order.
    tuple, optional
        If return_res is True, returns (ndarray, xy_res, z_res).
    tuple, optional
        If return_metadata is True, returns (ndarray, xy_res, z_res, x_dim, y_dim, z_dim).
    """
    zarr_path = Path(zarr_path)
    if not zarr_path.exists():
        raise FileNotFoundError(f"Zarr path {zarr_path} does not exist.")

    def log(msg):
        if verbose:
            print(msg)

    # Load .zattrs
    zattrs = {}
    zattrs_path = zarr_path / ".zattrs"
    if zattrs_path.exists():
        with open(zattrs_path) as f:
            zattrs = json.load(f)

    level_str = str(level) if level is not None else None
    xy_res = z_res = None
    if "multiscales" in zattrs:
        multiscale = zattrs["multiscales"][0]
        axes = multiscale.get("axes", [])
        datasets = multiscale.get("datasets", [])

        # Infer highest-res level available on disk
        level_str = str(level) if level is not None else None
        if level_str is None and datasets:
            dataset_dirs = [ds["path"] for ds in datasets if ds["path"] == "." or str(ds["path"]).isdigit()]
            existing_dirs = [p for p in dataset_dirs if (zarr_path / p).exists()]
            if not level_str and existing_dirs:
                if "." in existing_dirs:
                    level_str = "."
                elif existing_dirs:
                    level_str = str(min(map(int, existing_dirs)))

        # Extract resolution for this level
        dataset = next((d for d in datasets if str(d["path"]) == level_str), None)
        if dataset:
            transforms = dataset.get("coordinateTransformations", [])
            if transforms:
                scale = transforms[0].get("scale", [])
                if len(scale) == len(axes):
                    res_dict = {axis["name"]: s for axis, s in zip(axes, scale)}
                    xy_res = res_dict.get("x", None)
                    z_res = res_dict.get("z", None)
                    # Convert to micrometers
                    xy_res = xy_res * 1e3 if xy_res is not None else None
                    z_res = z_res * 1e3 if z_res is not None else None

    # Load image data
    ndarray = None
    if level_str: # If a level is specified or found, load that level
        level_path = zarr_path / level_str
        if level_path.exists():
            log(f"        Multi-resolution structure detected: loading level {level_str}")
            ndarray = da.from_zarr(level_path).compute() # convert dask array to numpy array
        else:
            raise ValueError(f"Specified level {level_str} does not exist in {zarr_path}")
    else: # Load flat format (.zattrs is missing or it does not match expected metadata structure)
        log("        No compatible .zattrs metadata found. Loading flat zarr format.")
        zarr_dataset = zarr.open(zarr_path, mode='r')
        ndarray = np.array(zarr_dataset)

    # Extract channel if specified (e.g., 0 for the first channel, 1 for the second, etc.)
    log(f"        Array shape ([C], Z, Y, X): {ndarray.shape}")
    if ndarray.ndim == 4:
        if channel is not None:
            log(f"        Extracted channel: {channel}")
            ndarray = ndarray[channel]
        else:
            raise ValueError(f"Multiple channels found: {ndarray.shape[0]} channels. Please specify a channel index.")

    if ndarray.ndim != 3:
        raise ValueError(f"Expected 3D array, but got shape {ndarray.shape}")

    # Transpose to desired axis order
    if desired_axis_order == "xyz":
        ndarray = np.transpose(ndarray, (2, 1, 0))
        log(f"        Array shape after transposing to (X, Y, Z): {ndarray.shape}")

    xy_res, z_res, x_dim, y_dim, z_dim = metadata(zarr_path, ndarray, return_res, return_metadata, xy_res, z_res, save_metadata)
    return return_3D_img(ndarray, return_metadata=return_metadata, return_res=return_res, xy_res=xy_res, z_res=z_res, x_dim=x_dim, y_dim=y_dim, z_dim=z_dim)

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
    file_paths = match_files(metadata)
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
def load_3D_img(img_path, channel=0, desired_axis_order="xyz", return_res=False, return_metadata=False, xy_res=None, z_res=None, save_metadata=None, verbose=False): 
    """
    Load a 3D image from various file formats and return the ndarray.

    Parameters
    ----------
    img_path : str
        The path to the image file (.czi, .ome.tif, .tif, .nii.gz, .h5, .zarr) or directory w/ 2D .ome.tif or .tif files.
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
    if img_path.is_dir() and not str(img_path).endswith('.zarr'):
        tif_files = match_files('*.tif', base_path=img_path)
        if tif_files: 
            return load_tifs(img_path, desired_axis_order, return_res, return_metadata, save_metadata, xy_res, z_res)

    if not img_path.exists():
        raise FileNotFoundError(f"\nNo compatible image files found at {img_path} for load_3D_img(). Use: .czi, .ome.tif, .tif, .nii.gz, .h5, .zarr")
    
    # Load image based on file type and optionally return resolutions and dimensions
    try:
        if str(img_path).endswith('.czi'):
            return load_czi(img_path, channel=channel, desired_axis_order=desired_axis_order, return_res=return_res, return_metadata=return_metadata, save_metadata=save_metadata, xy_res=xy_res, z_res=z_res)
        elif str(img_path).endswith('.ome.tif') or str(img_path).endswith('.tif'):
            return load_3D_tif(img_path, desired_axis_order, return_res, return_metadata, save_metadata, xy_res, z_res)
        elif str(img_path).endswith('.nii.gz'):
            return load_nii(img_path, desired_axis_order, return_res, return_metadata, save_metadata, xy_res, z_res)
        elif str(img_path).endswith('.h5'):
            return load_h5(img_path, desired_axis_order, return_res, return_metadata, save_metadata, xy_res, z_res)
        elif str(img_path).endswith('.zarr'):
            return load_zarr(img_path, channel=channel, desired_axis_order=desired_axis_order, return_res=return_res, return_metadata=return_metadata, save_metadata=save_metadata, xy_res=xy_res, z_res=z_res, verbose=verbose)
        else:
            raise ValueError(f"Unsupported file type: {img_path.suffix}. Supported file types: .czi, .ome.tif, .tif, .nii.gz, .h5")
    except (FileNotFoundError, ValueError) as e:
        print(f"\n    [red bold]Error: {e}\n")
        import sys; sys.exit()


# Save images
@print_func_name_args_times()
def save_as_nii(ndarray, output, xy_res=1000, z_res=1000, data_type=None, reference=None):
    """
    Save a numpy array as a .nii.gz image with the specified resolution and orientation, using a reference image if provided.

    Parameters
    ----------
    ndarray : ndarray
        The numpy array to save as a NIFTI image.
    output : str or Path
        The file path to save the output image. '.nii.gz' is appended if not present.
    xy_res : float, optional
        XY-plane resolution in microns. Default is 1000.
    z_res : float, optional
        Z-axis resolution in microns. Default is 1000.
    data_type : data-type, optional
        Data type for the NIFTI image. Default is np.float32.
    reference : str, Path, or nib.Nifti1Image, optional
        Either a path to a reference .nii.gz file or a Nifti1Image object
        to set orientation and resolution. If provided, `xy_res` and `z_res` are ignored. Default is None.

    Notes
    -----
    - The function will automatically create parent directories if they do not exist.
    - The affine transformation is constructed assuming RAS orientation if no reference is provided.
    """
    output = Path(output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    if not str(output).endswith('.nii.gz'):
        output = output.with_suffix('.nii.gz')
    
    if reference is not None:
        if isinstance(reference, (str, Path)):
            ref_nii = nib.load(str(reference))
        elif isinstance(reference, nib.Nifti1Image):
            ref_nii = reference
        else:
            raise ValueError("\nReference for save_as_nii() must be a path to a .nii.gz file or a Nifti1Image object.\n")
        
        affine = ref_nii.affine
        header = ref_nii.header.copy()
        if data_type is None:
            data_type = header.get_data_dtype()
    else:
        # Create the affine matrix with the appropriate resolutions (converting microns to mm)
        affine = np.diag([xy_res / 1000, xy_res / 1000, z_res / 1000, 1]) # RAS orientation
        header = nib.Nifti1Header()

    # Create and save the NIFTI image
    nii = nib.Nifti1Image(ndarray, affine, header)
    nii.header.set_data_dtype(data_type or np.float32)
    
    nib.save(nii, output)    
    print(f"\n    Output: [default bold]{output}")

@print_func_name_args_times()
def save_as_tifs(ndarray, tif_dir_out=None, ndarray_axis_order="xyz", parallel=True, max_workers=None, verbose=False):
    """
    Save an ndarray as a series of .tif images.

    Parameters
    ----------
    ndarray : ndarray
        The 3D image array to save.
    tif_dir_out : str or Path
        The directory to save the .tif files.
    ndarray_axis_order : str, optional
        The order of the ndarray axes. Default is 'xyz'.
    parallel : bool, optional
        Whether to save slices in parallel. Default is False.
    max_workers : int or None, optional
        Number of threads to use for parallel saving. Defaults to os.cpu_count().
    verbose : bool, optional
        How to print the output directory. Default is False.

    Returns
    -------
    None
    """
    tif_dir_out = Path(tif_dir_out)
    tif_dir_out.mkdir(parents=True, exist_ok=True)

    if ndarray_axis_order == "xyz":
        ndarray = np.transpose(ndarray, (2, 1, 0))  # to zyx

    def save_slice(i):
        slice_file_path = tif_dir_out / f"slice_{i:04d}.tif"
        tifffile.imwrite(str(slice_file_path), ndarray[i])

    if parallel:
        with ThreadPoolExecutor(max_workers=max_workers or os.cpu_count()) as executor:
            list(executor.map(save_slice, range(ndarray.shape[0])))
    else:
        for i in range(ndarray.shape[0]):
            save_slice(i)

    if verbose:
        print(f"        Output directory: [magenta]{tif_dir_out}")
    else:
        print(f"Output directory with tif series: [magenta]{tif_dir_out}")

@print_func_name_args_times()
def save_as_zarr(ndarray, output_path=None, ndarray_axis_order="xyz", xy_res=None, z_res=None, verbose=False):
    """
    Save a 3D ndarray to a .zarr file as well as OME-NGFF-compatible metadata.

    Parameters
    ----------
    ndarray : ndarray
        The 3D image array to save.
    output_path : str
        The path to save the .zarr file.
    ndarray_axis_order : str, optional
        The order of the ndarray axes. Default is 'xyz'.
    xy_res : float, optional
        The voxel size in the XY plane (in mm).
    z_res : float, optional
        The voxel size in the Z direction (in mm).
    """
    if ndarray_axis_order == "xyz":
        ndarray = np.transpose(ndarray, (2, 1, 0))

    if isinstance(ndarray, da.Array):
        dask_array = ndarray
    else:
        dask_array = da.from_array(ndarray, chunks='auto')
    compressor = zarr.Blosc(cname='lz4', clevel=9, shuffle=zarr.Blosc.BITSHUFFLE)
    dask_array.to_zarr(output_path, compressor=compressor, overwrite=True)
    if verbose:
        print(f"\n    Saved zarr as: [default bold]{output_path}")

    # Add NGFF-style .zattrs
    first_axis = "x" if ndarray_axis_order == "xyz" else "z"
    third_axis = "z" if first_axis == "x" else "x"
    if xy_res is not None or z_res is not None:
        attrs = {
            "multiscales": [{
                "version": "0.4",
                "axes": [
                    {"name": first_axis, "type": "space", "unit": "millimeter"},
                    {"name": "y", "type": "space", "unit": "millimeter"},
                    {"name": third_axis, "type": "space", "unit": "millimeter"},
                ],
                "datasets": [{
                    "path": ".",
                    "coordinateTransformations": [{
                        "type": "scale",
                        "scale": [xy_res, xy_res, z_res]
                    }]
                }]
            }]
        }
        zarr.open(output_path, mode='a').attrs.update(attrs)
        if verbose:
            print(f"    Added NGFF-style .zattrs with resolutions (in mm): xy_res={xy_res}, z_res={z_res}")

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

@print_func_name_args_times()
def save_3D_img(img, output_path=None, ndarray_axis_order="xyz", xy_res=1000, z_res=1000, data_type=np.float32, reference_img=None, verbose=False):
    """
    Save a 3D image in various formats.

    Parameters
    ----------
    img : ndarray
        The 3D image array to save.
    output_path : str
        The path to save the image. The file extension determines the format: .nii.gz, .zarr, .h5, .tif, or a directory path for a TIFF series.
    ndarray_axis_order : str, optional
        The order of the ndarray axes. Default is 'xyz'.
    xy_res : float, optional
        The x/y resolution in microns for a NIFTI image output. Default is 1000.
    z_res : float, optional
        The z resolution in microns for a NIFTI image output. Default is 1000.
    data_type : data-type, optional
        Data type for a NIFTI image output. Default is np.float32.
    reference_img : str, Path, or a nib.Nifti1Image object, optional
        Either path to a .nii.gz file or a Nifti1Image object to set orientation and resolution. Default is None. If provided, xy_res and z_res are ignored.
    verbose : bool, optional
        Print addtional infomation. Default is False.
    """
    output = Path(output_path)
    output.parent.mkdir(exist_ok=True, parents=True)

    output_str = str(output).lower()
    suffix = output.suffix.lower()

    if output_str.endswith('.nii.gz'):
        save_as_nii(img, output, xy_res, z_res, data_type=data_type, reference=reference_img)
    elif suffix == '.zarr':
        save_as_zarr(img, output, ndarray_axis_order=ndarray_axis_order, xy_res=xy_res, z_res=z_res, verbose=verbose)
    elif suffix == '.h5':
        save_as_h5(img, output, ndarray_axis_order=ndarray_axis_order)
    elif suffix == '.tif':
        # If user gave a file path like red2/slice_0000.tif, use the parent directory
        save_as_tifs(img, tif_dir_out=output.parent, ndarray_axis_order=ndarray_axis_order, parallel=True, max_workers=None, verbose=verbose)
    elif suffix == '':
        # If no suffix, assume directory path for TIFFs
        save_as_tifs(img, tif_dir_out=output, ndarray_axis_order=ndarray_axis_order, parallel=True, max_workers=None, verbose=verbose)
    else:
        raise ValueError(f"Unsupported file type for save_3D_img(): '{suffix}'. Use: .nii.gz, .zarr, .h5, .tif, or a directory path for a TIFF series.")

# TODO: Function to extract a resolution level from a Zarr file (return as ndarray)

@print_func_name_args_times()
def zarr_level_to_tifs(zarr_path, output_dir, channel_map, resolution_level=None, xy_res=None, z_res=None):
    """
    Extracts a specified resolution level from a Zarr file and saves the specified channels as TIFF files.

    Parameters:
    -----------
    zarr_path : str or Path
        Path to the Zarr file.
    output_dir : str or Path
        Directory to save the output TIFF files. If None, defaults to "TIFFs/<sample_name>".
    resolution_level : str
        Resolution level to extract (e.g., "0", "1", ..., "9").
    channel_map : dict
        Mapping of output directory names to Zarr channel indices (e.g., {'red': 0, 'green': 1}).
    xy_res : float, optional
        X/Y resolution in microns.
    z_res : float, optional
        Z resolution in microns. Default is 100 µm for Genetic Tools Atlas data.
    """
    # Check what resolution levels are available in the Zarr file
    zarr_path = Path(zarr_path)
    if not zarr_path.exists():
        raise FileNotFoundError(f"Zarr input path does not exist: {zarr_path}")
    else:
        print(f"Zarr input path exists: {zarr_path}")
        levels = [str(level) for level in zarr_path.iterdir() if level.is_dir()]

    if len(levels) == 1:
        resolution_level = levels[0]
    elif resolution_level is None:
        raise ValueError(f"Multiple resolution levels found in {zarr_path.name}. Please specify a resolution level. Available levels: {levels}")

    if not zarr_path.is_dir():
        raise NotADirectoryError(f"Zarr input path is not a directory: {zarr_path}")
    if not (zarr_path / resolution_level).is_dir():
        raise FileNotFoundError(f"Resolution level {resolution_level} not found in Zarr file: {zarr_path}")

    z = zarr.open(zarr_path, mode="r")
    z_level = z[resolution_level]

    if z_level.ndim != 4:
        raise ValueError(f"Expected shape (c, z, y, x), got {z_level.shape}")

    num_channels = z_level.shape[0]
    if num_channels == 1:
        print(f"⚠️ Only one channel found in {zarr_path.name}")

    print(f"📂 Processing {zarr_path.name} at resolution level {resolution_level}...")

    for name, idx in channel_map.items():
        out_dir = output_dir / name
        tif_files = match_files('*.tif', base_path=out_dir)
        if tif_files:
            print(f"⚠️ Skipping {name} in {zarr_path.name}: output TIFFs already exist at {out_dir}")
            continue
        if idx >= num_channels:
            print(f"⚠️ Channel index {idx} not found in {zarr_path.name} (only {num_channels} channels). Skipping {name}.")
            continue
        save_as_tifs(z_level[idx], out_dir, ndarray_axis_order="zyx", parallel=True)
        save_metadata_to_file(
            xy_res=xy_res, 
            z_res=z_res, 
            x_dim=z_level[idx].shape[2], 
            y_dim=z_level[idx].shape[1], 
            z_dim=z_level[idx].shape[0], 
            save_metadata=Path(out_dir).parent / "parameters" / "metadata.txt"
        )

# Other functions
def nii_voxel_size(nii, use_um=True):
    """Get the resolution (voxel size) of a NIfTI image.
    
    Parameters:
    -----------
    nii : str, Path, or nib.Nifti1Image
        Path to the NIfTI image file or a Nifti1Image object.

    use_um : bool, optional. Default is True.
        If True, return the resolution in micrometers (um). If False, return the resolution in millimeters (mm).

    Returns:
    --------
    res : tuple of float or float
        If anisotropic, returns (x_res, y_res, z_res) in micrometers (um) or millimeters (mm).
        If isotropic, returns a single float value for the resolution in micrometers (um) or millimeters (mm).
    """
    nii = nii_path_or_nii(nii)
    res = nii.header.get_zooms()  # (x, y, z) in mm
    if use_um:
        res = tuple([r * 1000 for r in res])  # Convert to micrometers

    # Return as a single value if isotropic, else as a tuple
    return res[0] if res[0] == res[1] == res[2] else res
