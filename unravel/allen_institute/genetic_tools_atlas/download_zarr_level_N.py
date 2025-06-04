#!/usr/bin/env python3

"""
Download a specific level of STPT .zarr datasets from the Allen Genetic Tools Atlas.

Usage given a list of experiment IDs:
-------------------------------------
    ./download_zarr_level_N.py -e <exp_id1> <exp_id2> ... -l <level> -o <output_dir> [-w <workers>]

Usage given a CSV file with S3 paths:
-------------------------------------
    ./download_zarr_level_N.py -c <path_to_csv> -l <level> -o <output_dir> [-pc <path_column>] [-w <workers>]
"""

import s3fs
from pathlib import Path
from rich import print
from rich.traceback import install
from concurrent.futures import ThreadPoolExecutor, as_completed

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.config import Configuration
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg, print_func_name_args_times

def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-e', '--exp_ids', help='Allen Genetic Tools Atlas experiment ID to download (e.g., 1342775164)', nargs='*', action=SM)
    opts.add_argument('-l', '--level', help='path/metadata.txt. Default: parameters/metadata.txt', default="parameters/metadata.txt", action=SM)
    opts.add_argument('-o', '--output', help='Output directory. Default: GTA_STPT', default="GTA_STPT", action=SM)
    opts.add_argument('-c', '--csv', help='Path to a CSV file with experiment IDs. If provided, will read IDs from this file instead of command line.', default=None, action=SM)
    opts.add_argument('-pc', '--path_column', help='Column name in the CSV file that contains the s3 paths to the zarr files. Default: "STPT Data File Path"', default="STPT Data File Path", action=SM)
    opts.add_argument('-w', '--workers', help='Number of parallel downloads', type=int, default=10, action=SM)

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
    path_list = [path.rstrip('/') for path in path_list] # Remove trailing slashes
    return path_list

@print_func_name_args_times()
def download_GTA_STPT_zarr(exp_id, level, output_dir):
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

    # Set up S3 filesystem
    fs = s3fs.S3FileSystem(anon=True)

    # Define AWS s3 paths
    zarr_root = f"s3://allen-genetic-tools/tissuecyte/{exp_id}/ome_zarr_conversion/{exp_id}.zarr"
    alt_zarr_root = f"s3://allen-genetic-tools/tissuecyte/{exp_id}/ome-zarr/"
    local_root = output_dir / f"{exp_id}.zarr"

    if not local_root.exists():
        try:
            # Check if the zarr root exists
            if not fs.exists(zarr_root):
                print(f"[{exp_id}] Zarr root does not exist: {zarr_root}. Trying alternative path.")
                zarr_root = alt_zarr_root
            if not fs.exists(zarr_root):
                print(f"[{exp_id}] ⚠️ Zarr root does not exist: {zarr_root}. Skipping.")
                return

            print(f"[{exp_id}] Downloading level {level} of: {zarr_root} → {local_root}")

            # Download required top-level metadata files
            for meta_file in [".zattrs", ".zgroup"]:
                s3_meta = f"{zarr_root}/{meta_file}"
                local_meta = local_root / meta_file
                try:
                    fs.get(s3_meta, local_meta)
                except FileNotFoundError:
                    print(f"[{exp_id}] ⚠️ Skipped missing metadata: {meta_file}")

            # Download only resolution level N
            s3_dataset = f"{zarr_root}/{level}"  # For all levels use zarr_root --> local_root
            local_dataset = local_root / level
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

    if args.csv:
        # If a CSV file is provided, read experiment IDs from it
        s3_paths = get_s3_paths_from_csv(args.csv, args.path_column)
        exp_ids = [Path(path).name.split('.')[0] for path in s3_paths]
    elif len(args.exp_ids) > 0:
        # If experiment IDs are provided as command line arguments, use them directly
        exp_ids = args.exp_ids
    else:
        # If no experiment IDs are provided, print help and exit
        print("No experiment IDs provided. Use -e <exp_id> or -c <csv_path> to specify experiment IDs.")
        return
    
    # Download each experiment ID in parallel
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = [
            executor.submit(download_GTA_STPT_zarr, exp_id, args.level, args.output)
            for exp_id in exp_ids
        ]
        for f in as_completed(futures):
            if f.result() is not None:
                print(f.result())  # Print any exceptions raised in the threads

    verbose_end_msg()
    

if __name__ == "__main__":
    main()
