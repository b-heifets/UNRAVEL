#!/usr/bin/env python3

"""

Use ``cstats_brain_model`` from UNRAVEL to prep an img.nii.gz and RGBA.txt LUT for vizualization in dsi_studio.

Prereqs:
    - Use ``cstats_summary`` or ``cstats_index`` to generate a valid cluster index.

Inputs:
    - input.nii.gz (e.g., a valid cluster index, but can be any binary or labeled image)

Outputs: 
    - img_ABA.nii.gz (Allen brain atlas labels were applied) or img_ABA_WB.nii.gz if -m was used (WB = Whole Brain)
    - rgba.txt (RGBA values for each region in the cluster index)

Note: 
    - The input image will be binarized and multiplied by the split atlas to apply region IDs.
    - Split means the left hemisphere region IDs are increased by 20000.
    - CCFv3-2020_regional_summary.csv is in UNRAVEL/unravel/core/csvs/
    - It has columns: Region_ID, ID_Path, Region, Abbr, General_Region, R, G, B
    - Alternatively, use CCFv3-2017_regional_summary.csv or provide a custom CSV with the same columns.

Next steps:
    - Use DSI Studio to visualize img_WB.nii.gz with the RGBA values.


Usage:
------
    cstats_brain_model -i input.nii.gz [-m] [-ax 2] [-s 0] [-sa atlas/atlas_CCFv3_2020_30um_split.nii.gz] [-csv CCFv3-2020_regional_summary.csv] [-v]
"""

import nibabel as nib
import numpy as np
import pandas as pd
from pathlib import Path
from rich import print
from rich.traceback import install

from unravel.core.argparse_rich_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.config import Configuration 
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg
from unravel.voxel_stats.mirror import mirror


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-i', '--input', help="path/img.nii.gz (e.g., a valid cluster map)", required=True, action=SM)

    opts_mirror = parser.add_argument_group('Optional args for mirroring the input')
    opts_mirror.add_argument('-m', '--mirror', help='Provide flag to mirror the input image for a bilateral representation.', action='store_true', default=False)
    opts_mirror.add_argument('-ax', '--axis', help='Axis to flip the image along if mirroing. Default: 2', default=2, type=int, action=SM)
    opts_mirror.add_argument('-s', '--shift', help='Number of voxels to shift content after flipping. Default: 0', default=0, type=int, action=SM)

    opts_coloring = parser.add_argument_group('Optional args for region coloring')
    opts_coloring.add_argument('-sa', '--split_atlas', help='path/split_atlas.nii.gz. Default: atlas/atlas_CCFv3_2020_30um_split.nii.gz', default='atlas/atlas_CCFv3_2020_30um_split.nii.gz', action=SM)
    opts_coloring.add_argument('-csv', '--csv_path', help='CSV name or path/name.csv. Default: CCFv3-2020_regional_summary.csv', default='CCFv3-2020_regional_summary.csv', action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()

# TODO: Consider consolidating regional_summary.csv (regional_summary_CCFv3-2017.csv) and CCFv3-2020_regional_summary.csv and ideally add logic to match usage automatic (i.e., no extra arg needed)


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    if args.mirror:
        output = args.input.replace('.nii.gz', '_ABA_WB.nii.gz')
    else:
        output = args.input.replace('.nii.gz', '_ABA.nii.gz')
        
    txt_output = args.input.replace('.nii.gz', '_rgba.txt')

    if Path(output).exists() and Path(txt_output).exists():
        print(f'{output} and {Path(txt_output).name} exist. Skipping.')
        return
        

    # Load the input NIFTI file
    nii = nib.load(args.input)
    img = np.asanyarray(nii.dataobj, dtype=nii.header.get_data_dtype()).squeeze()

    # Make a bilateral version of the cluster index
    if args.mirror:
        mirror_img = mirror(img, axis=args.axis, shift=args.shift)

        # Combine original and mirrored images
        img = img + mirror_img

    # Binarize
    img[img > 0] = 1

    # Multiply by atlas to apply region IDs to the cluster index
    atlas_nii = nib.load(args.split_atlas)
    atlas_img = np.asanyarray(atlas_nii.dataobj, dtype=atlas_nii.header.get_data_dtype()).squeeze()
    final_data = img * atlas_img

    # Save the bilateral version of the cluster index with ABA colors

    nib.save(nib.Nifti1Image(final_data, atlas_nii.affine, atlas_nii.header), output)

    # Calculate and save histogram
    histogram, _ = np.histogram(final_data, bins=21144, range=(0, 21144))

    # Exclude the background (region 0) from the histogram
    histogram = histogram[1:]

    # Determine what regions are present based on the histogram
    present_regions = np.where(histogram > 0)[0] + 1  # Add 1 to account for the background

    # Get R, G, B values for each region
    if args.csv_path == 'CCFv3-2017_regional_summary.csv' or args.csv_path == 'CCFv3-2020_regional_summary.csv': 
        color_map = pd.read_csv(Path(__file__).parent.parent / 'core' / 'csvs' / args.csv_path) #(Region_ID,ID_Path,Region,Abbr,General_Region,R,G,B)
    else:
        color_map = pd.read_csv(args.csv_path)

    # Delete rgba.txt if it exists (used for coloring the regions in DSI Studio)
    if Path(txt_output).exists():
        Path(txt_output).unlink()

    # Determine the RGB color for bars based on the region_id
    for region_id in present_regions:
        combined_region_id = region_id if region_id < 20000 else region_id - 20000
        region_rgb = color_map[color_map['Region_ID'] == combined_region_id][['R', 'G', 'B']]

        if region_rgb.empty:
            print(f"\n    [red1]Region ID {region_id} not found in the color map (see help regarding the -csv argument). Exiting.\n")
            if Path(txt_output).exists():
                Path(txt_output).unlink()
            import sys ; sys.exit()
    
        # Convert R, G, B values to space-separated R G B A values (one line per region)
        rgba_str = ' '.join(region_rgb.astype(str).values[0]) + ' 255'

        # Save the RGBA values to a .txt file
        with open(txt_output, 'a') as f:
            f.write(rgba_str + '\n')

    verbose_end_msg()


if __name__ == '__main__':
    main()