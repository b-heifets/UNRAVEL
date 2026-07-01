#!/usr/bin/env python3

"""
Use ``cstats_mean_IF`` (``cmi``) from UNRAVEL to measure mean intensity of immunofluorescence staining in clusters.

By default, this measures mean IF intensity in each cluster.

If an atlas is provided with ``--atlas/-a``, this measures mean IF intensity in each
atlas region within each cluster.

Prereqs:
    - ``vstats``
    - ``cstats_fdr`` or ``cstats_clusters`` to generate a rev_cluster_index.nii.gz

Inputs:
    - Cluster index image from ``cstats_fdr`` or ``cstats_clusters``
    - NIfTI images to measure
    - Optional atlas image in the same space/resolution as the cluster index

Outputs:
    - Cluster-only mode:
        ./cluster_mean_IF_<cluster_index>/image_name.csv
        Columns: condition, sample, cluster_ID, n_voxels, mean_intensity

    - Cluster-region mode:
        ./cluster_region_mean_IF_<cluster_index>/image_name.csv
        Columns: condition, sample, cluster_ID, region_ID, region, abbr, n_voxels, mean_intensity

Next steps:
    - cd cluster_mean_IF... or cluster_region_mean_IF...
    - Concatenate outputs:
        tabular_concat -i '*.csv' -a 0 -o concat/concat.csv -v
    - Summarize:
        cstats_mean_IF_summary --order Control Treatment --labels Control Treatment -t ttest

Usage:
------
    cstats_mean_IF -i path/rev_cluster_index.nii.gz [-ip '*.nii.gz'] [-c 1 2 3] [-v]

Usage for region means within clusters:
---------------------------------------
    cstats_mean_IF -i path/rev_cluster_index.nii.gz -a path/atlas.nii.gz [-ip '*.nii.gz'] [-c 1 2 3] [-r 10 20 30] [--min_voxels 5] [-v]
"""

import csv
import nibabel as nib
import numpy as np
import pandas as pd
from pathlib import Path
from rich.traceback import install

from unravel.core.config import Configuration
from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.img_io import load_3D_img
from unravel.core.utils import log_command, match_files, verbose_start_msg, verbose_end_msg


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument(
        '-i', '--input',
        help='Path/rev_cluster_index.nii.gz from ``cstats_fdr`` or ``cstats_clusters``',
        required=True,
        action=SM,
    )

    opts = parser.add_argument_group('Optional args')
    opts.add_argument(
        '-ip', '--input_pattern',
        help="Glob pattern(s) for NIfTI images to process. Default: '*.nii.gz'",
        default='*.nii.gz',
        nargs='*',
        action=SM,
    )
    opts.add_argument(
        '-a', '--atlas',
        help='Optional atlas image. If provided, measure mean IF in each region within each cluster.',
        action=SM,
    )
    opts.add_argument(
        '-c', '--clusters',
        help='Space-separated list of cluster IDs to process. Default: all clusters',
        nargs='*',
        type=int,
        action=SM,
    )
    opts.add_argument(
        '-r', '--regions',
        help='Space-separated list of region IDs to process when --atlas is provided. Default: all regions within clusters',
        nargs='*',
        type=int,
        action=SM,
    )
    opts.add_argument(
        '--min_voxels',
        help='Minimum voxels required for a cluster or cluster-region pair. Default: 1',
        type=int,
        default=1,
        action=SM,
    )
    opts.add_argument(
        '-l', '--lut',
        help='Optional region LUT CSV path or CSV name in unravel/core/csvs/. Expected columns: Region_ID, Region, Abbr. Default: CCFv3-2020__regionID_side_IDpath_region_abbr.csv',
        default='CCFv3-2020__regionID_side_IDpath_region_abbr.csv',
        action=SM,
    )
    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity', action='store_true', default=False)

    return parser.parse_args()


def _has_values(values):
    """Return True when an optional nargs list has at least one value."""
    return values is not None and len(values) > 0


