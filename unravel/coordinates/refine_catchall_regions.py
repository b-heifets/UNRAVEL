#!/usr/bin/env python3

"""
Use ``coords_refine_catchall_regions`` or ``refine_catchall`` from UNRAVEL to refine catch-all atlas labels for points/units/channels using nearby descendant regions.

This script is intended to run after ``coords_physical_points_add_regions``. It keeps
the original atlas lookup columns and adds refined region columns.

For points assigned to broad/catch-all regions, e.g. STR, TH, HY, MB, etc., the script:
    1. Finds descendants of the catch-all region using structure_id_path.
    2. Converts descendant structure_IDs to lowered_IDs.
    3. Searches outward from the point voxel until a valid descendant atlas ID is found.
    4. Assigns the nearest descendant ID.
    5. If multiple descendant IDs are found at the same nearest distance, uses the mode.

Input:
    - CSV with voxel coordinate columns, e.g. x, y, z
    - Region metadata columns from ``coords_physical_points_add_regions``
    - Atlas image in the same array orientation as the voxel coordinates
    - Region info CSV, e.g. CCFv3-2020_info.csv

Output:
    - CSV with original metadata plus:
        refined_lowered_ID
        refined_abbreviation
        refined_region_name
        refined_structure_ID
        refined_structure_id_path
        refinement_status
        refinement_radius_vox
        refinement_distance_vox
        refinement_distance_um

Note:
    - This script assumes the atlas values are lowered_IDs.
    - structure_id_path contains structure_IDs, not lowered_IDs.
    - Descendants are identified using structure_ID in structure_id_path,
      then converted back to lowered_IDs for atlas lookup.
    - The original direct atlas lookup columns are preserved.

Usage:
------
    coords_refine_catchall_regions \\
        -i ISOTRP_all_recordings_units_CCFcoordinates__w_CCFv3-2020_regions.csv \\
        -a atlas_CCFv3_2020_25um_LIP_applied.nii.gz \\
        -rc CCFv3-2020_info.csv \\
        -s 25 \\
        -o ISOTRP_all_recordings_units_CCFcoordinates__w_refined_regions.csv
"""

from pathlib import Path

import numpy as np
import pandas as pd
from rich import print
from rich.traceback import install

from unravel.core.config import Configuration
from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.img_io import load_3D_img
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg
from unravel.coordinates.physical_points_to_img import parse_spacing, validate_columns

DEFAULT_CATCHALL_ABBRS = ["CB", "CTXsp", "fiber tracts", "HPF", "HY", "MB", "MOB", "MY", "OLF", "PAL", "P", "STR", "TH"]


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group("Required arguments")
    reqs.add_argument("-i", "--input", help="Input CSV from ``coords_physical_points_add_regions``.", required=True, action=SM)
    reqs.add_argument("-a", "--atlas", help="Atlas image matching x/y/z voxel coordinate space.", required=True, action=SM)

    coord_args = parser.add_argument_group("Coordinate arguments")
    coord_args.add_argument("-x", "--x_col", help="Voxel coordinate column for atlas axis 0. Default: x", default="x", action=SM)
    coord_args.add_argument("-y", "--y_col", help="Voxel coordinate column for atlas axis 1. Default: y", default="y", action=SM)
    coord_args.add_argument("-z", "--z_col", help="Voxel coordinate column for atlas axis 2. Default: z", default="z", action=SM)
    coord_args.add_argument("-s", "--spacing", help="Voxel spacing in physical units. Default: 25", default=[25], nargs="*", type=float, action=SM)

    region_args = parser.add_argument_group("Region info CSV arguments")
    region_args.add_argument("-rc", "--region_csv", help="CSV name or path/name.csv. Default: CCFv3-2020_info.csv", default="CCFv3-2020_info.csv", action=SM)
    region_args.add_argument("-id", "--region_id_col", help="Atlas ID column used in the atlas image. Default: lowered_ID", default="lowered_ID", action=SM)
    region_args.add_argument("-sid", "--structure_id_col", help="Structure ID column used in structure_id_path. Default: structure_ID", default="structure_ID", action=SM)
    region_args.add_argument("-path", "--structure_id_path_col", help="Structure ID path column. Default: structure_id_path", default="structure_id_path", action=SM)
    region_args.add_argument("-abbr", "--abbr_col", help="Abbreviation column. Default: abbreviation", default="abbreviation", action=SM)
    region_args.add_argument("-name", "--name_col", help="Region name column. Default: full_structure_name", default="full_structure_name", action=SM)

    refine_args = parser.add_argument_group("Refinement arguments")
    refine_args.add_argument("--catchall", help="Catch-all region abbreviations to refine.", default=DEFAULT_CATCHALL_ABBRS, nargs="*", action=SM)
    refine_args.add_argument("-r", "--max_radius", help="Maximum outward search radius in voxels. Default: 20", default=20, type=int, action=SM)

    opts = parser.add_argument_group("Optional arguments")
    opts.add_argument("-o", "--output", help="Output CSV path. Default: input stem + _refined.csv", default=None, action=SM)
    opts.add_argument("-f", "--filter", help="Optional pandas query string.", default=None, action=SM)

    general = parser.add_argument_group("General arguments")
    general.add_argument("-v", "--verbose", help="Increase verbosity. Default: False", action="store_true", default=False)

    return parser.parse_args()


