#!/usr/bin/env python3

import sys
import nibabel as nib
from nibabel.orientations import axcodes2ornt, ornt_transform, io_orientation, inv_ornt_aff

def set_nii_orientation(nii_img, target_axcodes, zero_origin=True, qform_code=1, sform_code=1):
    """Set the orientation the the .nii.gz image header
    
    Arguments: 
    nii_img: a NIfTI image object from nibabel
    target_axcodes: a tuple of axis codes like ('R', 'A', 'S') or ('L', 'P', 'S')
    """

    print(f'\n{nii_img.affine}\n')
    import sys ; sys.exit()

    img = nii_img.get_fdata() 

    # Determine the current orientation of the ndarray
    current_ornt = io_orientation(nii_img.affine)

    # Convert target axis codes to an orientation
    target_ornt = axcodes2ornt(target_axcodes)

    # Find the transformation needed
    transformation_ornt = ornt_transform(current_ornt, target_ornt)

    # Adjust the affine to match the new orientation
    new_affine = inv_ornt_aff(transformation_ornt, img.shape) @ nii_img.affine

    # Zero the origin:
    if zero_origin:
        for i in range(3):
            new_affine[i,3] = 0     
        
    # Make the .nii.gz image with the adjusted header.
    nii_img_oriented = nib.Nifti1Image(img, new_affine, nii_img.header)

    # Set the header information
    nii_img_oriented.header['xyzt_units'] = 10 # mm, s
    nii_img_oriented.header['qform_code'] = qform_code
    nii_img_oriented.header['sform_code'] = sform_code
    nii_img_oriented.header['regular'] = b'r'

    return nii_img_oriented

nii = nib.load(sys.argv[1])

nii_img_oriented = set_nii_orientation(nii, ('P', 'I', 'R'))

nib.save(nii_img_oriented, sys.argv[2])



input_path = sys.argv[1]  
output_path = sys.argv[2]  
reorient_nii_image(input_path, output_path, target_axcodes=('P', 'I', 'R'))