#!/usr/bin/env python3

import argparse
import ants
import nibabel as nib
import numpy as np
from pathlib import Path
from rich import print
from rich.live import Live
from rich.traceback import install

from argparse_utils import SM, SuppressMetavar
from unravel_config import Configuration
from unravel_img_io import load_3D_img, resolve_path
from unravel_img_tools import pad_img, reorient_for_raw_to_nii_conv, resample
from unravel_utils import print_func_name_args_times, print_cmd_and_times, initialize_progress_bar, get_samples


def parse_args():
    parser = argparse.ArgumentParser(description='Warps native image to atlas space', formatter_class=SuppressMetavar)
    parser.add_argument('-e', '--exp_paths', help='List of experiment dir paths w/ sample?? dirs to process.', nargs='*', default=None, action=SM)
    parser.add_argument('-p', '--pattern', help='Pattern for sample?? dirs. Use cwd if no matches.', default='sample??', action=SM)
    parser.add_argument('-d', '--dirs', help='List of sample?? dir names or paths to dirs to process', nargs='*', default=None, action=SM)

    # Required arguments:
    parser.add_argument('-i', '--input', help='INPUT: Path of native image relative to ./sample??', required=True, action=SM)
    parser.add_argument('-o', '--output', help='Output path/img.nii.gz', required=True, action=SM)

    # Optional arguments:
    parser.add_argument('-c', '--chann_idx', help='.czi channel index. Default: 1', default=1, type=int, action=SM)
    parser.add_argument('-x', '--xy_res', help='Native x/y voxel size in microns (Default: get via metadata)', default=None, type=float, action=SM)
    parser.add_argument('-z', '--z_res', help='Native z voxel size in microns (Default: get via metadata)', default=None, type=float, action=SM)
    parser.add_argument('-ro', '--reg_outputs', help="Name of folder w/ outputs from reg.py (e.g., transforms). Default: reg_outputs", default="reg_outputs", action=SM)
    parser.add_argument('-a', '--atlas', help='path/atlas.nii.gz (Default: /usr/local/unravel/atlases/gubra/gubra_ano_combined_25um.nii.gz)', default='/usr/local/unravel/atlases/gubra/gubra_ano_combined_25um.nii.gz', action=SM)
    parser.add_argument('-t', '--template', help='path/template.nii.gz (Default: /usr/local/unravel/atlases/gubra/gubra_template_25um.nii.gz)', default='/usr/local/unravel/atlases/gubra/gubra_template_25um.nii.gz', action=SM)
    parser.add_argument('-m', '--moving_img', help='Name of image to warp (saved in reg_outputs dir). Default: img_to_warp_to_atlas_space.nii.gz', default='img_to_warp_to_atlas_space.nii.gz', action=SM)
    parser.add_argument('-dt', '--dtype', help='Desired dtype for output (e.g., uint8, uint16). Default: args.input.dtype', default=None, action=SM)
    parser.add_argument('-ar', '--atlas_res', help='Resolution of atlas in microns. Default=25', type=int, default=25, action=SM)
    parser.add_argument('-rf', '--reg_fixed', help='Name of fixed reg input in ./reg_outputs. Default: autofl_50um_masked_fixed_reg_input.nii.gz', default='autofl_50um_masked_fixed_reg_input.nii.gz', action=SM)
    parser.add_argument('-ip', '--interpol', help='Interpolator for ants.apply_transforms (nearestNeighbor, multiLabel, linear, bSpline [default])', default="bSpline", action=SM)
    parser.add_argument('-zo', '--zoom_order', help='SciPy zoom order for resampling the native image. Default: 1', default=1, type=int, action=SM)
    parser.add_argument('-tp', '--tform_prefix', help='Registration output prefix. Default: ANTsPy_', default='ANTsPy_', action=SM)
    parser.add_argument('-l', '--miracl', help='Mode for backward compatibility (accounts for raw to nii reorienting)', action='store_true', default=False)
    parser.add_argument('-v', '--verbose', help='Enable verbose mode', action='store_true')
    parser.epilog = """Run script from the experiment directory w/ sample?? dir(s) or a sample?? dir
Example usage: to_atlas.py -i ochann -o img_in_atlas_space.nii.gz -x 3.5232 -z 6 [-mi -v]

Prereqs: 
reg.py

Input examples (path is relative to ./sample??; 1st glob match processed): 
*.czi, ochann/*.tif, ochann, *.tif, *.h5, or *.zarr 
"""
    return parser.parse_args()


