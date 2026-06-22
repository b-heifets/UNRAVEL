#!/usr/bin/env python3
"""
Use ``gta_zarr_metadata_summary`` (``gta_z``) from UNRAVEL to download and summarize STPT OME-Zarr multiscale metadata for Allen Genetic Tools Atlas.

This script supports both metadata layouts seen in GTA STPT data:
    1) Zarr v2-style root metadata in .zattrs
    2) Zarr v3-style root metadata in zarr.json

It also checks both GTA root layouts used by existing download code:
    - tissuecyte/<exp_id>/ome_zarr_conversion/<exp_id>.zarr
    - tissuecyte/<exp_id>/ome-zarr

Outputs a wide CSV with one row per experiment and columns for voxel size (microns)
at each available multiscale level.

Example columns:
    experiment_id,0_xy,0_z,1_xy,1_z,...,9_xy,9_z,max_level,status,error

Usage:
------
    gta_z [-e <exp_id1> <exp_id2> ...] [-f <file_with_exp_ids>] [-a] [-o <output_csv>] [-w <num_workers>] [--metadata-dir <dir_to_cache_metadata>] [--force] [-v]
"""

import argparse
import json
import pandas as pd
import s3fs
import re
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from rich.traceback import install
from typing import Any

from unravel.core.config import Configuration
from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg



BUCKET = "allen-genetic-tools"
PREFIX = "tissuecyte"
MAX_LEVEL = 9

def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-md', '--metadata', help='path/metadata.txt. Default: parameters/metadata.txt', default="parameters/metadata.txt", action=SM)
    opts.add_argument('-x', '--xy_res', help='xy resolution in um (to manually set if metadata cannot be extracted from image)', type=float, default=None, action=SM)
    opts.add_argument('-z', '--z_res', help='z resolution in um (to manually set if metadata cannot be extracted from image)', type=float, default=None, action=SM)
    opts.add_argument('-c', '--channel', help='Channel number for .czi images. Default: 0', default=0, type=int, action=SM)
    opts.add_argument('-o', '--output', help='Output path. Default: reg_inputs/autofl_50um.nii.gz', default="reg_inputs/autofl_50um.nii.gz", action=SM)
    opts.add_argument('-r', '--reg_res', help='Resample input to this res in um for reg. Default: 50', default=50, type=int, action=SM)
    opts.add_argument('-zo', '--zoom_order', help='Order for resampling (scipy.ndimage.zoom). Default: 1', default=1, type=int, action=SM)

    opts.add_argument('-e', '--exp-ids', help='One or more experiment IDs.', nargs='*', default=[], action=SM)
    opts.add_argument('-f', '--file', help='Text file with one experiment ID per line.', default=None, action=SM)
    opts.add_argument('-a', '--all', action='store_true', help=f'Discover all experiment folders under s3://{BUCKET}/{PREFIX}/', default=False)
    opts.add_argument('-o', '--output', help='Output CSV path. Default: stpt_resolutions_um.csv', default="stpt_resolutions_um.csv", action=SM)
    opts.add_argument('-w', '--workers', help='Number of parallel workers. Default: 20', type=int, default=20, action=SM)
    opts.add_argument('-md', '--metadata-dir', help='Optional directory to save root metadata files used for parsing. Each experiment gets either .zattrs or zarr.json depending on what exists remotely.', default=None, action=SM)
    opts.add_argument('--force', action='store_true', help='Overwrite cached metadata files when --metadata-dir is used.')

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()


def load_exp_ids(args: argparse.Namespace) -> list[str]:
    exp_ids: list[str] = []
    if args.exp_ids:
        exp_ids.extend(str(x).strip() for x in args.exp_ids)
    if args.file:
        with open(args.file, "r", encoding="utf-8") as f:
            exp_ids.extend(line.strip() for line in f if line.strip() and not line.strip().startswith("#"))

    seen: set[str] = set()
    cleaned: list[str] = []
    for exp_id in exp_ids:
        exp_id = str(exp_id).strip()
        if exp_id.isdigit() and exp_id not in seen:
            seen.add(exp_id)
            cleaned.append(exp_id)
    return cleaned


def discover_all_exp_ids(fs: s3fs.S3FileSystem, verbose: bool = False) -> list[str]:
    prefix = f"s3://{BUCKET}/{PREFIX}"
    entries = fs.ls(prefix, detail=False)
    exp_ids: list[str] = []
    for entry in entries:
        name = Path(entry).name.rstrip("/")
        if re.fullmatch(r"\d{9,}", name):
            exp_ids.append(name)
    exp_ids = sorted(set(exp_ids), key=int)
    if verbose:
        print(f"Discovered {len(exp_ids)} experiment folders under {prefix}")
    return exp_ids


