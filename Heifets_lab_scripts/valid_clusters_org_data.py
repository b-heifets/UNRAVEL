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
    """Copy a file from src path to a dest path, optionally printing the action."""
    shutil.copy(src, dest)

def copy_stats_files(item, new_dir, vstats_path, p_val_txt):
    """Process statistical files associated with cluster corrections."""
    vstats_path = Path(vstats_path)
    if vstats_path.exists():
        print('vstats_path exists')

        stats_path = vstats_path / 'stats'
        
        file_to_glob = stats_path / item.name / f'{item.name}.nii.gz'
        print(f'{item.name=}')
        for path in stats_path.rglob(f'*{item.name}*.nii.gz'):
            print(path.name)

        import sys ; sys.exit()
        
        print(f'{file_to_glob=}')
        # rev_cluster_index = next(cluster_correction_path.glob(f"{item.name}.nii.gz"), None)
        rev_cluster_index = next(stats_path.rglob(f"{item.name}.nii.gz"), None)

        print(f'{rev_cluster_index=}')
        import sys ; sys.exit()

        if Path(rev_cluster_index).exists():
            cluster_correction_dir = Path(rev_cluster_index).parent
            
            print(f'{cluster_correction_dir=}')
            
            cluster_info = cluster_correction_dir / f'{cluster_correction_dir.name}_cluster_info.txt'
            if cluster_info.exists():
                dest_stats = new_dir / cluster_info.name
                cp(src=cluster_info, dest=dest_stats)
            
            p_val_thresh_file = cluster_correction_dir / p_val_txt
            if p_val_thresh_file.exists():
                dest_p_val_thresh = new_dir / p_val_txt
                cp(src=p_val_thresh_file, dest=dest_p_val_thresh)

def organize_validation_data(sample_path, clusters_path, validation_dir_pattern, density_type, target_dir, vstats_path, p_val_txt):
    """Organize the cluster validation data.
    
    Args:
        - sample_path (Path): the path to the sample directory
        - clusters_path (Path): the path to the clusters directory
        - target_dir (Path): the path to the target directory"""
    for item in clusters_path.glob(validation_dir_pattern):
        if item.is_dir():
            new_dir = target_dir / item.name
            new_dir.mkdir(parents=True, exist_ok=True)
            src_file = item / f'{density_type}_density_data.csv'
            if src_file.exists():
                dest_file = new_dir / f'{sample_path.name}__{density_type}_density_data__{item.name}.csv'
                cp(src=src_file, dest=dest_file)

            if vstats_path is not None:
                copy_stats_files(item, new_dir, vstats_path, p_val_txt)


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
