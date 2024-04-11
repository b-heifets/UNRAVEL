#!/usr/bin/env python3

import argparse
import nibabel as nib
import numpy as np
from rich.traceback import install

from argparse_utils import SM, SuppressMetavar
from unravel_img_tools import pad_img


def parse_args():
    parser = argparse.ArgumentParser(description='Adds 15 percent of padding to an image and saves it', formatter_class=SuppressMetavar)
    parser.add_argument('-i', '--input', help='path/img.nii.gz', required=True, action=SM)
    parser.add_argument('-o', '--output', help='path/img.nii.gz. Default: None (saves as path/img_pad.nii.gz) ', default=None, action=SM)
    return parser.parse_args()


def main(): 
    args = parse_args()

    nii = nib.load(args.input)
    img = nii.get_fdata(dtype=np.float32)
    data_type = nii.get_data_dtype()
    img = img.astype(data_type)

    # Pad the image
    img = pad_img(img, pad_width=0.15)

    # Save the padded image
    fixed_img_padded_nii = nib.Nifti1Image(img, nii.affine.copy(), nii.header)
    fixed_img_padded_nii.set_data_dtype(data_type)

    if args.output is None:
        padded_img_path = args.input.replace('.nii.gz', '_pad.nii.gz')
    else:
        padded_img_path = args.output

    nib.save(fixed_img_padded_nii, padded_img_path)

if __name__ == '__main__': 
    install()
    main()