def root_candidates(exp_id: str) -> list[str]:
    return [
        f"s3://{BUCKET}/{PREFIX}/{exp_id}/ome_zarr_conversion/{exp_id}.zarr",
        f"s3://{BUCKET}/{PREFIX}/{exp_id}/ome-zarr",
    ]


def metadata_candidates(exp_id: str) -> list[tuple[str, str]]:
    candidates: list[tuple[str, str]] = []
    for root in root_candidates(exp_id):
        candidates.append((f"{root}/.zattrs", ".zattrs"))
        candidates.append((f"{root}/zarr.json", "zarr.json"))
    return candidates


def cache_path(cache_dir: Path, exp_id: str, metadata_name: str) -> Path:
    return cache_dir / exp_id / metadata_name


def read_cached_metadata(exp_id: str, cache_dir: Path) -> tuple[str, str] | None:
    for metadata_name in (".zattrs", "zarr.json"):
        local_path = cache_path(cache_dir, exp_id, metadata_name)
        if local_path.exists():
            return local_path.read_text(encoding="utf-8"), metadata_name
    return None


def fetch_root_metadata_text(
    exp_id: str,
    fs: s3fs.S3FileSystem,
    save_metadata_dir: Path | None = None,
    force: bool = False,
) -> tuple[str, str, str]:
    if save_metadata_dir is not None and not force:
        cached = read_cached_metadata(exp_id, save_metadata_dir)
        if cached is not None:
            text, metadata_name = cached
            return text, metadata_name, f"cache://{exp_id}/{metadata_name}"

    tried_paths: list[str] = []
    for remote_path, metadata_name in metadata_candidates(exp_id):
        tried_paths.append(remote_path)
        if not fs.exists(remote_path):
            continue

        with fs.open(remote_path, "r") as f:
            text = f.read()

        if save_metadata_dir is not None:
            local_path = cache_path(save_metadata_dir, exp_id, metadata_name)
            local_path.parent.mkdir(parents=True, exist_ok=True)
            local_path.write_text(text, encoding="utf-8")

        return text, metadata_name, remote_path

    tried_str = " | ".join(tried_paths)
    raise FileNotFoundError(f"Missing root metadata (.zattrs or zarr.json): {tried_str}")


def _axis_units_to_um(value: float | int | None, unit: str | None) -> float | None:
    if value is None:
        return None
    if unit is None:
        return float(value)

    unit_normalized = unit.strip().lower()
    if unit_normalized in {"micrometer", "micrometers", "micron", "microns", "µm", "um"}:
        return float(value)
    if unit_normalized in {"millimeter", "millimeters", "mm"}:
        return float(value) * 1000.0
    if unit_normalized in {"meter", "meters", "m"}:
        return float(value) * 1_000_000.0
    if unit_normalized in {"nanometer", "nanometers", "nm"}:
        return float(value) / 1000.0
    return float(value)


def _empty_row(exp_id: str) -> dict[str, Any]:
    row: dict[str, Any] = {"experiment_id": exp_id}
    for level in range(MAX_LEVEL + 1):
        row[f"{level}_xy"] = None
        row[f"{level}_z"] = None
    row["max_level"] = None
    return row


def _extract_multiscales_container(parsed: dict[str, Any], metadata_name: str) -> dict[str, Any]:
    """
    Normalize root metadata layouts.

    Supported cases:
      - .zattrs: multiscales at top level
      - zarr.json v3 / OME-NGFF 0.5: attributes -> ome -> multiscales
      - zarr.json older-style variants: attributes -> multiscales OR top-level multiscales
    """
    if metadata_name == ".zattrs":
        return parsed

    if metadata_name != "zarr.json":
        return parsed

    # Most correct v3 / OME-Zarr 0.5 location
    attributes = parsed.get("attributes")
    if isinstance(attributes, dict):
        ome = attributes.get("ome")
        if isinstance(ome, dict) and "multiscales" in ome:
            return ome
        if "multiscales" in attributes:
            return attributes

    if "ome" in parsed and isinstance(parsed["ome"], dict) and "multiscales" in parsed["ome"]:
        return parsed["ome"]

    return parsed


