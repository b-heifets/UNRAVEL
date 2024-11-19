#!/usr/bin/env python3

"""
Use ``cstats_org_data`` (``cod``) from UNRAVEL to aggregate and organize csv outputs from ``cstats_validation``.

Inputs: 
    - clusters/cluster_validation_results_`*` (glob pattern matching ``cstats_validation`` output dirs)
    - CSVs with the density data (e.g., cell_density_data.csv or label_density_data.csv from ``cstats_validation``)
    - Optional: path/vstats to copy p val, info, and index files

Outputs:
    - target_dir/sample??__cell_density_data__<cluster_validation_results_`*`>.csv
    - target_dir/sample??__label_density_data__<cluster_validation_results_`*`>.csv

Notes:
    - If the cluster_validation_results_`*` directory name contains "_gt_" or "_lt_", the script will attempt to replace it with "_v_" to match the vstats directory.
    - This is useful when non-directional maps were made as directional.
    - If the cluster_validation_results_`*` directory name contains "_LH" or "_RH", the script will attempt to remove it to match the vstats directory.    

Usage
-----
    cstats_org_data -cvd '<asterisk>' [-dt cell | label] [-vd path/vstats_dir] [-td target_dir] [-pvt p_value_threshold.txt] [-d list of paths] [-p sample??] [-v]
"""

import re
import shutil
from glob import glob
from pathlib import Path
from rich import print
from rich.live import Live
from rich.traceback import install

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM

