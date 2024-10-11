#!/usr/bin/env python3

"""
Use ``_other/drafts/remap_atlas.py`` from UNRAVEL to remap an atlas, updating region IDs. 

Note:
    - Default csv: UNRAVEL/unravel/core/csvs/CCFv3-2020_info.csv
    
Usage:
------
    _other/drafts/remap_atlas.py -a path/to/atlas.nii.gz -csv path/to/CCFv3-2020_info.csv] [-v]
"""

import nibabel as nib
import numpy as np
import pandas as pd
from pathlib import Path
from rich import print
from rich.traceback import install

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.config import Configuration 
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg
from unravel.core.img_io import load_nii


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-a', '--atlas', help='Path to the atlas NIfTI file ', required=True, action=SM)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-csv', '--csv_path', help='CSV name or path/name.csv. Default: CCFv3-2020_info.csv', default='/Users/Danielthy/Documents/_GitHub/UNRAVEL_dev/unravel/core/csvs/CCFv3-2020_info.csv', action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()

# TODO: Change /Users/Danielthy/Documents/_GitHub/UNRAVEL_dev/unravel/core/csvs/CCFv3-2020_info.csv to CCFv3-2020_info.csv after testing

def convert_ids_to_general(atlas_img, id_mapping):
    converted_atlas = np.copy(atlas_img)
    unique_ids = np.unique(atlas_img)

    for uid in unique_ids:
        if uid in id_mapping:
            converted_atlas[atlas_img == uid] = id_mapping[uid]  # Update the region ID to the general region ID
        else:
            if uid != 0:
                print(f"Warning: ID {uid} not found in mapping.")
    
    return converted_atlas

@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    atlas_img = load_nii(args.atlas)

    # Load the specified columns from the CSV with CCFv3 info
    if args.csv_path == 'CCFv3-2017_info.csv' or args.csv_path == 'CCFv3-2020_info.csv': 
        ccf_df = pd.read_csv(Path(__file__).parent.parent / 'core' / 'csvs' / args.csv_path, usecols=['structure_ID', 'lowered_ID', 'structure_id_path', 'very_general_region'])
    else:
        ccf_df = pd.read_csv(args.csv_path, usecols=['structure_ID', 'lowered_ID', 'structure_id_path', 'very_general_region'])

    # Determine unique very_general_regions
    very_general_regions = ccf_df['very_general_region'].unique()

    # For each very_general_region, find the corresponding structure_ID at the first occurrence
    general_ids_df = {}
    for region in very_general_regions:
        general_ids_df[region] = ccf_df[ccf_df['very_general_region'] == region]['structure_ID'].values[0]

    # Drop some general regions that are not useful
    to_drop = ['root', 'grey matter', 'Cortical plate', 'Cerebral nuclei', 'Brain stem', 'Interbrain', 'Hindbrain', 'ventricular systems']
    for region in to_drop:
        general_ids_df.pop(region, None)

    # For each lowered_ID, find the corresponding very_general_region: structure_ID
    low_id__vgr = dict(zip(ccf_df['lowered_ID'], ccf_df['very_general_region']))

    # Make a mapping from lowered_ID to very_general_region: structure_ID
    low_id__general_id = {k: general_ids_df.get(v, 0) for k, v in low_id__vgr.items()}

    # Convert the atlas
    atlas_img_collapsed = convert_ids_to_general(atlas_img, low_id__general_id)

    # Save the new atlas as a .nii.gz file
    atlas_nii = nib.load(args.atlas)
    new_atlas_img = nib.Nifti1Image(atlas_img_collapsed, atlas_nii.affine, atlas_nii.header)
    new_atlas_path = Path(args.atlas).parent / f"{str(Path(args.atlas).name).replace('.nii.gz', '_collapsed.nii.gz')}"
    nib.save(new_atlas_img, new_atlas_path)

    print(f"\n    Collapsed atlas saved to {new_atlas_path}\n")

    verbose_end_msg()

if __name__ == '__main__':
    main()