@print_func_name_args_times()
def copy_nii_header(source_img, new_img):
    """Copy header info from nii_img to new_img"""
    fields_to_copy = [
        'xyzt_units', 'descrip', 'qform_code', 'sform_code',
        'qoffset_x', 'qoffset_y', 'qoffset_z', 'pixdim', 
    ]
    for field in fields_to_copy:
        new_img.header[field] = source_img.header[field]

    return new_img

@print_func_name_args_times()
def to_atlas(img, xy_res, z_res, reg_outputs_path, atlas_res, zoom_order, interpol, reg_fixed, tform_prefix, moving_img, output_dtype, atlas_path, template_path, output, miracl=False):
    """Warp native image to atlas space using ANTs.
    
    Args:
        img (np.ndarray): 3D image to warp
        xy_res (float): x/y resolution in microns
        z_res (float): z resolution in microns
        reg_outputs_path (Path): Path to directory with outputs (e.g., transforms) from registration
        atlas_res (int): Resolution of the image just before warping in microns (also the resolution of the atlas)
        zoom_order (int): SciPy zoom order for resampling the native image
        interpol (str): Interpolator for ants.apply_transforms
        reg_fixed (str): Name of file in reg_outputs dir used as fixed input for registration
        tform_prefix (str): Registration output prefix
        moving_img (str): Name of image to warp (saved in reg_outputs_path dir)
        atlas_path (str): Path to the atlas
        output (str): Output path/img.nii.gz
        miracl (bool): Compatibility with miracl (accounts for raw to nii reorienting)
        
    Outputs:
        Warped image saved to output path"""

    # Load image used as fixed input for registration to copy header info
    fixed_img_for_reg_nii = nib.load(Path(reg_outputs_path, reg_fixed))

    # Get dtype from input image if not specified
    if output_dtype is None:
        output_dtype = img.dtype

    # Resample and reorient image
    img = resample(img, xy_res, z_res, atlas_res, zoom_order=zoom_order) 

    # Reorient image if miracl mode is True
    if miracl:
        img = reorient_for_raw_to_nii_conv(img)    

    # Padding the image 
    img = pad_img(img, pad_width=0.15)

    # Conver ndarray to FLOAT32 for ANTs
    img = img.astype('float32') 

    new_affine = fixed_img_for_reg_nii.affine.copy()

    # Determine scale factors from source affine by examining the length of the vectors
    # This works regardless of the orientation or which axes are flipped
    scale_factors = np.linalg.norm(fixed_img_for_reg_nii.affine[:3, :3], axis=0) # Euclidean norm of each column

    # Adjust scale factors in the new affine matrix according to target resolution
    # We calculate the adjustment factor based on the target resolution divided by the original scale factor
    # Then apply this adjustment maintaining the direction (sign) of the original scale factors
    atlas_res_in_mm = atlas_res / 1000
    for i in range(3):
        adjustment_factor = np.array([atlas_res_in_mm, atlas_res_in_mm, atlas_res_in_mm])[i] / scale_factors[i]
        new_affine[:3, i] = fixed_img_for_reg_nii.affine[:3, i] * adjustment_factor

    # Convert to a NIfTI image
    img_nii = nib.Nifti1Image(img, new_affine)

    # Set the header information
    img_nii.header['xyzt_units'] = 10 # mm, s 
    img_nii.header['qform_code'] = fixed_img_for_reg_nii.header['qform_code'] 
    img_nii.header['sform_code'] = fixed_img_for_reg_nii.header['sform_code'] 
    img_nii.header['pixdim'][1:] = atlas_res_in_mm, atlas_res_in_mm, atlas_res_in_mm, 0, 0, 0, 0
    img_nii.header['regular'] = b'r'
    img_nii.set_sform(new_affine)

    # Save the resampled image
    nib.save(img_nii, Path(reg_outputs_path, moving_img))

    # Load img_nii as an ANTs image for warping
    moving_ants_img = ants.image_read(str(Path(reg_outputs_path, moving_img))) 

    # Load reference image
    ref_image = ants.image_read(str(Path(reg_outputs_path, reg_fixed)))

    # Create a dummy moving image filled with zeros
    dummy_moving = ants.make_image(ref_image.shape, voxval=0, spacing=ref_image.spacing, origin=ref_image.origin, direction=ref_image.direction)

    # Specify the transformations
    transforms = [
        str(reg_outputs_path / f'{tform_prefix}1InverseWarp.nii.gz'), 
        str(reg_outputs_path / f'{tform_prefix}0GenericAffine.mat') 
    ]

    # Apply the transformations to generate a composite deformation field
    deformation_field = ants.apply_transforms(
        fixed=ref_image, 
        moving=dummy_moving, 
        transformlist=transforms, 
        whichtoinvert=[False, True], 
        compose=f'{reg_outputs_path}/' # dir to output comptx.nii.gz
    )

    # Applying transformations from registration and the initial alignment
    template = ants.image_read(template_path) 
    transforms = [
        str(reg_outputs_path / f'{tform_prefix}init_tform.mat'), # Initial transformation matrix 
        str(reg_outputs_path / 'comptx.nii.gz') # Composite transformation field
    ]
    warped_img_ants = ants.apply_transforms(fixed=template, moving=moving_ants_img, transformlist=transforms, interpolator=interpol)

    # Convert the ANTsImage to a numpy array 
    warped_img = warped_img_ants.numpy()

    # Convert dtype of warped image to match input image
    if np.issubdtype(output_dtype, np.unsignedinteger):
        warped_img[warped_img < 0] = 0 # If output_dtype is unsigned, set negative values to zero
    warped_img = warped_img.astype(output_dtype)

    # Convert the warped image to NIfTI, copy relevant header information, and save it
    atlas = nib.load(atlas_path) 
    warped_img_nii = nib.Nifti1Image(warped_img, atlas.affine.copy())
    warped_img_nii = copy_nii_header(atlas, warped_img_nii)
    nib.save(warped_img_nii, output)


