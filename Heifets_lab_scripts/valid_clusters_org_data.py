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
from unravel_utils import print_cmd_and_times, initialize_progress_bar, get_samples, print_func_name_args_times


def parse_args():
    parser = argparse.ArgumentParser(description='Aggregates csv outputs from validate_clusters.py', formatter_class=SuppressMetavar)
    parser.add_argument('-e', '--exp_paths', help='List of experiment dir paths w/ sample?? dirs to process.', nargs='*', default=None, action=SM)
    parser.add_argument('-p', '--pattern', help='Pattern for sample?? dirs. Use cwd if no matches.', default='sample??', action=SM)
    parser.add_argument('-d', '--dirs', help='List of sample?? dir names or paths to dirs to process', nargs='*', default=None, action=SM)
    parser.add_argument('-i', '--input', help='Glob pattern matching cluster validation output dirs to copy data from', required=True, action=SM)
    parser.add_argument('-vd', '--vstats_path', help='path/vstats_dir (vstats.py dir)', default=None, action=SM)
    parser.add_argument('-dt', '--density_type', help='Type of density data to aggregate (cell [default] or label).', default='cell', action=SM)
    parser.add_argument('-td', '--target_dir', help='path/dir to copy results. If omitted, copy data to the cwd', default=None, action=SM)
    parser.add_argument('-pvt', '--p_val_txt', help='Name of the file w/ the corrected p value thresh (e.g., from fdr.py). Default: p_value_threshold.txt', default='p_value_threshold.txt', action=SM)
    parser.add_argument('-v', '--verbose', help='Increase verbosity.', action='store_true', default=False)
    parser.epilog = """Usage: valid_clusters_org_data.py -e <list of experiment directories> -i '*' -td <target_dir> -vd <path/vstats_dir> -v
"""
    return parser.parse_args()

# @print_func_name_args_times()
def cp(src, dest):
    """Copy a file from src path to a dest path, optionally printing the action.
    
    Args:
        - src (Path): the source path
        - dest (Path): the destination path"""
    shutil.copy(src, dest)

def copy_stats_files(validation_dir, dest_path, vstats_path, p_val_txt):
    """Process statistical files associated with cluster corrections.
    
    Args:
        - validation_dir (Path): the path to the validation directory
        - dest_path (Path): the path to the new directory
        - vstats_path (Path): the path to the vstats directory
        - p_val_txt (str): the name of the file with the corrected p value threshold"""
    vstats_path = Path(vstats_path)
    if vstats_path.exists():
        validation_dir_name = str(validation_dir.name)
        if validation_dir_name.endswith('_LH') or validation_dir_name.endswith('_RH'):
            cluster_correction_dir = validation_dir_name[:-3]  # Remove last 3 characters (_LH or _RH)
        else:
            cluster_correction_dir = validation_dir_name
        cluster_correction_path = vstats_path / 'stats' / cluster_correction_dir

        cluster_info = cluster_correction_path / f'{cluster_correction_dir}_cluster_info.txt'
        if cluster_info.exists():
            dest_stats = dest_path / cluster_info.name
            cp(src=cluster_info, dest=dest_stats)
            
            p_val_thresh_file = cluster_correction_path / p_val_txt
            if p_val_thresh_file.exists():
                dest_p_val_thresh = dest_path / p_val_txt
                cp(src=p_val_thresh_file, dest=dest_p_val_thresh)

def organize_validation_data(sample_path, clusters_path, validation_dir_pattern, density_type, target_dir, vstats_path, p_val_txt):
    """Organize the cluster validation data.
    
    Args:
        - sample_path (Path): the path to the sample directory
        - clusters_path (Path): the path to the clusters directory
        - validation_dir_pattern (str): the pattern to match the validation directories
        - density_type (str): the type of density data to aggregate (cell or label)
        - target_dir (Path): the path to the target directory
        - vstats_path (Path): the path to the vstats directory
        - p_val_txt (str): the name of the file with the corrected p value threshold"""
    for validation_dir in clusters_path.glob(validation_dir_pattern):
        if validation_dir.is_dir():
            dest_path = target_dir / validation_dir.name
            dest_path.mkdir(parents=True, exist_ok=True)
            src_file = validation_dir / f'{density_type}_density_data.csv'
            if src_file.exists():
                dest_file = dest_path / f'{sample_path.name}__{density_type}_density_data__{validation_dir.name}.csv'
                cp(src=src_file, dest=dest_file)

            if vstats_path is not None:
                copy_stats_files(validation_dir, dest_path, vstats_path, p_val_txt)


def main():

    target_dir = Path(args.target_dir).resolve() if args.target_dir else Path.cwd()
    target_dir.mkdir(exist_ok=True, parents=True)

    samples = get_samples(args.dirs, args.pattern, args.exp_paths)
    
    progress, task_id = initialize_progress_bar(len(samples), "[red]Processing samples...")
    with Live(progress):
        for sample in samples:

            sample_path = Path(sample).resolve() if sample != Path.cwd().name else Path.cwd()

            clusters_path = sample_path / 'clusters'
            if clusters_path.exists():
                organize_validation_data(sample_path, clusters_path, args.input, args.density_type, target_dir, args.vstats_path, args.p_val_txt)
            
            progress.update(task_id, advance=1)


if __name__ == '__main__':
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    print_cmd_and_times(main)()
