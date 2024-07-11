#!/usr/bin/env python3

"""
Use ``cluster_org_data`` from UNRAVEL to aggregate and organize csv outputs from ``cluster_validation``.

Usage
-----
    cluster_org_data -e <list of experiment directories> -cvd '<asterisk>' -td <target_dir> -vd <path/vstats_dir> -v
"""

import argparse
import re
import shutil
from glob import glob
from pathlib import Path
from rich import print
from rich.live import Live
from rich.traceback import install

from unravel.core.argparse_utils import SuppressMetavar, SM
from unravel.core.config import Configuration 
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg, get_samples


def parse_args():
    parser = argparse.ArgumentParser(formatter_class=SuppressMetavar)
    parser.add_argument('-e', '--exp_paths', help='List of experiment dir paths w/ sample?? dirs to process.', nargs='*', default=None, action=SM)
    parser.add_argument('-p', '--pattern', help='Pattern for sample?? dirs. Use cwd if no matches.', default='sample??', action=SM)
    parser.add_argument('-d', '--dirs', help='List of sample?? dir names or paths to dirs to process', nargs='*', default=None, action=SM)
    parser.add_argument('-cvd', '--cluster_val_dirs', help='Glob pattern matching cluster validation output dirs to copy data from (relative to ./sample??/clusters/)', required=True, action=SM)
    parser.add_argument('-vd', '--vstats_path', help='path/vstats_dir (the dir ``vstats`` was run from) to copy p val, info, and index files if provided', default=None, action=SM)
    parser.add_argument('-dt', '--density_type', help='Type of density data to aggregate (cell [default] or label).', default='cell', action=SM)
    parser.add_argument('-td', '--target_dir', help='path/dir to copy results. If omitted, copy data to the cwd', default=None, action=SM)
    parser.add_argument('-pvt', '--p_val_txt', help='Name of the file w/ the corrected p value thresh (e.g., from ``cluster_fdr``). Default: p_value_threshold.txt', default='p_value_threshold.txt', action=SM)
    parser.add_argument('-v', '--verbose', help='Increase verbosity.', action='store_true', default=False)
    parser.epilog = __doc__
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

        validation_dir_name = validation_dir_name.replace('_gt_', '_v_').replace('_lt_', '_v_')

        if validation_dir_name.endswith('_LH') or validation_dir_name.endswith('_RH'):
            cluster_correction_dir = validation_dir_name[:-3]  # Remove last 3 characters (_LH or _RH)
        else:
            cluster_correction_dir = validation_dir_name

        # Regular expression to match the part before and after 'q*' to remove any suffix added to the rev_cluster_index<suffix>.nii.gz
        pattern = r'(.*q\d+\.\d+)(_.+)?'  # This also works when there is no "suffix"
        match = re.match(pattern, cluster_correction_dir)
        if match:
            cluster_correction_dir = match.group(1)
            suffix = match.group(2)[1:] if match.group(2) else ''  # This gets the string after the q value if there is one
        else:
            print("\n    [red1]No match found in cluster_org_data\n")

        cluster_correction_path = vstats_path / 'stats' / cluster_correction_dir

        if not cluster_correction_path.exists():
            cluster_correction_dir = find_matching_directory(vstats_path / 'stats', cluster_correction_dir)
            cluster_correction_path = vstats_path / 'stats' / cluster_correction_dir

        if not cluster_correction_path.exists():
            print(f'\n    [red]Path for copying the rev_cluster_index.nii.gz and p value threshold does not exist: {cluster_correction_path}\n')
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

        if validation_dir_name.endswith('_LH'):
            rev_cluster_index_path = cluster_correction_path / f'{str(validation_dir.name)[:-3]}_rev_cluster_index_LH.nii.gz'
        elif validation_dir_name.endswith('_RH'):
            rev_cluster_index_path = cluster_correction_path / f'{str(validation_dir.name)[:-3]}_rev_cluster_index_RH.nii.gz'
        else:
            rev_cluster_index_path = cluster_correction_path / f'{str(validation_dir.name)}_rev_cluster_index.nii.gz'

        if not rev_cluster_index_path.exists(): 
            suffix = str(validation_dir_name).replace(str(cluster_correction_path.name), '')
            rev_cluster_index_path =  cluster_correction_path / f"{cluster_correction_path.name}_rev_cluster_index{suffix}.nii.gz"

        if rev_cluster_index_path.exists():
            dest_rev_cluster_index = dest_path / rev_cluster_index_path.name
            if not dest_rev_cluster_index.exists():
                cp(src=rev_cluster_index_path, dest=dest_rev_cluster_index)
        else: 
            print(f'\n    [red]The rev_cluster_index.nii.gz ({rev_cluster_index_path}) does not exist\n')
            import sys ; sys.exit()

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

    samples = get_samples(args.dirs, args.pattern, args.exp_paths)
    
    for sample in samples:

        sample_path = Path(sample).resolve() if sample != Path.cwd().name else Path.cwd()

        clusters_path = sample_path / 'clusters'
        if clusters_path.exists():
            organize_validation_data(sample_path, clusters_path, args.cluster_val_dirs, args.density_type, target_dir, args.vstats_path, args.p_val_txt)

    verbose_end_msg()


if __name__ == '__main__':
    main()