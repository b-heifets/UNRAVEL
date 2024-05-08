#!/usr/bin/env python3

import argparse
import shutil
from glob import glob
from pathlib import Path
from rich import print
from rich.live import Live
from rich.traceback import install

from argparse_utils import SuppressMetavar, SM
from unravel_config import Configuration 
from unravel_utils import print_cmd_and_times, get_samples


def parse_args():
    parser = argparse.ArgumentParser(description='Aggregates csv outputs from validate_clusters.py', formatter_class=SuppressMetavar)
    parser.add_argument('-e', '--exp_paths', help='List of experiment dir paths w/ sample?? dirs to process.', nargs='*', default=None, action=SM)
    parser.add_argument('-p', '--pattern', help='Pattern for sample?? dirs. Use cwd if no matches.', default='sample??', action=SM)
    parser.add_argument('-d', '--dirs', help='List of sample?? dir names or paths to dirs to process', nargs='*', default=None, action=SM)
    parser.add_argument('-cvd', '--cluster_val_dirs', help='Glob pattern matching cluster validation output dirs to copy data from (relative to ./sample??/clusters/)', required=True, action=SM)
    parser.add_argument('-vd', '--vstats_path', help='path/vstats_dir (the dir vstats.py was run from) to copy p val, info, and index files if provided', default=None, action=SM)
    parser.add_argument('-dt', '--density_type', help='Type of density data to aggregate (cell [default] or label).', default='cell', action=SM)
    parser.add_argument('-td', '--target_dir', help='path/dir to copy results. If omitted, copy data to the cwd', default=None, action=SM)
    parser.add_argument('-pvt', '--p_val_txt', help='Name of the file w/ the corrected p value thresh (e.g., from fdr.py). Default: p_value_threshold.txt', default='p_value_threshold.txt', action=SM)
    parser.add_argument('-v', '--verbose', help='Increase verbosity.', action='store_true', default=False)
    parser.epilog = """Usage: valid_clusters_org_data.py -e <list of experiment directories> -cvd '*' -td <target_dir> -vd <path/vstats_dir> -v
"""
    return parser.parse_args()

# TODO: Copy the rev_cluster_index.nii.gz to the target_dir

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
        cluster_correction_path = vstats_path / 'stats' / cluster_correction_dir

        cluster_info = cluster_correction_path / f'{cluster_correction_dir}_cluster_info.txt'
        if cluster_info.exists():
            dest_stats = dest_path / cluster_info.name
            if not dest_stats.exists(): 
                cp(src=cluster_info, dest=dest_stats)
            
        p_val_thresh_file = cluster_correction_path / p_val_txt
        if p_val_thresh_file.exists():
            dest_p_val_thresh = dest_path / p_val_txt
            if not dest_p_val_thresh.exists():
                cp(src=p_val_thresh_file, dest=dest_p_val_thresh)

        if validation_dir_name.endswith('_LH'):
            rev_cluster_index_path = cluster_correction_path / f'{str(validation_dir.name)[:-3]}_rev_cluster_index_LH.nii.gz'
        elif validation_dir_name.endswith('_RH'):
            rev_cluster_index_path = cluster_correction_path / f'{str(validation_dir.name)[:-3]}_rev_cluster_index_RH.nii.gz'
        else:
            rev_cluster_index_path = cluster_correction_path / f'{str(validation_dir.name)}_rev_cluster_index.nii.gz'

        if rev_cluster_index_path.exists():
            dest_rev_cluster_index = dest_path / rev_cluster_index_path.name
            if not dest_rev_cluster_index.exists():
                cp(src=rev_cluster_index_path, dest=dest_rev_cluster_index)

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


def main():

    target_dir = Path(args.target_dir).resolve() if args.target_dir else Path.cwd()
    target_dir.mkdir(exist_ok=True, parents=True)

    samples = get_samples(args.dirs, args.pattern, args.exp_paths)
    
    for sample in samples:

        sample_path = Path(sample).resolve() if sample != Path.cwd().name else Path.cwd()

        clusters_path = sample_path / 'clusters'
        if clusters_path.exists():
            organize_validation_data(sample_path, clusters_path, args.cluster_val_dirs, args.density_type, target_dir, args.vstats_path, args.p_val_txt)


if __name__ == '__main__':
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    print_cmd_and_times(main)()