#!/usr/bin/env python3

"""
Use ``atlas_relabel`` from UNRAVEL to convert intensities (e.g., atlas label IDs) based on a CSV.

Usage: 
------
    atlas_relabel -i path/old_image.nii.gz -o path/new_image.nii.gz -ic path/input.csv -oc volume_summary -odt uint16
"""

import argparse
import numpy as np
import nibabel as nib
import pandas as pd
from pathlib import Path
from rich import print
from rich.traceback import install

from unravel.core.config import Configuration
from unravel.core.argparse_utils import SuppressMetavar, SM
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg


def parse_args():
    parser = argparse.ArgumentParser(formatter_class=SuppressMetavar)
    parser.add_argument('-i', '--input', help='path/old_image.nii.gz', required=True, action=SM)
    parser.add_argument('-o', '--output', help='path/new_image.nii.gz', required=True, action=SM)
    parser.add_argument('-ic', '--csv_input', help='path/input.csv w/ old IDs in column 1 and new IDs in column 2', required=True, action=SM)
    parser.add_argument('-oc', '--csv_output', help='Optionally provide prefix to output label volume summaries (e.g., volume_summary)', default=None, action=SM)
    parser.add_argument('-odt', '--data_type', help='Output data type. Default: uint16', default="uint16", action=SM)
    parser.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)
    parser.epilog = __doc__
    return parser.parse_args()


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    # Load the specified columns from the CSV with CCFv3 info
    if Path(args.csv_input).exists() and args.csv_input.endswith('.csv'):
        df = pd.read_csv(args.csv_input)
    else:
        raise FileNotFoundError(f'CSV file not found: {args.csv_input}')
    
    # Get column names
    columns = df.columns

    # Convert values in columns to integers
    df[columns] = df[columns].astype(int)

    # Load the NIfTI image
    nii = nib.load(args.input)
    img = nii.get_fdata(dtype=np.float32)

    # Initialize an empty ndarray with the same shape as img and data type uint16
    if args.data_type: 
        new_img_array = np.zeros(img.shape, dtype=args.data_type)
    else:
        new_img_array = np.zeros(img.shape, dtype=np.uint16)

    # Replace voxel values in the new image array with the new labels
    for old_label, new_label in zip(df[columns[0]], df[columns[1]]):
        mask = img == old_label
        new_img_array[mask] = new_label

    # Convert the ndarray to an NIfTI image and save
    new_nii = nib.Nifti1Image(new_img_array, nii.affine, nii.header)
    nib.save(new_nii, args.output)

    # Summarize the volume for each label before and after the replacement
    if args.csv_output:
        old_labels, counts_old_labels = np.unique(img, return_counts=True)
        new_labels, counts_new_labels = np.unique(new_img_array, return_counts=True)
        volume_summary_old_labels = pd.DataFrame({columns[0]: old_labels, 'voxel_count': counts_old_labels})
        volume_summary_new_labels = pd.DataFrame({columns[1]: new_labels, 'voxel_count': counts_new_labels})
        volume_summary_old_labels.to_csv(f'{args.csv_output}_old_labels.csv', index=False)
        volume_summary_new_labels.to_csv(f'{args.csv_output}_new_labels.csv', index=False)

    verbose_end_msg()


if __name__ == '__main__':
    main()