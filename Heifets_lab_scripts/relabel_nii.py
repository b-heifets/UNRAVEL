#!/usr/bin/env python3

import argparse
import numpy as np
import nibabel as nib
import pandas as pd
from argparse_utils import SuppressMetavar, SM
from pathlib import Path
from rich import print
from rich.traceback import install

def parse_args():
    parser = argparse.ArgumentParser(description='''Convert the intensities (e.g., atlas label IDs) based on a CSV.''', formatter_class=SuppressMetavar)
    parser.add_argument('-i', '--input', help='path/old_image.nii.gz', required=True, action=SM)
    parser.add_argument('-c', '--csv', help='path/input.csv w/ old IDs in column 1 and new IDs in column 2', required=True, action=SM)
    parser.add_argument('-o', '--output', help='path/new_image.nii.gz', required=True, action=SM)
    return parser.parse_args()


def main():
    args = parse_args()

    # Load the specified columns from the CSV with CCFv3 info
    if Path(args.csv).exists() and args.csv.endswith('.csv'):
        df = pd.read_csv(args.csv)
    else:
        raise FileNotFoundError(f'CSV file not found: {args.csv}')
    
    # Get column names
    columns = df.columns

    # Convert values in columns to integers
    df[columns] = df[columns].astype(int)

    # Load the NIfTI image
    nii = nib.load(args.input)
    img = nii.get_fdata()

    # Get the unique labelss in the image and voxel counts for each label
    old_labels, counts_old_labels = np.unique(img, return_counts=True)

    # Replace voxel values in the image with the new labels
    for old_label, new_label in zip(df[columns[0]], df[columns[1]]):
        # Where the img == old_label, replace with the new_label
        img = np.where(img == old_label, new_label, img) 

    # Get the unique labels in the image and voxel counts for each label after the replacement
    new_labels, counts_new_labels = np.unique(img, return_counts=True)

    # Convert the ndarray to an NIfTI image
    new_img = nib.Nifti1Image(img, nii.affine, nii.header)

    # Save the atlas with the new labels
    nib.save(new_img, args.output)

    # Summarize the volume for each label before and after the replacement
    volume_summary_old_labels = pd.DataFrame({columns[0]: old_labels, 'voxel_count': counts_old_labels})
    volume_summary_new_labels = pd.DataFrame({columns[1]: new_labels, 'voxel_count': counts_new_labels})

    # Save the volume summary to a CSV
    volume_summary_old_labels.to_csv('volume_summary_old_labels.csv', index=False)
    volume_summary_new_labels.to_csv('volume_summary_new_labels.csv', index=False)


if __name__ == '__main__':
    install()
    main()