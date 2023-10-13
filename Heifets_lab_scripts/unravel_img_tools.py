#!/usr/bin/env python3

import nibabel as nib
import numpy as np
import subprocess
import tifffile
from aicspylibczi import CziFile
from glob import glob
from lxml import etree
from pathlib import Path
from scipy import ndimage
from tifffile import imread, imwrite 
from unravel_utils import print_func_name_args_times


######## Load images ########

@print_func_name_args_times(arg_index_for_basename=0)
def load_czi_channel(czi_path, channel):
    """Load a channel from a .czi image and return it as a numpy array."""
    if czi_path:
        czi = CziFile(czi_path)
        ndarray = czi.read_image(C=channel)[0]
        ndarray = np.squeeze(ndarray)
        ndarray = np.transpose(ndarray, (2, 1, 0))
        return ndarray
    else:
        print(f"  [red bold].czi file not found: {czi_path}[/]")
        return None

@print_func_name_args_times(arg_index_for_basename=0)
def load_nii(img_path):
    """Load a .nii.gz image and return it as a numpy array."""
    if img_path:
        img = nib.load(img_path)
        ndarray = img.get_fdata()
        return ndarray
    else:
        print(f"  [red bold].nii.gz file note found: {img_path}[/]")
        return None

@print_func_name_args_times(arg_index_for_basename=0)
def load_tifs(tif_dir_path): 
    """Load a series of .tif images and return them as a numpy array."""
    tifs = glob(f"{tif_dir_path}/*.tif")
    if tifs:
        tifs_sorted = sorted(tifs)
        tifs_stacked = [imread(tif) for tif in tifs_sorted]
        ndarray = np.stack(tifs_stacked, axis=0)  # stack along the first dimension (z-axis)
        return ndarray # shape: z, y, x
    else:
        print(f"  [red bold]No .tif files found in {tif_dir_path}[/]")
        return None


######## Get metadata ########

@print_func_name_args_times(arg_index_for_basename=0)
def xyz_res_from_czi(czi_path):
    """Extract metadata from .czi file and returns tuple with xy_res and z_res (voxel size) in microns."""
    czi = CziFile(czi_path)
    xml_root = czi.meta
    xy_res, z_res = None, None
    scaling_info = xml_root.find(".//Scaling")
    if scaling_info is not None:
        xy_res = float(scaling_info.find("./Items/Distance[@Id='X']/Value").text)*1e6
        z_res = float(scaling_info.find("./Items/Distance[@Id='Z']/Value").text)*1e6
    return xy_res, z_res

@print_func_name_args_times(arg_index_for_basename=0)
def xyz_res_from_tif(path_to_first_tif_in_series):
    """Extract metadata from .ome.tif file and returns tuple with xy_res and z_res in microns."""
    with tifffile.TiffFile(path_to_first_tif_in_series) as tif:
        meta = tif.pages[0].tags
        ome_xml_str = meta['ImageDescription'].value
        ome_xml_root = etree.fromstring(ome_xml_str.encode('utf-8'))
        default_ns = ome_xml_root.nsmap[None]
        pixels_element = ome_xml_root.find(f'.//{{{default_ns}}}Pixels')
        xy_res, z_res = None, None
        xy_res = float(pixels_element.get('PhysicalSizeX'))
        z_res = float(pixels_element.get('PhysicalSizeZ'))
        return xy_res, z_res


######## Save images ########

@print_func_name_args_times(arg_index_for_basename=0)
def save_as_nii(ndarray, output, x_res, y_res, z_res, data_type):
    """Save a numpy array as a .nii.gz image."""

    output = Path(output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    # Reorient ndarray
    ndarray = np.transpose(ndarray, (2, 1, 0))
    
    # Create the affine matrix with the appropriate resolutions (converting microns to mm)
    affine = np.diag([x_res / 1000, y_res / 1000, z_res / 1000, 1])
    
    # Create and save the NIFTI image
    nifti_img = nib.Nifti1Image(ndarray, affine)
    nifti_img.header.set_data_dtype(data_type)
    nib.save(nifti_img, str(output))
    
    print(f"\n  Output: [default bold]{output}[/]\n")

@print_func_name_args_times(arg_index_for_basename=0)
def save_as_tifs(ndarray, tif_dir_out):
    """Save a numpy array as a series of .tif images."""
    tif_dir_out.mkdir(parents=True, exist_ok=True)
    for i, slice_ in enumerate(ndarray):
        slice_file_path = tif_dir_out / f"slice_{i:04d}.tif"
        imwrite(str(slice_file_path), slice_)
    print(f"\n  Output: [default bold]{tif_dir_out}[/]\n")


######## Image processing ########

@print_func_name_args_times(arg_index_for_basename=0)
def resample_reorient(ndarray, xy_res, z_res, res, zoom_order=1):
    """Resample and reorient an ndarray for registration or warping to atlas space."""

    # Resample autofl image
    zf_xy = xy_res / res # Zoom factor
    zf_z = z_res / res
    img_resampled = ndimage.zoom(ndarray, (zf_xy, zf_xy, zf_z), order=zoom_order)

    # Reorient autofluo image
    img_reoriented = np.einsum('zyx->xzy', img_resampled)
    
    return img_reoriented

@print_func_name_args_times(arg_index_for_basename=0)
def ilastik_segmentation(tif_dir, ilastik_project, output_dir, ilastik_log=None, args=None):
    """Segment tif series with Ilastik."""
    tif_dir = str(Path(tif_dir).resolve())
    tif_list = glob(f"{tif_dir}/*.tif")
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