def load_region_info(args):
    """Load required region info columns."""
    columns_to_load = [
        args.region_id_col,
        args.structure_id_col,
        args.structure_id_path_col,
        args.abbr_col,
        args.name_col,
    ]

    if args.region_csv in ["CCFv3-2017_info.csv", "CCFv3-2020_info.csv"]:
        region_csv_path = Path(__file__).parent.parent.parent / "unravel" / "core" / "csvs" / args.region_csv
    else:
        region_csv_path = Path(args.region_csv)

    region_info_df = pd.read_csv(region_csv_path, usecols=columns_to_load)
    region_info_df = region_info_df.dropna(subset=[args.region_id_col, args.structure_id_col])

    region_info_df[args.region_id_col] = region_info_df[args.region_id_col].astype(np.int64)
    region_info_df[args.structure_id_col] = region_info_df[args.structure_id_col].astype(np.int64)

    return region_info_df


def parse_id_path(path):
    """Parse Allen-style structure_id_path into a list of integer structure_IDs."""
    if pd.isna(path):
        return []

    path_str = str(path).strip()

    # Handles formats like "/997/8/567/" or "[997, 8, 567]"
    for char in ["[", "]"]:
        path_str = path_str.replace(char, "")
    path_str = path_str.replace(",", "/")
    parts = [p for p in path_str.strip("/").split("/") if p.strip()]

    ids = []
    for p in parts:
        try:
            ids.append(int(float(p)))
        except ValueError:
            continue

    return ids


def build_region_lookup(region_info_df, args):
    """Build dictionaries for lowered_ID/structure_ID/abbr/name lookups."""
    by_lowered = region_info_df.set_index(args.region_id_col).to_dict(orient="index")

    abbr_to_rows = {}
    for _, row in region_info_df.iterrows():
        abbr = row[args.abbr_col]
        if pd.isna(abbr):
            continue
        abbr_to_rows.setdefault(str(abbr), []).append(row)

    return by_lowered, abbr_to_rows


def get_descendant_lowered_ids(region_info_df, catchall_structure_id, catchall_lowered_id, args):
    """Return lowered_IDs whose structure_id_path contains catchall_structure_id."""
    valid_ids = set()

    for _, row in region_info_df.iterrows():
        path_ids = parse_id_path(row[args.structure_id_path_col])
        if catchall_structure_id in path_ids:
            lowered_id = row[args.region_id_col]
            if pd.notna(lowered_id):
                valid_ids.add(int(lowered_id))

    valid_ids.discard(0)
    valid_ids.discard(int(catchall_lowered_id))

    return valid_ids


