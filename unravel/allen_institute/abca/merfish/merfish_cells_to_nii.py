#!/usr/bin/env python3

"""
Use ``abca_merfish_cells_to_nii`` or ``mc`` from UNRAVEL to convert ABCA MERFISH cells to a .nii.gz 3D image.

Prereqs:
    - ``merfish_cluster`` or ``merfish_filter`` to generate filtered cell data.

Usage:
------
    abca_merfish_cells_to_nii -i path/filtered_cells.csv -r path/to/reference.nii.gz [-b] [-o path/to/output.nii.gz] [-v]
"""

import nibabel as nib
import numpy as np
import pandas as pd
from pathlib import Path
from rich import print
from rich.traceback import install

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.config import Configuration 
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg, print_func_name_args_times


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-i', '--input', help='path/filtered_cells.csv', required=True, action=SM)
    reqs.add_argument('-r', '--ref_nii', help='Path to reference .nii.gz for header info (e.g., image_volumes/MERFISH-C57BL6J-638850-CCF/20230630/resampled_annotation.nii.gz)', required=True, action=SM)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-b', '--bin', help='Binarize the image. Default: False', action='store_true', default=False)
    opts.add_argument('-o', '--output', help='Output path for the saved .nii.gz image. Default: None', default=None, action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()


@print_func_name_args_times()
def merfish_cells_to_img(cell_df, img, xy_res, z_res):
    """
    Convert MERFISH cell metadata into a 3D image by marking voxel positions of cells.

    Parameters
    ----------
    cell_df : pd.DataFrame
        DataFrame containing filtered cell metadata with reconstructed coordinates.
    img : np.ndarray
        An empty 3D NumPy array shaped like the reference .nii.gz image.
    xy_res : float
        Resolution of the x-y plane in microns (µm).
    z_res : float
        Resolution of the z-plane in microns (µm).

    Returns
    -------
    np.ndarray
        A 3D image where cell positions are marked with 1.
    """
    if cell_df.empty:
        print("[bold yellow]Warning:[/bold yellow] No cells found in the input CSV. Returning empty image.")
        return img

    # Convert resolution to mm
    xy_res_mm = xy_res / 1000
    z_res_mm = z_res / 1000

    # Get image shape
    x_size, y_size, z_size = img.shape

    # Convert reconstructed coordinates to voxel indices
    cell_df['x_voxel'] = (cell_df['x_reconstructed'] / xy_res_mm).astype(int)
    cell_df['y_voxel'] = (cell_df['y_reconstructed'] / xy_res_mm).astype(int)
    cell_df['z_voxel'] = (cell_df['z_reconstructed'] / z_res_mm).astype(int)

    # Clip voxel indices to prevent out-of-bounds errors
    cell_df['x_voxel'] = cell_df['x_voxel'].clip(0, x_size - 1)
    cell_df['y_voxel'] = cell_df['y_voxel'].clip(0, y_size - 1)
    cell_df['z_voxel'] = cell_df['z_voxel'].clip(0, z_size - 1)

    # Remove NaNs to avoid indexing issues
    cell_df.dropna(subset=['x_voxel', 'y_voxel', 'z_voxel'], inplace=True)

    # Mark voxel positions in the image
    for _, row in cell_df.iterrows():
        img[row['x_voxel'], row['y_voxel'], row['z_voxel']] = 1

    return img

@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    # Load the filtered cell metadata
    cell_df = pd.read_csv(args.input, dtype={'cell_label': str}, usecols=['cell_label', 'brain_section_label', 'x_reconstructed', 'y_reconstructed', 'z_reconstructed'])

    # Load reference image
    ref_nii = nib.load(args.ref_nii)
    img = np.zeros(ref_nii.shape, dtype=np.uint8)

    # Convert cell data to a 3D image
    img = merfish_cells_to_img(cell_df, img, xy_res=10, z_res=200)

    # Binarize the image if specified
    if args.bin:
        img[img > 0] = 1

    # Set output path
    if args.output:
        output_path = Path(args.output)
    else:
        suffix = '_bin.nii.gz' if args.bin else '.nii.gz'
        output_path = str(Path(args.input)).replace('.csv', suffix)

    # Save the image as a .nii.gz file
    nii_img = nib.Nifti1Image(img, affine=ref_nii.affine, header=ref_nii.header)
    nib.save(nii_img, output_path)
    print(f"\n    [bold green]Saved image to {output_path}[/bold green]\n")

    verbose_end_msg()

if __name__ == '__main__':
    main()