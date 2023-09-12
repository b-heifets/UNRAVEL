#!/usr/bin/env python3

import argparse
import nibabel as nib
import numpy as np
import os
import subprocess
import sys
import unravel_utils as unrvl

# Adapted from miracl_reg_warp_clar_to_allen.sh by Daniel Rijsketic (09/12/2023)

def parse_args():
    parser = argparse.ArgumentParser(description='Warp image data to atlas space')
    parser.add_argument('-i', '--input', required=True, help='Input downsampled .nii.gz to warp', metavar='')
    parser.add_argument('-rd', '--regdir', required=True, help='Folder w/ intermediate reg images (Default: clar_allen_reg)', default='clar_allen_reg', metavar='')
    parser.add_argument('-oc', '--ort_code', required=True, help='(3 letter orientation code: A/P=Anterior/Posterior, L/R=Left/Right, S/I=Superior/Interior)', metavar='')
    parser.add_argument('-t', '--template', help='Template to warp to (path/gubra_template_25um.nii.gz)', default="/usr/local/unravel/atlases/gubra/gubra_template_25um.nii.gz",  metavar='')
    parser.add_argument('-a', '--atlas_name', help='Name of atlas (Default: gubra)', default="gubra", metavar='')
    parser.add_argument('-r', '--res', help='Atlas resolution in microns (Default: 25)', default=25, type=int, metavar='')
    return parser.parse_args()

def check_ants_path():
    try:
        ants_path = subprocess.check_output(["which", "antsRegistration"]).decode('utf-8').strip()
        
        if not ants_path:
            raise FileNotFoundError("ANTS program can't be found. Please (re)define $ANTSPATH in your environment.")
        
        print("\nANTS path check: OK...")
        
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("ANTS program can't be found. Please (re)define $ANTSPATH in your environment.")
        sys.exit(1)

def reorient_nii(image, ort_cord):
    """
    Reorient a 3D image based on the orientation code (using the letters RLAPSI). Assumes initial orientation is RAS (NIFTI convention).
    """

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

    # Validate input
    if len(ort_cord) != 3:
        raise ValueError("Invalid orientation code. Must be a 3-letter code consisting of RLAPSI.")

    # Determine new orientation based on the code
    new_axes_order = [direction_map[c] for c in ort_cord]

    # Reorder the axes
    reoriented_volume = np.transpose(image, axes=new_axes_order)

    # Flip axes as necessary
    for idx, c in enumerate(ort_cord):
        if flip_map[c]:
            reoriented_volume = np.flip(reoriented_volume, axis=idx)

    return reoriented_volume


def reorient_and_pad_image(args=None):
    img = nib.load(args.input)
    img_data = img.get_fdata()

    # Reorient the image
    # (Assuming you have a function to reorient the image based on ort_code)
    img_data_reoriented = reorient_nii(img_data, args.ort_code) 

    # Padding the image
    pad_percent = 0.15  # 15%
    pad_x = int(img_data_reoriented.shape[0] * pad_percent)
    pad_y = int(img_data_reoriented.shape[1] * pad_percent)
    pad_z = 0
    img_data_padded = np.pad(img_data_reoriented, ((pad_x, pad_x), (pad_y, pad_y), (pad_z, pad_z)), mode='constant')

    # Change the type to 'short'
    img_data_short = img_data_padded.astype(np.int16)

    # Save the new image
    img_new = nib.Nifti1Image(img_data_short, img.affine)
    base = os.path.basename(args.input)
    img_name = os.path.splitext(base)[0]
    img_ort = f'{img_name}_ort.nii.gz'
    nib.save(img_new, img_ort)

    return img_name, img_ort


def warp_to_atlas(img_name, img_ort, args):
    
    # Warp image to atlas space
    warped_img = os.path.join(os.getcwd() , f"{img_name}_{args.atlas}_space.nii.gz")
    subprocess.run("antsApplyTransforms "\
                "-d 3 "\
                f"-r {args.template} "\
                f"-i {img_ort} "\
                "-n Bspline "\
                f"-t [{args.regdir}/init_tform.mat, 1] {args.regdir}/allen_clar_ants1InverseWarp.nii.gz [{args.regdir}/allen_clar_ants0GenericAffine.mat, 1] "\
                f"-o {warped_img}", \
                shell=True)
    
    # Delete intermediate files
    # subprocess.run(f"rm {img_ort}", shell=True)

    return img_name, warped_img


def main():
    args = parse_args()

    check_ants_path()
    
    img_name, img_ort = reorient_and_pad_image(args)

    warp_to_atlas(img_name, img_ort, args)


if __name__ == '__main__':
    main()