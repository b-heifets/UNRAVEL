#!/usr/bin/env python3

import argparse
from pathlib import Path
import ants
import nibabel as nib
import numpy as np
from argparse_utils import SM, SuppressMetavar
from to_atlas import pad_img
from unravel_img_io import load_3D_img, resolve_path

from unravel_img_tools import reorient_for_raw_to_nii_conv, resample




def parse_args():
    parser = argparse.ArgumentParser(description='Warps native image to atlas space', formatter_class=SuppressMetavar)
    parser.add_argument('-e', '--exp_paths', help='List of experiment dir paths w/ sample?? dirs to process.', nargs='*', default=None, action=SM)
    parser.add_argument('-p', '--pattern', help='Pattern for sample?? dirs. Use cwd if no matches.', default='sample??', action=SM)
    parser.add_argument('-d', '--dirs', help='List of sample?? dir names or paths to dirs to process', nargs='*', default=None, action=SM)
    parser.add_argument('-i', '--input', help='INPUT: Path of native image relative to ./sample??', required=True, action=SM)
    parser.add_argument('-m', '--moving_img', help='Name of image to warp. Default: img_to_warp_to_atlas_space.nii.gz', default='img_to_warp_to_atlas_space.nii.gz', action=SM)
    parser.add_argument('-tr', '--target_res', help='Res of image just before warping in micron. Default=50', type=int, default=50, action=SM) ### Test if other res works


    parser.add_argument('-rf', '--reg_fixed', help='Name of file in transforms dir used as fixed input for registration. Default: clar.nii.gz', default='clar.nii.gz', action=SM)
    parser.add_argument('-o', '--output', help='Output path/img.nii.gz', default=None, action=SM)
    parser.add_argument('-c', '--chann_idx', help='.czi channel index. Default: 1', default=1, type=int, action=SM)
    parser.add_argument('-ort', '--ort_code', help='3 letter orientation code for reorienting (using the letters RLAPSI). Default: ALI', default='ALI', action=SM)
    parser.add_argument('-ln', '--label', help='Fluorescent label name (e.g., cfos). If raw data is tifs, should match tif dir name. Default: ochann)', default="ochann", action=SM)
    # parser.add_argument('-f', '--fixed_img', help='', action=SM)
    parser.add_argument('-ip', '--interpol', help='Interpolator for ants.apply_transforms (nearestNeighbor, genericLabel, linear, bSpline [default])', default="bSpline", action=SM)
    parser.add_argument('-a', '--atlas_name', help='Name of atlas (Default: gubra)', default="gubra", action=SM)
    parser.add_argument('--transforms', help="Name of folder w/ transforms from registration. Default: clar_allen_reg", default="clar_allen_reg", action=SM)
    parser.add_argument('-x', '--xy_res', help='Native x/y voxel size in microns (Default: get via metadata)', default=None, type=float, action=SM)
    parser.add_argument('-z', '--z_res', help='Native z voxel size in microns (Default: get via metadata)', default=None, type=float, action=SM)
    parser.add_argument('-r', '--reg_res', help='Registration resolution in microns (reg.py). Default: 50', default=50, type=int, action=SM)
    parser.add_argument('-fr', '--fixed_res', help='Resolution of the fixed reference image. Default: 25', default='25',type=int, action=SM)
    parser.add_argument('-zo', '--zoom_order', help='SciPy zoom order for resampling the native image. Default: 1', default=1, type=int, action=SM)
    parser.add_argument('-dt', '--dtype', help='Desired dtype for full res output (uint8, uint16). Default: moving_img.dtype', action=SM)
    parser.add_argument('-rp', '--reg_o_prefix', help='Registration output prefix. Default: allen_clar_ants', default='allen_clar_ants', action=SM)
    parser.add_argument('-l', '--legacy', help='Mode for backward compatibility (accounts for raw to nii reorienting)', action='store_true', default=False)
    parser.add_argument('-v', '--verbose', help='Enable verbose mode', action='store_true')
    parser.epilog = """Run script from the experiment directory w/ sample?? dir(s) or a sample?? dir
Example usage: to_atlas.py -i ochann -o test.nii.gz -x 3.5232 -z 6 [-l -v]

Prereq: ./parameters/metadata.txt (prep_reg.py or metadata.py)

Input examples (path is relative to ./sample??; 1st glob match processed): 
*.czi, autofluo/*.tif series, autofluo, *.tif, *.h5, or *.zarr 

"""
    return parser.parse_args()



### TODO: Make sure that uint16 is used instead of int16. Undo hard coding

args = parse_args()

# Load autofluo image [and xy and z voxel size in microns]
img, xy_res, z_res = load_3D_img('/SSD3/mdma_v_meth/sample16/ochann', args.chann_idx, "xyz", return_res=True, xy_res=args.xy_res, z_res=args.z_res)

