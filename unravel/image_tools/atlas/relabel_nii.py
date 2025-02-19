#!/usr/bin/env python3

"""
Use ``atlas_relabel`` (``relabel``) from UNRAVEL to convert intensities (e.g., atlas label IDs) based on a CSV.

Inputs:
    - old_image.nii.gz: Lable image with original intensities.
    - input.csv: CSV with old IDs in column 1 and new IDs in column 2.

Outputs:
    - new_image.nii.gz: Image with relabeled intensities.
    - relabel_nii_volume_summary_old_labels.csv: Summary of the volume for each label before the replacement.
    - relabel_nii_volume_summary_new_labels.csv: Summary of the volume for each label after the replacement.

Usage: 
------
    atlas_relabel -i path/old_image.nii.gz -o path/new_image.nii.gz -ci path/input.csv [-vols] [-odt uint16] [-v]
"""

import numpy as np
import nibabel as nib
import pandas as pd
from pathlib import Path
from rich import print
from rich.traceback import install

from unravel.core.config import Configuration
from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM

from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-i', '--input', help='path/old_image.nii.gz', required=True, action=SM)
    reqs.add_argument('-ci', '--csv_input', help='path/input.csv w/ old IDs in column 1 and new IDs in column 2', required=True, action=SM)
    reqs.add_argument('-o', '--output', help='path/new_image.nii.gz', required=True, action=SM)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-vols', '--volumes', help='Provide flag to output label volume summaries', default=None, action=SM)
    opts.add_argument('-odt', '--data_type', help='Output data type. Default: uint16', default="uint16", action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

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
    if args.output:
        old_labels, counts_old_labels = np.unique(img, return_counts=True)
        new_labels, counts_new_labels = np.unique(new_img_array, return_counts=True)
        volume_summary_old_labels = pd.DataFrame({columns[0]: old_labels, 'voxel_count': counts_old_labels})
        volume_summary_new_labels = pd.DataFrame({columns[1]: new_labels, 'voxel_count': counts_new_labels})
        volume_summary_old_labels.to_csv(f'relabel_nii_volume_summary_old_labels.csv', index=False) 
        volume_summary_new_labels.to_csv(f'relabel_nii_volume_summary_new_labels.csv', index=False)

    verbose_end_msg()


if __name__ == '__main__':
    main()