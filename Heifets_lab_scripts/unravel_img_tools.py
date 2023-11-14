#!/usr/bin/env python3

import cv2 
import nibabel as nib
import numpy as np
import subprocess
import tifffile
from aicspylibczi import CziFile
from concurrent.futures import ThreadPoolExecutor
from glob import glob
from lxml import etree
from pathlib import Path
from PIL import Image
from rich import print
from scipy import ndimage
from tifffile import imwrite 
from unravel_utils import print_func_name_args_times


####### Load 3D image and get xy and z voxel size in microns #######

@print_func_name_args_times()
def load_czi(czi, channel, desired_axis_order="xyz", return_res=False):
    """Load a CZI image and return the ndarray
    Default: axis_order=xyz (other option: axis_order="zyx")
    Default: returns: ndarray
    If return_res=True returns: ndarray, xy_res, z_res (resolution in um)"""
    ndarray = np.squeeze(czi.read_image(C=channel)[0])
    ndarray = np.transpose(ndarray, (2, 1, 0)) if desired_axis_order == "xyz" else ndarray
    if return_res:
        xy_res, z_res = xyz_res_from_czi(czi)
        return ndarray, xy_res, z_res
    else:
        return ndarray

# @print_func_name_args_times()
# def load_tifs(tif_path, desired_axis_order="xyz", return_res=False):
#     """Load a tif series and return the ndarray and optionally the xy and z resolutions in microns."""
#     tifs_stacked = []
#     for tif_file in sorted(Path(tif_path).parent.glob("*.tif")):
#         with Image.open(tif_file) as img:
#             tifs_stacked.append(np.array(img))
#     ndarray = np.stack(tifs_stacked, axis=0)
#     ndarray = np.transpose(ndarray, (2, 1, 0)) if desired_axis_order == "xyz" else ndarray
#     if return_res:
#         xy_res, z_res = xyz_res_from_tif(tif_path)
#         return ndarray, xy_res, z_res
#     else:
#         return ndarray
    
def load_single_tif(tif_file):
    """Load a single tif file and return ndarray."""
    with Image.open(tif_file) as img:
        return np.array(img)

@print_func_name_args_times()
def load_tifs(tif_path, desired_axis_order="xyz", return_res=False, parallel_loading=True):
    """Load a tif series [in parallel] and return the ndarray
    Default: axis_order=xyz (other option: axis_order="zyx")
    Default: returns: ndarray
    If return_res=True returns: ndarray, xy_res, z_res (resolution in um)"""
    tif_files = sorted(Path(tif_path).parent.glob("*.tif"))

    if parallel_loading:
        with ThreadPoolExecutor() as executor:
            tifs_stacked = list(executor.map(load_single_tif, tif_files))
    else:
        tifs_stacked = [] ################################################# Is this line not needed.
        for tif_file in sorted(Path(tif_path).parent.glob("*.tif")):
            with Image.open(tif_file) as img:
                tifs_stacked.append(np.array(img))

    ndarray = np.stack(tifs_stacked, axis=0)
    ndarray = np.transpose(ndarray, (2, 1, 0)) if desired_axis_order == "xyz" else ndarray

    if return_res:
        xy_res, z_res = xyz_res_from_tif(tif_path)
        return ndarray, xy_res, z_res
    else:
        return ndarray


@print_func_name_args_times()
def load_nii(nii_path, desired_axis_order="xyz", return_res=False):
    """Load a .nii.gz image and return the ndarray
    Default: axis_order=xyz (other option: axis_order="zyx")
    Default: returns: ndarray
    If return_res=True returns: ndarray, xy_res, z_res (resolution in um)"""
    img = nib.load(nii_path)
    data_dtype = img.header.get_data_dtype()
    ndarray = np.asanyarray(img.dataobj).astype(data_dtype)
    ndarray = np.squeeze(ndarray)
    ndarray = np.transpose(ndarray, (2, 1, 0)) if desired_axis_order == "zyx" else ndarray
    if return_res:
        xy_res, z_res = xyz_res_from_nii(nii_path)
        return ndarray, xy_res, z_res
    else:
        return ndarray
    
