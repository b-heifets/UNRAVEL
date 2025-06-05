#!/usr/bin/env python3

"""
Use ``gta_download_STPT_zarr`` (``gta_dl``) from UNRAVEL to download STPT Zarr images from the Allen Genetic Tools Atlas (GTA).

Prereqs:
    - Optional: Use ``gta_find_STPT_brains`` to search for STPT brains of interest and generate a CSV file with S3 paths.

Usage given a list of experiment IDs:
-------------------------------------
    gta_dl -e <exp_id1> <exp_id2> ... -l <level> -o <output_dir> [-w <workers>]

Usage given a CSV file with S3 paths:
-------------------------------------
    gta_dl -c <path_to_csv> -l <level> -o <output_dir> [-pc <path_column>] [-w <workers>]
"""

import re
import s3fs
from pathlib import Path
from rich import print
from rich.live import Live
from rich.traceback import install
from concurrent.futures import ThreadPoolExecutor, as_completed

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.config import Configuration
from unravel.core.utils import initialize_progress_bar, log_command, verbose_start_msg, verbose_end_msg

def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-e', '--exp_ids', help='GTA experiment ID to download (e.g., 1342775164)', nargs='*', action=SM)
    opts.add_argument('-l', '--level', help='path/metadata.txt. Default: parameters/metadata.txt', default="parameters/metadata.txt", action=SM)
    opts.add_argument('-o', '--output', help='Output directory. Default: GTA_STPT_level_<level>', default=None, action=SM)
    opts.add_argument('-c', '--csv', help='Path to a CSV file with experiment IDs. If provided, will read IDs from this file instead of command line.', default=None, action=SM)
    opts.add_argument('-col', '--column', help='CSV column name w/ either the "Image Series ID" or Zarr s3 paths. Default: "File URI"', default="File URI", action=SM)
    opts.add_argument('-w', '--workers', help='Number of parallel downloads', type=int, default=10, action=SM)
    opts.add_argument('-f', '--force', help='Force download even if the zarr file already exists. Default: False', action='store_true', default=False)
    opts.add_argument('--full', help='Download the full Zarr root instead of a specific level. ⚠️ This can be >200 GB per brain!', action='store_true', default=False)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()

def get_s3_paths_from_csv(csv_path, path_column):
    """
    Read S3 paths from a CSV file.

    Parameters
    ----------
    csv_path : str
        Path to the CSV file containing S3 paths.
    path_column : str
        Column name in the CSV file that contains the S3 paths.

    Returns
    -------
    list of str
        List of S3 paths.
    """
    import pandas as pd
    df = pd.read_csv(csv_path)
    if path_column not in df.columns:
        raise ValueError(f"Column '{path_column}' not found in the CSV file.")
    path_list = df[path_column].dropna().tolist()
    path_list = [str(path).rstrip('/') for path in path_list] # Remove trailing slashes
    return path_list

def extract_exp_id(s3_path):
    # if there are slashes in the path, extract the first occurrence of 9 or more digits
    if s3_path.startswith('s3://'):
        match = re.search(r'/(\d{9,})/', s3_path)  # Match 9 or more digits between slashes
    else:
        match = re.search(r'(\d{9,})', s3_path)  # Match 9 or more digits anywhere in the string
    return match.group(1) if match else None

