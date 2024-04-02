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
    parser = argparse.ArgumentParser(description='''Summarize volumes of the top x regions and collapsing them into parent regions until a criterion is met.''',
                                     formatter_class=SuppressMetavar)
    parser.add_argument('-i', '--input', help='path/image.nii.gz', required=True, action=SM)
    parser.epilog = """
"""
    return parser.parse_args()




def main():
    args = parse_args()

    # Load the specified columns from the CSV with CCFv3 info
    ccfv3_ids_df = pd.read_csv(Path(__file__).parent / 'CCFv3_ID_dict__2017_to_2020.csv')
    id_dict = dict(ccfv3_ids_df['old_ID:new_ID'].str.split(':').apply(lambda x: (int(x[0]), int(x[1]))))
    
    print(id_dict)
    import sys ; sys.exit()

    # Load the NIfTI image
    nii_path = 'path_to_your_nii_image.nii.gz'  # Update this path
    img = nib.load(nii_path)
    data = img.get_fdata()

    # Replace voxel values based on the dictionary
    for old_id, new_id in id_dict.items():
        data = np.where(data == old_id, new_id, data)

    # Update the image with the new data
    new_img = nib.Nifti1Image(data, img.affine, img.header)

    # Save the modified image (optional)
    nib.save(new_img, 'modified_image.nii.gz')

    # Summarize the volume for each ID before and after the replacement
    volume_summary = pd.DataFrame(columns=['ID', 'Original Volume', 'New Volume'])
    for id_ in set(list(id_dict.keys()) + list(id_dict.values())):
        original_volume = (data == id_).sum()
        volume_summary = volume_summary.append({'ID': id_, 'Original Volume': original_volume, 'New Volume': original_volume}, ignore_index=True)

    # Save the volume summary to a CSV
    volume_summary.to_csv('volume_summary.csv', index=False)


if __name__ == '__main__':
    install()
    main()