def build_label_index(cluster_index, atlas=None, clusters=None, regions=None, min_voxels=1):
    """
    Precompute voxel membership for cluster-only or cluster-region mean IF.

    Cluster-only mode:
        key = cluster_ID

    Cluster-region mode:
        key = cluster_ID * key_base + region_ID
    """

    if min_voxels < 1:
        raise ValueError("--min_voxels must be >= 1")

    if atlas is None:
        valid_mask = cluster_index > 0

        if _has_values(clusters):
            clusters = np.asarray(clusters, dtype=cluster_index.dtype)
            valid_mask &= np.isin(cluster_index, clusters)

        keys = cluster_index[valid_mask].astype(np.int64, copy=False)
        key_base = None

    else:
        valid_mask = (cluster_index > 0) & (atlas > 0)

        if _has_values(clusters):
            clusters = np.asarray(clusters, dtype=cluster_index.dtype)
            valid_mask &= np.isin(cluster_index, clusters)

        if _has_values(regions):
            regions = np.asarray(regions, dtype=atlas.dtype)
            valid_mask &= np.isin(atlas, regions)

        cluster_vals = cluster_index[valid_mask].astype(np.int64, copy=False)
        region_vals = atlas[valid_mask].astype(np.int64, copy=False)

        if cluster_vals.size == 0:
            raise ValueError("No valid cluster-region voxels found.")

        key_base = int(region_vals.max()) + 1
        keys = cluster_vals * key_base + region_vals

    if keys.size == 0:
        raise ValueError("No valid cluster voxels found.")

    counts = np.bincount(keys)
    keep = counts >= min_voxels
    keep[0] = False

    return valid_mask, keys, counts, keep, key_base