def download_GTA_STPT_zarr(exp_id, level, output_dir, force=False, full=False, verbose=False):
    """
    Download level-N serial 2-photon (STPT) data from an Allen Genetic Tools Atlas (GTA) experiment.

    Parameters
    ----------
    exp_id : str
        Allen GTA experiment ID.
    level : str
        Zarr resolution level to download (0 is highest resolution and 9 is lowest).
    output_dir : str
        Output directory for downloaded data.
    workers : int, optional
        Number of parallel downloads (default is 10).

    Notes
    -----
    - X & Y resolution levels are as follows:
        - 0: 0.35 µm
        - 1: 0.7 µm
        - 2: 1.4 µm
        - 3: 2.8 µm
        - 4: 5.6 µm
        - 5: 11.2 µm
        - 6: 22.4 µm
        - 7: 44.8 µm
        - 8: 89.6 µm
        - 9: 179.2 µm
    - Z resolution is always 100 µm.

    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)


    # Define AWS s3 paths
    primary_root = f"s3://allen-genetic-tools/tissuecyte/{exp_id}/ome_zarr_conversion/{exp_id}.zarr"
    alternate_root = f"s3://allen-genetic-tools/tissuecyte/{exp_id}/ome-zarr"
    local_root = output_dir / f"{exp_id}.zarr"
    primary_level_path = f"{primary_root}/{level}"
    alternate_level_path = f"{alternate_root}/{level}"

    # Set up S3 filesystem
    fs = s3fs.S3FileSystem(anon=True)

    if force or not local_root.exists():
        try:
            # Check if the zarr level exists in either primary or alternate paths
            if fs.exists(primary_level_path):
                zarr_root = primary_root
            elif fs.exists(alternate_level_path):
                zarr_root = alternate_root
            else:
                # List available levels from each root if the level is missing
                available_primary_levels = []
                available_alt_levels = []
                if fs.exists(primary_root):
                    available_primary_levels = fs.ls(primary_root, detail=False)
                    available_primary_levels = [Path(p).name for p in available_primary_levels if Path(p).name.isdigit()]
                if fs.exists(alternate_root):
                    available_alt_levels = fs.ls(alternate_root, detail=False)
                    available_alt_levels = [Path(p).name for p in available_alt_levels if Path(p).name.isdigit()]

                print(f"[{exp_id}] ⚠️ Zarr level {level} not found at either:")
                print(f"   - {primary_level_path}")
                print(f"   - {alternate_level_path}")
                if available_primary_levels or available_alt_levels:
                    print(f"   ✅ Available levels:")
                    if available_primary_levels:
                        print(f"     • [primary]  {sorted(available_primary_levels)}")
                    if available_alt_levels:
                        print(f"     • [alternate] {sorted(available_alt_levels)}")
                else:
                    print("   ❌ No zarr root found at either path.")
                return

            if verbose:
                print(f"[{exp_id}] Downloading level {level} of: {zarr_root} → {local_root}")

            # Download required top-level metadata files
            for meta_file in [".zattrs", ".zgroup"]:
                s3_meta = f"{zarr_root}/{meta_file}"
                local_meta = local_root / meta_file
                try:
                    fs.get(s3_meta, local_meta)
                except FileNotFoundError:
                    print(f"[{exp_id}] ⚠️ Skipped missing metadata: {meta_file}")

            # Download the specified level or the full Zarr root
            if full:
                s3_dataset = zarr_root
                local_dataset = local_root
                if verbose:
                    print(f"[{exp_id}] ⚠️ Downloading FULL Zarr: {zarr_root} → {local_root} (this may be >100 GB)")
            else:
                s3_dataset = f"{zarr_root}/{level}"
                local_dataset = local_root / level
                if verbose:
                    print(f"[{exp_id}] Downloading level {level}: {s3_dataset} → {local_dataset}")


            fs.get(s3_dataset, local_dataset, recursive=True)

        except Exception as e:
            print(f"⚠️ Error processing {exp_id}: {e}")

    else:
        print(f"[{exp_id}] Skipping {local_root} (already exists)")


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    if args.full:
        print("[yellow]⚠️ You selected '--full' — this may download hundreds of gigabytes per experiment.[/yellow]\n")

    if args.csv:
        # If a CSV file is provided, read experiment IDs from it
        s3_paths = get_s3_paths_from_csv(args.csv, args.column)
        exp_ids = [extract_exp_id(path) for path in s3_paths]
        exp_ids = [eid for eid in exp_ids if eid is not None]

        # If there were paths with no valid experiment IDs, print a warning
        if not exp_ids:
            print(f"No valid experiment IDs found in the CSV file '{args.csv}'. Please check the '{args.column}' column.")
            print("Experiment IDs are extracted using the regex pattern: r'/(\d{9,})/'")

    elif len(args.exp_ids) > 0:
        # If experiment IDs are provided as command line arguments, use them directly
        exp_ids = args.exp_ids
    else:
        # If no experiment IDs are provided, print help and exit
        print("No experiment IDs provided. Use -e <exp_id> or -c <csv_path> to specify experiment IDs.")
        return
    
    # Define output directory
    if args.output is not None:
        output_dir = Path(args.output)
    else:
        output_dir = Path(f"GTA_STPT_level_{args.level}")

    # Get uniq experiment IDs
    exp_ids = list(set(exp_ids))  # Remove duplicates

    # Print message about downloading the datasets
    print(f"\n[bold green]Downloading {len(exp_ids)} Zarr datasets at level {args.level} to {output_dir}...[/bold green]\n")

    progress, task_id = initialize_progress_bar(len(exp_ids), task_message="[bold green]Downloading Zarr datasets...")
    with Live(progress):

        def wrapped_download(exp_id):
            download_GTA_STPT_zarr(exp_id, args.level, output_dir, args.force, args.full, args.verbose)
            progress.update(task_id, advance=1)
    
        # Download each experiment ID in parallel
        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            futures = [executor.submit(wrapped_download, exp_id) for exp_id in exp_ids]
            for f in as_completed(futures):
                if f.result() is not None:
                    print(f.result())  # Print any exceptions raised in the threads

    verbose_end_msg()
    

if __name__ == "__main__":
    main()