# Helper function to resolve file path to first matching file in dir or file itself
def resolve_path(file_path, extensions):
    """Return first matching file in dir or file itself if it matches the extensions."""
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

@print_func_name_args_times()
def load_3D_img(file_path, channel=0, desired_axis_order="xyz", return_res=False): 
    """Load <file_path> (.czi, .nii.gz, or .tif).
    file_path can be path to image file or dir (uses first *.czi, *.tif, or *.nii.gz match)
    Default: axis_order=xyz (other option: axis_order="zyx")
    Default: returns: ndarray
    If return_res=True returns: ndarray, xy_res, z_res (resolution in um)
    """ 

    # Resolve the file path to the first matching file
    path = resolve_path(file_path, ['.czi', '.tif', '.nii.gz'])
    if not path:
        raise FileNotFoundError(f"No compatible image files found in {file_path}. Supported file types: .czi, .tif, .nii.gz")
    print(f"    [default]Loading {path}")

    # Load image based on file type and optionally return resolutions
    if str(path).endswith('.czi'):
        czi = CziFile(path)
        return load_czi(czi, channel, desired_axis_order, return_res)
    elif str(path).endswith('.ome.tif'):
        return load_tifs(path, desired_axis_order, return_res, parallel_loading=True)
    elif str(path).endswith('.tif'):
        if return_res:
            return load_tifs(path, desired_axis_order, return_res=False, parallel_loading=True), None, None
        else:
            return load_tifs(path, desired_axis_order, return_res=False, parallel_loading=True)
    elif str(path).endswith('.nii.gz'):
        return load_nii(path, desired_axis_order, return_res)
    else:
        raise ValueError(f"Unsupported file type: {path.suffix}. Supported file types: .czi, .tif, .nii.gz")


def xyz_res_from_czi(czi_path):
    xml_root = czi_path.meta
    scaling_info = xml_root.find(".//Scaling")
    xy_res = float(scaling_info.find("./Items/Distance[@Id='X']/Value").text) * 1e6
    z_res = float(scaling_info.find("./Items/Distance[@Id='Z']/Value").text) * 1e6
    return xy_res, z_res

def xyz_res_from_nii(nii_path):
    img = nib.load(nii_path)
    affine = img.affine
    xy_res = abs(affine[0, 0] * 1e3) # Convert from mm to um
    z_res = abs(affine[2, 2] * 1e3)
    return xy_res, z_res

def xyz_res_from_tif(tif_path):
    with tifffile.TiffFile(tif_path) as tif:
        meta = tif.pages[0].tags
        ome_xml_str = meta['ImageDescription'].value
        ome_xml_root = etree.fromstring(ome_xml_str.encode('utf-8'))
        default_ns = ome_xml_root.nsmap[None]
        pixels_element = ome_xml_root.find(f'.//{{{default_ns}}}Pixels')
        xy_res, z_res = None, None
        xy_res = float(pixels_element.get('PhysicalSizeX'))
        z_res = float(pixels_element.get('PhysicalSizeZ'))
        return xy_res, z_res


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
    print(f"    Output: [default bold]{output}")


@print_func_name_args_times()
def save_as_tifs(ndarray, tif_dir_out, ndarray_axis_order="xyz"):
    """Save <ndarray> as tifs in <Path(tif_dir_out)>"""
    tif_dir_out.mkdir(parents=True, exist_ok=True)
    if ndarray_axis_order == "xyz":
        ndarray = np.transpose(ndarray, (2, 1, 0)) # Transpose to zyx (tiff expects zyx)
    for i, slice_ in enumerate(ndarray):
        slice_file_path = tif_dir_out / f"slice_{i:04d}.tif"
        imwrite(str(slice_file_path), slice_)
    print(f"    Output: [default bold]{tif_dir_out}")


####### Image processing #######

@print_func_name_args_times()
def resample_reorient(ndarray, xy_res, z_res, res, zoom_order=1):
    """Resample and reorient an ndarray for registration or warping to atlas space."""

    # Resample autofl image
    zf_xy = xy_res / res # Zoom factor
    zf_z = z_res / res
    img_resampled = ndimage.zoom(ndarray, (zf_xy, zf_xy, zf_z), order=zoom_order)

    # Reorient autofluo image
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