def parse_root_metadata(exp_id: str, metadata_text: str, metadata_name: str) -> dict[str, Any]:
    parsed = json.loads(metadata_text)
    container = _extract_multiscales_container(parsed, metadata_name)

    row = _empty_row(exp_id)

    multiscales = container.get("multiscales", [])
    if not multiscales:
        raise ValueError(f"No 'multiscales' found in root {metadata_name}")

    multiscale = multiscales[0]
    axes = multiscale.get("axes", [])
    datasets = multiscale.get("datasets", [])
    if not datasets:
        raise ValueError(f"No datasets found under multiscales[0] in {metadata_name}")

    axis_names = [axis.get("name") for axis in axes]
    axis_units = {axis.get("name"): axis.get("unit") for axis in axes}

    available_levels: list[int] = []

    for dataset in datasets:
        path = str(dataset.get("path", "")).strip()
        if not path.isdigit():
            continue

        level = int(path)
        if level < 0 or level > MAX_LEVEL:
            continue

        scale_transform = None
        for transform in dataset.get("coordinateTransformations", []):
            if transform.get("type") == "scale":
                scale_transform = transform
                break
        if scale_transform is None:
            continue

        scale_values = scale_transform.get("scale", [])
        if len(scale_values) != len(axis_names):
            continue

        scale_by_axis = dict(zip(axis_names, scale_values))
        x_um = _axis_units_to_um(scale_by_axis.get("x"), axis_units.get("x"))
        y_um = _axis_units_to_um(scale_by_axis.get("y"), axis_units.get("y"))
        z_um = _axis_units_to_um(scale_by_axis.get("z"), axis_units.get("z"))

        xy_um = None
        if x_um is not None and y_um is not None:
            xy_um = (float(x_um) + float(y_um)) / 2.0
        elif x_um is not None:
            xy_um = float(x_um)
        elif y_um is not None:
            xy_um = float(y_um)

        row[f"{level}_xy"] = xy_um
        row[f"{level}_z"] = z_um
        available_levels.append(level)

    if available_levels:
        row["max_level"] = max(available_levels)

    return row


def process_experiment(
    exp_id: str,
    fs: s3fs.S3FileSystem,
    save_metadata_dir: Path | None = None,
    force: bool = False,
) -> dict[str, Any]:
    try:
        metadata_text, metadata_name, remote_path = fetch_root_metadata_text(
            exp_id=exp_id,
            fs=fs,
            save_metadata_dir=save_metadata_dir,
            force=force,
        )
        row = parse_root_metadata(exp_id, metadata_text, metadata_name)
        row["status"] = "ok"
        row["error"] = None
        row["metadata_source"] = metadata_name
        row["metadata_path"] = remote_path
        return row
    except Exception as e:
        row = _empty_row(exp_id)
        row["status"] = "error"
        row["error"] = str(e)
        row["metadata_source"] = None
        row["metadata_path"] = None
        return row


def build_column_order() -> list[str]:
    columns = ["experiment_id"]
    for level in range(MAX_LEVEL + 1):
        columns.extend([f"{level}_xy", f"{level}_z"])
    columns.extend(["max_level", "status", "error", "metadata_source", "metadata_path"])
    return columns


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    save_metadata_dir = Path(args.save_metadata_dir) if args.save_metadata_dir else None
    if save_metadata_dir is not None:
        save_metadata_dir.mkdir(parents=True, exist_ok=True)

    fs = s3fs.S3FileSystem(anon=True)

    exp_ids = load_exp_ids(args)
    if args.all:
        discovered = discover_all_exp_ids(fs, verbose=args.verbose)
        seen = set(exp_ids)
        exp_ids.extend([eid for eid in discovered if eid not in seen])

    exp_ids = sorted(set(exp_ids), key=int)

    if not exp_ids:
        raise SystemExit("No experiment IDs provided. Use -e, -f, or --all.")

    if args.verbose:
        print(f"Processing {len(exp_ids)} experiment(s)...")

    rows: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(
                process_experiment,
                exp_id,
                fs,
                save_metadata_dir,
                args.force,
            ): exp_id
            for exp_id in exp_ids
        }
        for future in as_completed(futures):
            row = future.result()
            rows.append(row)
            if args.verbose:
                print(
                    f"[{row['experiment_id']}] {row['status']}"
                    + (f" ({row['metadata_source']})" if row.get("metadata_source") else "")
                )

    df = pd.DataFrame(rows)
    column_order = build_column_order()
    for col in column_order:
        if col not in df.columns:
            df[col] = None

    df = df[column_order].sort_values(
        "experiment_id",
        key=lambda s: s.astype(str).astype(int)
    ).reset_index(drop=True)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)

    n_ok = int((df["status"] == "ok").sum())
    n_err = int((df["status"] == "error").sum())
    print(f"Saved {output_path}")
    print(f"Experiments processed: {len(df)} | ok: {n_ok} | error: {n_err}")

    verbose_end_msg()

if __name__ == "__main__":
    main()