from unravel.core.config import Configuration 
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg, get_samples


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-cvd', '--cluster_val_dirs', help='Glob pattern matching cluster validation output dirs to copy data from (relative to ./sample??/clusters/)', required=True, action=SM)

    opts = parser.add_argument_group('Optional args')
    opts.add_argument('-dt', '--density_type', help='Type of density data to aggregate (cell [default] or label).', default='cell', action=SM)
    opts.add_argument('-vd', '--vstats_path', help='path/vstats_dir (the dir ``vstats`` was run from) to copy p val, info, and index files if provided', default=None, action=SM)
    opts.add_argument('-td', '--target_dir', help='path/dir to copy results. If omitted, copy data to the cwd', default=None, action=SM)
    opts.add_argument('-pvt', '--p_val_txt', help='Name of the file w/ the corrected p value thresh (e.g., from ``cstats_fdr``). Default: p_value_threshold.txt', default='p_value_threshold.txt', action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-d', '--dirs', help='Paths to sample?? dirs and/or dirs containing them (space-separated) for batch processing. Default: current dir', nargs='*', default=None, action=SM)
    general.add_argument('-p', '--pattern', help='Pattern for directories to process. Default: sample??', default='sample??', action=SM)
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()

# TODO: Copy the rev_cluster_index.nii.gz to the target_dir

def find_matching_directory(base_path, long_name):
    base_path = Path(base_path)

    # Get all directories in base_path
    dirs = [d for d in base_path.iterdir() if d.is_dir()]

    # Find the directory whose name is a substring of long_name
    for dir in dirs:
        if dir.name in long_name:
            return dir.name

    return None

def cp(src, dest):
    """Copy a file from src path to a dest path, optionally printing the action.
    
    Args:
        - src (Path): the source path
        - dest (Path): the destination path"""
    if Path(src).exists():
        Path(dest).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(src, dest)

def copy_stats_files(validation_dir, dest_path, vstats_path, p_val_txt):
    """Copy the cluster info, p value threshold, and rev_cluster_index files to the target directory.
    
    Args:
        - validation_dir (Path): the path to the validation directory
        - dest_path (Path): the path to the new directory
        - vstats_path (Path): the path to the vstats directory
        - p_val_txt (str): the name of the file with the corrected p value threshold"""

    vstats_path = Path(vstats_path)

    if vstats_path.exists():
        validation_dir_name = str(validation_dir.name)
        original_validation_dir_name = validation_dir_name  # Keep original for fallback

        # Attempt to replace _gt_/_lt_ with _v_ for cases when non-directional maps were made as directional
        validation_dir_name = validation_dir_name.replace('_gt_', '_v_').replace('_lt_', '_v_')

        # Remove hemisphere suffix if present
        if validation_dir_name.endswith('_LH') or validation_dir_name.endswith('_RH'):
            cluster_correction_dir = validation_dir_name[:-3]  # Remove last 3 characters (_LH or _RH)
        else:
            cluster_correction_dir = validation_dir_name

        # Use regex to handle cases with or without "_q" in the directory name
        if '_q' in cluster_correction_dir:
            pattern = r'(.*q\d+\.\d+)(_.+)?' 
            match = re.match(pattern, cluster_correction_dir)
            if match:
                cluster_correction_dir = match.group(1)
                suffix = match.group(2)[1:] if match.group(2) else ''  # Get suffix after "q" value if present
            else:
                print(f"\n    [red1]The regex pattern {pattern} did not match the cluster_correction_dir: {cluster_correction_dir} in cstats_org_data\n")
        else:
            suffix = ''

        # Construct the path and check existence
        cluster_correction_path = vstats_path / 'stats' / cluster_correction_dir

        if not cluster_correction_path.exists():
            cluster_correction_dir = find_matching_directory(vstats_path / 'stats', cluster_correction_dir)

            if cluster_correction_dir is not None:
                cluster_correction_path = vstats_path / 'stats' / cluster_correction_dir
            else:
                # Fallback to original name
                cluster_correction_path = vstats_path / 'stats' / original_validation_dir_name
                # Remove hemisphere suffix if present
                if str(cluster_correction_path).endswith('_LH') or str(cluster_correction_path).endswith('_RH'):
                    cluster_correction_path = Path(str(cluster_correction_path)[:-3])  # Remove last 3 characters (_LH or _RH)
                else:
                    cluster_correction_path = validation_dir_name
                cluster_correction_dir = cluster_correction_path.name

        if not cluster_correction_path.exists():
            print(f'\n    [red]Path for rev_cluster_index.nii.gz, {p_val_txt}, and _cluster_info.txt does not exist: {cluster_correction_path}\n')
            import sys ; sys.exit()

        cluster_info = cluster_correction_path / f'{cluster_correction_dir}_cluster_info.txt'
        if cluster_info.exists():
            dest_stats = dest_path / cluster_info.name
            if not dest_stats.exists(): 
                cp(src=cluster_info, dest=dest_stats)
        else: 
            print(f'\n    [red]The cluster_info.txt ({cluster_info}) does not exist\n')
            
        p_val_thresh_file = cluster_correction_path / p_val_txt
        if p_val_thresh_file.exists():
            dest_p_val_thresh = dest_path / p_val_txt
            if not dest_p_val_thresh.exists():
                cp(src=p_val_thresh_file, dest=dest_p_val_thresh)
        else: 
            print(f'\n    [red]The p value threshold txt ({p_val_thresh_file}) does not exist\n')

        # Adjust rev_cluster_index path based on hemisphere suffix
        if validation_dir_name.endswith('_LH'):
            rev_cluster_index_path = cluster_correction_path / f'{str(validation_dir.name)[:-3]}_rev_cluster_index_LH.nii.gz'
        elif validation_dir_name.endswith('_RH'):
            rev_cluster_index_path = cluster_correction_path / f'{str(validation_dir.name)[:-3]}_rev_cluster_index_RH.nii.gz'
        else:
            rev_cluster_index_path = cluster_correction_path / f'{str(validation_dir.name)}_rev_cluster_index.nii.gz'

        # Adjust rev_cluster_index_path if suffix is missing
        if not rev_cluster_index_path.exists():
            suffix = str(validation_dir_name).replace(str(cluster_correction_path.name), '')
            rev_cluster_index_path =  cluster_correction_path / f"{cluster_correction_path.name}_rev_cluster_index{suffix}.nii.gz"

        if rev_cluster_index_path.exists():
            dest_rev_cluster_index = dest_path / rev_cluster_index_path.name
            if not dest_rev_cluster_index.exists():
                cp(src=rev_cluster_index_path, dest=dest_rev_cluster_index)
        else: 
            print(f'\n    [red]The rev_cluster_index.nii.gz ({rev_cluster_index_path}) does not exist\n')
            import sys; sys.exit()

def organize_validation_data(sample_path, clusters_path, validation_dir_pattern, density_type, target_dir, vstats_path, p_val_txt):
    """Copy the cluster validation, p value, cluster info, and rev_cluster_index files to the target directory.
    
    Args:
        - sample_path (Path): the path to the sample directory
        - clusters_path (Path): the path to the clusters directory
        - validation_dir_pattern (str): the pattern to match the validation directories
        - density_type (str): the type of density data to aggregate (cell or label)
        - target_dir (Path): the path to the target directory
        - vstats_path (Path): the path to the vstats directory
        - p_val_txt (str): the name of the file with the corrected p value threshold
        - cluster_idx (str): the name of the rev_cluster_index file"""

    validation_dirs = list(clusters_path.glob(validation_dir_pattern))
    if not validation_dirs:
        print(f"\n    [red1]No directories found matching pattern: {validation_dir_pattern} in {clusters_path}\n")
        import sys ; sys.exit()

    for validation_dir in clusters_path.glob(validation_dir_pattern):
        if validation_dir.is_dir():
            dest_path = target_dir / validation_dir.name
            dest_path.mkdir(parents=True, exist_ok=True)
            src_csv = validation_dir / f'{density_type}_density_data.csv'

            if src_csv.exists():
                dest_csv = dest_path / f'{sample_path.name}__{density_type}_density_data__{validation_dir.name}.csv'
                
                if not dest_csv.exists(): 
                    cp(src=src_csv, dest=dest_csv)

            if vstats_path is not None:
                copy_stats_files(validation_dir, dest_path, vstats_path, p_val_txt)

@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    target_dir = Path(args.target_dir).resolve() if args.target_dir else Path.cwd()
    target_dir.mkdir(exist_ok=True, parents=True)

    sample_paths = get_samples(args.dirs, args.pattern, args.verbose)

    for sample_path in sample_paths:

        clusters_path = sample_path / 'clusters'
        if clusters_path.exists():
            organize_validation_data(sample_path, clusters_path, args.cluster_val_dirs, args.density_type, target_dir, args.vstats_path, args.p_val_txt)

    verbose_end_msg()


if __name__ == '__main__':
    main()