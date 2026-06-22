#!/usr/bin/env python3

"""
Use ``coords_labeled_voxel_img_to_points`` or ``labeled_voxel_img_to_points`` from UNRAVEL
to decode a labeled voxel image back into a table of label coordinates.

This is useful after a unique-voxel labeled image has been reoriented,
resampled, or warped into another space, e.g. MERFISH-CCF space.

Input:
    - labeled .nii.gz image where each nonzero value is a voxel_label
    - optional mapping CSV from ``points_to_labeled_voxel_img`` linking voxel_label to original metadata

Output:
    - CSV with one row per voxel_label and coordinates in the current image space

Note:
    - If warping creates multiple voxels for the same label, coordinates are
      summarized by centroid, median, and mode-like first voxel.
    - Use centroid_x/y/z for sphere-mask creation unless you prefer an integer
      voxel coordinate. The rounded centroid columns are also provided.    

Usage:
------
    labeled_voxel_img_to_points \\
        -i unique_voxels_labeled_MERFISH.nii.gz \\
        -map unique_voxels/units__unique_voxel_mapping.csv \\
        -o unique_voxels_MERFISH_coords.csv \\
        -v
"""

from pathlib import Path

import numpy as np
import pandas as pd
from rich import print
from rich.traceback import install

from unravel.core.config import Configuration
from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.img_io import load_3D_img
from unravel.core.utils import get_stem, log_command, verbose_start_msg, verbose_end_msg


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group("Required arguments")
    reqs.add_argument("-i", "--input", help="Input labeled image.", required=True, action=SM)
    reqs.add_argument("-m", "--mode", help="Mode for summarizing coordinates. Options are 'centroid_rounded', 'centroid_float', 'median', or 'first'. Default is 'centroid_rounded'.", default="centroid_rounded", action=SM)

    opts = parser.add_argument_group("Optional arguments")
    opts.add_argument("-map", "--mapping_csv", help="Optional unique voxel mapping CSV to merge.", default=None, action=SM)
    opts.add_argument("-o", "--output", help="Output CSV path. Default: input stem + _points.csv", default=None, action=SM)

    general = parser.add_argument_group("General arguments")
    general.add_argument("-v", "--verbose", help="Increase verbosity. Default: False", action="store_true", default=False)

    return parser.parse_args()

def summarize_label_coords(label, coords, mode="centroid_rounded"):
    """Summarize coordinates for one label and return a dict.
    
    Parameters:
    -----------
    label : int
        The voxel label being summarized.
    coords : ndarray
        An Nx3 array of voxel coordinates corresponding to the given label.
    mode : str
        The method for summarizing coordinates. Options are:
        - 'centroid_rounded': Compute the centroid and round to the nearest integer voxel coordinate
        - 'centroid_float': Compute the centroid and keep as float (physical space)
        - 'median': Compute the median coordinate across all voxels
        - 'first': Take the coordinates of the first voxel (mode-like)

    Returns:
    --------
    dict
        A dictionary for a row with keys 'voxel_label', 'x', 'y', 'z', and 'n_voxels_after_warp'.
    
    """
    centroid = coords.mean(axis=0)
    median = np.median(coords, axis=0)
    first = coords[0]

    row = {
        "voxel_label": int(label),
        "n_voxels_after_warp": int(len(coords)),
    }

    if mode == "centroid_rounded":
        row["voxel_coord_x"] = int(np.rint(centroid[0]))
        row["voxel_coord_y"] = int(np.rint(centroid[1]))
        row["voxel_coord_z"] = int(np.rint(centroid[2]))

    elif mode == "centroid_float":
        row["voxel_coord_x"] = float(centroid[0])
        row["voxel_coord_y"] = float(centroid[1])
        row["voxel_coord_z"] = float(centroid[2])

    elif mode == "median":
        row["voxel_coord_x"] = float(median[0])
        row["voxel_coord_y"] = float(median[1])
        row["voxel_coord_z"] = float(median[2])

    elif mode == "first":
        row["voxel_coord_x"] = int(first[0])
        row["voxel_coord_y"] = int(first[1])
        row["voxel_coord_z"] = int(first[2])

    else:
        raise ValueError(
            f"Invalid mode: {mode}. Must be one of "
            "'centroid_rounded', 'centroid_float', 'median', or 'first'."
        )

    return row

@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    input_path = Path(args.input)
    img = load_3D_img(input_path, verbose=args.verbose)

    coords = np.argwhere(img > 0)
    if coords.size == 0:
        raise ValueError(f"No nonzero voxels found in {input_path}")

    labels = img[coords[:, 0], coords[:, 1], coords[:, 2]].astype(np.int64)
    unique_labels = np.unique(labels)
    unique_labels = unique_labels[unique_labels > 0]

    rows = []
    for label in unique_labels:
        label_coords = coords[labels == label]
        rows.append(summarize_label_coords(label, label_coords, mode=args.mode))

    out_df = pd.DataFrame(rows).sort_values("voxel_label").reset_index(drop=True)

    if args.mapping_csv:
        mapping_df = pd.read_csv(args.mapping_csv)
        if "voxel_label" not in mapping_df.columns:
            raise ValueError(f"Mapping CSV must contain a voxel_label column: {args.mapping_csv}")
        out_df = out_df.merge(mapping_df, on="voxel_label", how="left")

    # Reorder so that the newer coordinates are come after voxel_x/y/z from coords_points_to_labeled_voxel_img, if those columns exist. This makes it easier to compare original vs. new coordinates.
    preferred = [
        "voxel_label",
        "n_voxels_after_warp",
        "voxel_x",
        "voxel_y",
        "voxel_z",
        "voxel_coord_x",
        "voxel_coord_y",
        "voxel_coord_z",
    ]

    ordered = [c for c in preferred if c in out_df.columns]
    remaining = [c for c in out_df.columns if c not in ordered]
    out_df = out_df[ordered + remaining]

    if args.output:
        output_path = Path(args.output)
    else:
        output_path = input_path.with_name(get_stem(input_path) + "_points.csv")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(output_path, index=False)

    print(f"\n    Input image: {input_path}")
    print(f"    Nonzero voxels: {len(coords)}")
    print(f"    Unique labels found: {len(unique_labels)}")
    if args.mapping_csv:
        print(f"    Mapping CSV merged: {args.mapping_csv}")
    print(f"    Output CSV saved to: {output_path}\n")

    verbose_end_msg()


if __name__ == "__main__":
    main()