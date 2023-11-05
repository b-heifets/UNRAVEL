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

# Helper function to resolve file path to first matching file in dir or file itself
def resolve_path(file_path, extension):
    """Return first matching file in dir or file itself if it matches the extension."""
    path = Path(file_path)
    if path.is_dir():
        sorted_files = sorted(path.glob(f"*.{extension}"))
        first_match = next(iter(sorted_files), None)
        return first_match
    return path if path.is_file() and path.suffix == f".{extension}" else None

@print_func_name_args_times()
def load_3D_img(file_path, channel=0, desired_axis_order="xyz"): 
    """Load <file_path> (.czi, .nii.gz, or .tif).
    file_path can be path to image file or dir (uses first *.czi, *.tif, or *.nii.gz match)
    Default: axis_order=xyz (other option: axis_order="zyx")
    Returns: ndarray, xy_res, z_res (resolution in um)
    """
    path = resolve_path(file_path, 'czi') or resolve_path(file_path, 'tif') or resolve_path(file_path, 'nii.gz') 
    if not path:
        print(f"    [red bold]No compatible image files found in {file_path}[/]")
        return None, None, None
    print(f"    [default]Loading {path.name}")
    if path.suffix == '.czi':
        czi = CziFile(path)
        ndarray = np.squeeze(czi.read_image(C=channel)[0])
        ndarray = np.transpose(ndarray, (2, 1, 0)) if desired_axis_order == "xyz" else ndarray
        xy_res, z_res = xyz_res_from_czi(czi)
    elif path.suffix in ['.tif', '.tiff']:
        tifs_stacked = []
        for tif_path in sorted(Path(path).parent.glob("*.tif")):
            with Image.open(tif_path) as img:
                tifs_stacked.append(np.array(img))
        ndarray = np.stack(tifs_stacked, axis=0)  # stack along the first dimension (z-axis)
        ndarray = np.transpose(ndarray, (2, 1, 0)) if desired_axis_order == "xyz" else ndarray
        xy_res, z_res = xyz_res_from_tif(path)
    elif path.suffix in ['.nii', '.nii.gz']:
        img = nib.load(path)
        ndarray = img.get_fdata()
        ndarray = np.transpose(ndarray, (2, 1, 0)) if desired_axis_order == "zyx" else ndarray
        xy_res, z_res = xyz_res_from_nii(path)
    else:
        print(f"    [red bold]Unsupported file type: {path.suffix}\n    Supported file types: .czi, .tif, .tiff, .nii, .nii.gz\n")
        return None, None, None

    return ndarray, xy_res, z_res

def xyz_res_from_czi(czi_path):
    xml_root = czi_path.meta
    scaling_info = xml_root.find(".//Scaling")
    xy_res = float(scaling_info.find("./Items/Distance[@Id='X']/Value").text) * 1e6
    z_res = float(scaling_info.find("./Items/Distance[@Id='Z']/Value").text) * 1e6
    return xy_res, z_res

def xyz_res_from_nii(nii_path):
    img = nib.load(nii_path)
    affine = img.affine
    xy_res = affine[0, 0] * 1e6
    z_res = affine[2, 2] * 1e6
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

def process_slice(slice_, struct_element):
    smoothed_slice = cv2.morphologyEx(slice_, cv2.MORPH_OPEN, struct_element)
    return slice_ - smoothed_slice

def rolling_ball_subtraction_opencv_parallel(ndarray, radius, threads=8):
    """Subtract background from <ndarray> using OpenCV. 
    Uses multiple threads to process slices in parallel.
    Radius is the radius of the rolling ball in pixels.
    """
    struct_element = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2*radius+1, 2*radius+1)) # 2D disk
    result = np.empty_like(ndarray) # Preallocate the result array
    num_cores = min(len(ndarray), threads) # Number of available CPU cores
    with ThreadPoolExecutor(max_workers=num_cores) as executor:
        for i, background_subtracted_slice in enumerate(executor.map(process_slice, ndarray, [struct_element]*len(ndarray))):
            result[i] = background_subtracted_slice
    return result