def calculate_mean_intensity(img, valid_mask, keys, counts, keep, key_base=None):
    """Calculate mean IF intensity for precomputed cluster or cluster-region labels."""

    img_vals = img[valid_mask].ravel()
    sums = np.bincount(keys, weights=img_vals, minlength=len(counts))

    rows = []
    for key in np.flatnonzero(keep):
        n_voxels = int(counts[key])
        mean_intensity = float(sums[key] / n_voxels)

        if key_base is None:
            rows.append({
                "cluster_ID": int(key),
                "n_voxels": n_voxels,
                "mean_intensity": mean_intensity,
            })
        else:
            rows.append({
                "cluster_ID": int(key // key_base),
                "region_ID": int(key % key_base),
                "n_voxels": n_voxels,
                "mean_intensity": mean_intensity,
            })

    return rows


def write_rows_to_csv(rows, output_file, condition, sample):
    """Write mean intensity rows to CSV with a stable column order."""

    if not rows:
        return

    has_regions = "region_ID" in rows[0]

    if has_regions:
        fieldnames = [
            "condition",
            "sample",
            "cluster_ID",
            "region_ID",
            "region",
            "abbr",
            "n_voxels",
            "mean_intensity",
        ]
    else:
        fieldnames = [
            "condition",
            "sample",
            "cluster_ID",
            "n_voxels",
            "mean_intensity",
        ]

    with open(output_file, "w", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        for row in rows:
            writer.writerow({
                "condition": condition,
                "sample": sample,
                **row,
            })


def condition_sample_from_filename(file):
    """
    Extract condition and sample from filename.

    Expected after utils_prepend-style naming:
        Condition_sampleXX_....

    Falls back gracefully if the filename does not contain both fields.
    """

    stem = Path(file).name.replace(".nii.gz", "").replace(".nii", "")
    parts = stem.split("_")

    if len(parts) >= 2:
        return parts[0], parts[1]

    return "", stem


def add_region_metadata(rows, region_lut):
    """Add region and abbr columns to cluster-region rows."""
    if not rows or "region_ID" not in rows[0]:
        return rows

    for row in rows:
        info = region_lut.get(int(row["region_ID"]), {})
        row["region"] = info.get("region", "")
        row["abbr"] = info.get("abbr", "")

    return rows


def resolve_lut_path(lut):
    """Resolve LUT path from explicit path or unravel/core/csvs/."""
    if lut is None:
        return None

    lut_path = Path(lut)
    if lut_path.exists():
        return lut_path

    core_lut = Path(__file__).parent.parent / 'core' / 'csvs' / lut
    if core_lut.exists():
        return core_lut

    raise FileNotFoundError(f"Could not find LUT CSV: {lut}")


def load_region_lut(lut):
    """Load region LUT as a dictionary keyed by Region_ID."""

    lut_path = resolve_lut_path(lut)

    if lut_path is None:
        return {}

    df = pd.read_csv(lut_path)

    if "Region_ID" not in df.columns:
        raise KeyError("LUT must contain a Region_ID column.")

    if "Region" not in df.columns and "Name" in df.columns:
        df = df.rename(columns={"Name": "Region"})

    for col in ["Region", "Abbr"]:
        if col not in df.columns:
            df[col] = ""

    df = df[["Region_ID", "Region", "Abbr"]].drop_duplicates(subset=["Region_ID"])

    return {
        int(row["Region_ID"]): {
            "region": row["Region"],
            "abbr": row["Abbr"],
        }
        for _, row in df.iterrows()
    }


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    cluster_index_img = load_3D_img(args.input, verbose=args.verbose)

    if not np.issubdtype(cluster_index_img.dtype, np.integer):
        raise ValueError("The cluster index must be an integer image.")

    atlas_img = None
    if args.atlas:
        atlas_img = load_3D_img(args.atlas, verbose=args.verbose)

        if not np.issubdtype(atlas_img.dtype, np.integer):
            raise ValueError("The atlas must be an integer label image.")

        if cluster_index_img.shape != atlas_img.shape:
            raise ValueError("Cluster index and atlas must have the same shape.")
        
    region_lut = load_region_lut(args.lut) if args.atlas else {}

    label_index = build_label_index(
        cluster_index_img,
        atlas=atlas_img,
        clusters=args.clusters,
        regions=args.regions,
        min_voxels=args.min_voxels,
    )

    mode = "cluster_region_mean_IF" if args.atlas else "cluster_mean_IF"
    input_name = str(Path(args.input).name).replace(".nii.gz", "")
    output_folder = Path(f"{mode}_{input_name}")
    output_folder.mkdir(parents=True, exist_ok=True)

    valid_mask, keys, counts, keep, key_base = label_index

    if args.verbose:
        n_labels = int(np.count_nonzero(keep))
        if args.atlas:
            print(f"\nProcessing {n_labels} cluster-region pairs.\n")
        else:
            print(f"\nProcessing {n_labels} clusters.\n")

    files = match_files(args.input_pattern)

    for file in files:
        if not str(file).endswith(".nii.gz"):
            continue

        nii = nib.load(file)
        img = np.asanyarray(nii.dataobj, dtype=nii.header.get_data_dtype()).squeeze()

        if img.shape != cluster_index_img.shape:
            raise ValueError(f"{file} does not have the same shape as the cluster index.")

        rows = calculate_mean_intensity(
            img,
            valid_mask,
            keys,
            counts,
            keep,
            key_base=key_base,
        )

        output_filename = str(file.name).replace(".nii.gz", ".csv")
        output = output_folder / output_filename

        if args.atlas:
            rows = add_region_metadata(rows, region_lut)

        condition, sample = condition_sample_from_filename(file)
        write_rows_to_csv(rows, output, condition, sample)

    if args.atlas:
        print(f"CSVs with cluster-region mean IF intensities output to ./{output_folder}/")
    else:
        print(f"CSVs with cluster mean IF intensities output to ./{output_folder}/")

    verbose_end_msg()


if __name__ == "__main__":
    main()