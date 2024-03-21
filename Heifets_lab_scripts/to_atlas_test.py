#!/usr/bin/env python3

import ants
import nibabel as nib
import numpy as np


### TODO: Make sure that uint16 is used instead of int16. Undo hard coding


# Load reference image
ref_image = ants.image_read('clar_allen_reg/init_allen.nii.gz')

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
input_image = ants.image_read('clar_allen_reg/sample16_08x_down_ochann_rb4_chan_ort_cp_org.nii.gz') 
ref_image_new = ants.image_read('/usr/local/unravel/atlases/gubra/gubra_template_25um.nii.gz') 

transforms = [
    'clar_allen_reg/init_tform.mat',  # Initial transformation matrix 
    'clar_allen_reg/comptx.nii.gz'  
]

output_image_2 = ants.apply_transforms(fixed=ref_image_new, moving=input_image, transformlist=transforms, interpolator='bSpline')

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
output_file_path = '/SSD3/mdma_v_meth/sample16/testing2_uint16.nii.gz'  


# Save the Nifti image using nibabel
nib.save(target_image_nii, output_file_path)