fixed_img_for_reg = resolve_path('/SSD3/mdma_v_meth/sample16', Path(args.transforms, args.reg_fixed))

# Resample and reorient image
img = resample(img, xy_res, z_res, args.reg_res, zoom_order=args.zoom_order) 

# Reorient image if legacy mode is True
if args.legacy:
    img = reorient_for_raw_to_nii_conv(img)    

# Padding the image 
img = pad_img(img, pad_width=0.15)

# Convert to a NIfTI image
target_img = nib.Nifti1Image(img, np.eye(4))

# Load image to copy header info 
source_img = nib.load(fixed_img_for_reg)
new_affine = source_img.affine.copy()

# Determine scale factors from source affine by examining the length of the vectors
# This works regardless of the orientation or which axes are flipped
scale_factors = np.linalg.norm(source_img.affine[:3, :3], axis=0)

# Adjust scale factors in the new affine matrix according to target resolution
# We calculate the adjustment factor based on the target resolution divided by the original scale factor
# Then apply this adjustment maintaining the direction (sign) of the original scale factors
target_res = args.target_res / 1000
for i in range(3):
    adjustment_factor = np.array([target_res, target_res, target_res])[i] / scale_factors[i]
    new_affine[:3, i] = source_img.affine[:3, i] * adjustment_factor

# Copy relevant header information
hdr1 = source_img.header
hdr2 = target_img.header
fields_to_copy = [
    'xyzt_units', 'descrip', 'qform_code', 'sform_code',
    'qoffset_x', 'qoffset_y', 'qoffset_z', 'pixdim', 
]
for field in fields_to_copy:
    hdr2[field] = hdr1[field]

# Save the image to be warped
img = img.astype('float32') # FLOAT32 for ANTs
target_image_nii = nib.Nifti1Image(img, new_affine, hdr2)
transforms_path = Path(args.transforms).resolve() # Directory with transforms from registration
moving_img_path = transforms_path / args.moving_img
nib.save(target_image_nii, moving_img_path)

# Load the it as an ANTs image for warping
# moving_ants_img = ants.image_read(str(moving_img_path))
moving_ants_img = ants.image_read(str(moving_img_path)) 





# Load reference image
ref_image = ants.image_read(str(fixed_img_for_reg)) ### clar.nii.gz (was init_allen.nii.gz)

# Create a dummy moving image filled with zeros
dummy_moving = ants.make_image(ref_image.shape, voxval=0, spacing=ref_image.spacing, origin=ref_image.origin, direction=ref_image.direction)

# Specify the transformations
transforms = [
    'clar_allen_reg/allen_clar_ants1InverseWarp.nii.gz', 
    'clar_allen_reg/allen_clar_ants0GenericAffine.mat' 
]

# Apply the transformations to generate a composite deformation field
deformation_field = ants.apply_transforms(
    fixed=ref_image, 
    moving=dummy_moving, 
    transformlist=transforms, 
    whichtoinvert=[False, True], 
    compose='clar_allen_reg/' # comptx.nii.gz ########################
)

# Applying transformations including an initial transformation and resampling to a new space
# input_image = ants.image_read('clar_allen_reg/sample16_08x_down_ochann_rb4_chan_ort_cp_org.nii.gz') # used as moving before

ref_image_new = ants.image_read('/usr/local/unravel/atlases/gubra/gubra_template_25um.nii.gz') 

transforms = [
    'clar_allen_reg/init_tform.mat',  # Initial transformation matrix 
    'clar_allen_reg/comptx.nii.gz'  
]

output_image_2 = ants.apply_transforms(fixed=ref_image_new, moving=moving_ants_img, transformlist=transforms, interpolator='bSpline')

# Convert the ANTsImage to a numpy array 
output_array = output_image_2.numpy()

# Assumes that raw image data type is unsigned int 16
if np.max(output_array) < 65535: 
    # Set negative values to zero
    output_array[output_array < 0] = 0

    # Convert dtype
    output_array = output_array.astype(np.uint16)

# Convert to a NIfTI image
target_img = nib.Nifti1Image(output_array, np.eye(4))

# Load image to copy header info 
source_img = nib.load('/usr/local/unravel/atlases/gubra/gubra_ano_combined_25um.nii.gz') 
new_affine = source_img.affine.copy()

# Copy relevant header information
hdr1 = source_img.header
hdr2 = target_img.header
fields_to_copy = [
    'xyzt_units', 'descrip', 'qform_code', 'sform_code',
    'qoffset_x', 'qoffset_y', 'qoffset_z', 'pixdim', 
]
for field in fields_to_copy:
    hdr2[field] = hdr1[field]

# Save the image to be warped
target_image_nii = nib.Nifti1Image(output_array, new_affine, hdr2)
output_file_path = '/SSD3/mdma_v_meth/sample16/testing2_uint16_rb.nii.gz'  


# Save the Nifti image using nibabel
nib.save(target_image_nii, output_file_path)