def main():    

    samples = get_samples(args.dirs, args.pattern, args.exp_paths)

    progress, task_id = initialize_progress_bar(len(samples), "[red]Processing samples...")
    with Live(progress):
        for sample in samples:
            
            sample_path = Path(sample).resolve() if sample != Path.cwd().name else Path.cwd()

            output = resolve_path(sample_path, args.output)
            if output.exists():
                print(f"\n\n    {output} already exists. Skipping.\n")
                return

            # Load full res image [and xy and z voxel size in microns], to be resampled [and reoriented], padded, and warped
            img_path = resolve_path(sample_path, args.input)
            img, xy_res, z_res = load_3D_img(img_path, args.chann_idx, "xyz", return_res=True, xy_res=args.xy_res, z_res=args.z_res)

            # Directory with outputs (e.g., transforms) from registration
            reg_outputs_path = resolve_path(sample_path, args.reg_outputs)

            # Warp native image to atlas space
            to_atlas(img, xy_res, z_res, reg_outputs_path, args.atlas_res, args.zoom_order, args.interpol, args.reg_fixed, args.tform_prefix, args.moving_img, args.dtype, args.atlas, args.template, args.output, miracl=args.miracl)

            progress.update(task_id, advance=1)


if __name__ == '__main__': 
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    print_cmd_and_times(main)()