def choose_catchall_row(catchall_abbr, abbr_to_rows, args):
    """Choose the row corresponding to a catch-all abbreviation."""
    rows = abbr_to_rows.get(str(catchall_abbr), [])
    if not rows:
        return None

    # Prefer the row whose abbreviation exactly matches and is broad.
    # If duplicates exist, the first is usually fine for CCF info CSVs.
    return rows[0]


def build_catchall_candidate_map(region_info_df, args):
    """Map catch-all abbreviation to valid descendant lowered_ID candidates."""
    _, abbr_to_rows = build_region_lookup(region_info_df, args)
    catchall_map = {}

    for catchall_abbr in args.catchall:
        catchall_row = choose_catchall_row(catchall_abbr, abbr_to_rows, args)
        if catchall_row is None:
            continue

        catchall_lowered_id = int(catchall_row[args.region_id_col])
        catchall_structure_id = int(catchall_row[args.structure_id_col])

        valid_ids = get_descendant_lowered_ids(
            region_info_df,
            catchall_structure_id=catchall_structure_id,
            catchall_lowered_id=catchall_lowered_id,
            args=args,
        )

        catchall_map[str(catchall_abbr)] = {
            "catchall_lowered_ID": catchall_lowered_id,
            "catchall_structure_ID": catchall_structure_id,
            "valid_lowered_IDs": valid_ids,
        }

    return catchall_map


def nearest_descendant_region_id(atlas_img, coord, valid_ids, max_radius=10):
    """Search outward from coord and return nearest valid atlas ID."""
    x, y, z = map(int, coord)
    shape = atlas_img.shape
    valid_ids = list(valid_ids)

    if len(valid_ids) == 0:
        return 0, 0, np.nan, "missing_descendants"

    for r in range(1, max_radius + 1):
        # Define the search cube boundaries, ensuring they stay within the image bounds
        x0, x1 = max(0, x - r), min(shape[0], x + r + 1)
        y0, y1 = max(0, y - r), min(shape[1], y + r + 1)
        z0, z1 = max(0, z - r), min(shape[2], z + r + 1)

        # Extract the sub-volume and find valid descendant IDs
        sub = atlas_img[x0:x1, y0:y1, z0:z1]
        mask = np.isin(sub, valid_ids)

        if not mask.any():
            continue

        # Get the coordinates of the valid descendant IDs within the search cube
        local_coords = np.argwhere(mask)
        global_coords = local_coords + np.array([x0, y0, z0])

        # Calculate distances from the original coordinate to the valid descendant coordinates
        distances = np.linalg.norm(global_coords - np.array([x, y, z]), axis=1)

        # Keep only coordinates within the current radius (spherical search)
        sphere_mask = distances <= r
        local_coords = local_coords[sphere_mask]
        global_coords = global_coords[sphere_mask]
        distances = distances[sphere_mask]

        if len(distances) == 0:
            continue

        # Find the nearest valid descendant ID(s) and choose the most common if there's a tie
        min_dist = distances.min()
        nearest_local = local_coords[distances == min_dist]
        nearest_ids = sub[
            nearest_local[:, 0],
            nearest_local[:, 1],
            nearest_local[:, 2],
        ].astype(np.int64)

        # If multiple nearest IDs, choose the mode (most common ID among the nearest)
        values, counts = np.unique(nearest_ids, return_counts=True)
        chosen_id = int(values[np.argmax(counts)])

        return chosen_id, r, float(min_dist), "refined"

    return 0, max_radius, np.nan, "no_descendant_found"


def add_region_metadata_for_refined_ids(out_df, region_info_df, args):
    """Merge metadata for refined lowered_IDs."""
    cols = [
        args.region_id_col,
        args.structure_id_col,
        args.structure_id_path_col,
        args.abbr_col,
        args.name_col,
    ]

    meta = region_info_df[cols].copy()
    meta = meta.rename(
        columns={
            args.region_id_col: "refined_lowered_ID",
            args.structure_id_col: "refined_structure_ID",
            args.structure_id_path_col: "refined_structure_id_path",
            args.abbr_col: "refined_abbreviation",
            args.name_col: "refined_region_name",
        }
    )

    return out_df.merge(meta, on="refined_lowered_ID", how="left")


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    input_path = Path(args.input)
    atlas_path = Path(args.atlas)
    spacing = parse_spacing(args.spacing)

    points_df = pd.read_csv(input_path)

    if args.filter:
        if args.verbose:
            print(f"\n[blue]Filtering rows using filter:[/] {args.filter}")
            print(f"    Original rows: {len(points_df)}")
        points_df = points_df.query(args.filter).copy()
        if args.verbose:
            print(f"    Remaining rows: {len(points_df)}\n")

    validate_columns(points_df, [
        args.x_col,
        args.y_col,
        args.z_col,
        args.region_id_col,
        args.abbr_col
    ])

    atlas_img = load_3D_img(atlas_path, verbose=args.verbose)
    region_info_df = load_region_info(args)
    by_lowered, _ = build_region_lookup(region_info_df, args)
    catchall_map = build_catchall_candidate_map(region_info_df, args)

    out_df = points_df.copy()

    out_df["refined_lowered_ID"] = out_df[args.region_id_col].fillna(0).astype(np.int64)
    out_df["refinement_status"] = "not_catchall"
    out_df["refinement_radius_vox"] = 0
    out_df["refinement_distance_vox"] = 0.0
    out_df["refinement_distance_um"] = 0.0

    n_refined = 0
    n_missing_descendants = 0
    n_no_descendant_found = 0
    n_catchall = 0

    for idx, row in out_df.iterrows():
        abbr = str(row[args.abbr_col])

        if abbr not in catchall_map:
            continue

        n_catchall += 1
        valid_ids = catchall_map[abbr]["valid_lowered_IDs"]

        coord = np.array([row[args.x_col], row[args.y_col], row[args.z_col]], dtype=int)

        refined_id, radius, dist_vox, status = nearest_descendant_region_id(
            atlas_img,
            coord=coord,
            valid_ids=valid_ids,
            max_radius=args.max_radius,
        )

        out_df.at[idx, "refinement_status"] = status
        out_df.at[idx, "refinement_radius_vox"] = radius
        out_df.at[idx, "refinement_distance_vox"] = dist_vox
        out_df.at[idx, "refinement_distance_um"] = dist_vox * float(spacing[0]) if np.isfinite(dist_vox) else np.nan

        if status == "refined":
            out_df.at[idx, "refined_lowered_ID"] = refined_id
            n_refined += 1
        elif status == "missing_descendants":
            n_missing_descendants += 1
        elif status == "no_descendant_found":
            n_no_descendant_found += 1

    out_df["refined_lowered_ID"] = out_df["refined_lowered_ID"].astype(np.int64)
    out_df = add_region_metadata_for_refined_ids(out_df, region_info_df, args)

    if args.output:
        output_path = Path(args.output)
    else:
        output_path = input_path.with_name(input_path.stem + "_refined.csv")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(output_path, index=False)

    print(f"\n    Input rows: {len(points_df)}")
    print(f"    Catch-all rows: {n_catchall}")
    print(f"    Refined rows: {n_refined}")
    print(f"    Missing descendant rows: {n_missing_descendants}")
    print(f"    No descendant found rows: {n_no_descendant_found}")
    print(f"    Max radius: {args.max_radius} voxels")
    print(f"    Output CSV saved to: {output_path}\n")

    verbose_end_msg()


if __name__ == "__main__":
    main()