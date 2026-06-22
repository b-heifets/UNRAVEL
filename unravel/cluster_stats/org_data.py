#!/usr/bin/env python3

"""
Use ``cstats_org_data`` (``cod``) from UNRAVEL to aggregate and organize csv outputs from ``cstats_validation``.

Prereqs:
    - ``cstats_validation`` (``cstats_val``) to generate the cluster validation

Inputs: 
    - clusters/cluster_validation_results_`*` (glob pattern matching ``cstats_validation`` output dirs)
    - CSVs with validation metric data (e.g., cell_density_data.csv, label_density_data.csv, mean_in_cluster_data.csv, or mean_in_seg_in_cluster_data.csv from ``cstats_validation``)
    - Optional: path/vstats to copy p val, info, and index files

Outputs:
    - target_dir/<cluster_validation_results_* >/sample??__<metric>_data__<cluster_validation_results_* >.csv
    - or, with --by_subregion:
      target_dir/<cluster_validation_results_* >/sample??__<metric>_by_subregion_data__<cluster_validation_results_* >.csv

Notes:
    - If the cluster_validation_results_`*` directory name contains "_gt_" or "_lt_", the script will attempt to replace it with "_v_" to match the vstats directory.
    - This is useful when non-directional maps were made as directional.
    - If the cluster_validation_results_`*` directory name contains "_LH" or "_RH", the script will attempt to remove it to match the vstats directory.    

Usage
-----
    cstats_org_data -cvd '<asterisk>' -me <metric> [-vd path/vstats_dir] [-td target_dir] [-pvt p_value_threshold.txt] [-d list of paths] [-p sample??] [-v]
"""

import shutil
from pathlib import Path
from rich import print
from rich.traceback import install

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM

from unravel.core.config import Configuration 
from unravel.core.utils import log_command, match_files, verbose_start_msg, verbose_end_msg, get_samples, print_func_name_args_times


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-cvd', '--cluster_val_dirs', help='One or more glob patterns matching cluster validation output dirs to copy data from (relative to ./sample??/clusters/)', nargs='*', required=True, action=SM)

    opts = parser.add_argument_group('Optional args')
    opts.add_argument('-me', '--metric',help='Metric output from cstats_validation to aggregate (e.g., cell_density, label_density, mean_in_cluster, mean_in_seg_in_cluster)',required=True,action=SM)
    opts.add_argument('-vd', '--vstats_path', help='path/vstats_dir (the dir ``vstats`` was run from) to copy p val, info, and index files if provided', default=None, action=SM)
    opts.add_argument('-td', '--target_dir', help='path/dir to copy results. If omitted, copy data to the cwd', default=None, action=SM)
    opts.add_argument('-pvt', '--p_val_txt', help='Name of the file w/ the corrected p value thresh (e.g., from ``cstats_fdr``). Default: p_value_threshold.txt', default='p_value_threshold.txt', action=SM)
    opts.add_argument('-bsr', '--by_subregion', help='Copy <metric>_by_subregion_data.csv instead of <metric>_data.csv.', action='store_true', default=False)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-d', '--dirs', help='Paths to sample?? dirs and/or dirs containing them (space-separated) for batch processing. Default: current dir', nargs='*', default=None, action=SM)
    general.add_argument('-p', '--pattern', help='Pattern for directories to process. Default: sample??', default='sample??', action=SM)
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)

    return parser.parse_args()


def resolve_cluster_correction_dir(validation_dir_name):
    name = str(validation_dir_name)

    # Normalize directional naming
    name = name.replace('_gt_', '_v_').replace('_lt_', '_v_')

    # Remove validation-output suffix
    name = name.replace('_rev_cluster_index', '')

    # Remove hemi suffix only for finding the parent stats dir
    hemi = None
    if name.endswith('_LH') or name.endswith('_RH'):
        hemi = name[-2:]
        name = name[:-3]

    return name, hemi

def find_matching_directory(base_path, long_name):
    base_path = Path(base_path)

    # Get all directories in base_path
    dirs = [d for d in base_path.iterdir() if d.is_dir()]

    # Find a directory whose name is a substring of long_name or vice versa
    for dir in dirs:
        if dir.name in long_name or long_name in dir.name:
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
        cluster_correction_dir, hemi = resolve_cluster_correction_dir(validation_dir_name)

        # Construct the path and check existence
        cluster_correction_path = vstats_path / 'stats' / cluster_correction_dir

        if not cluster_correction_path.exists():
            matched_dir = find_matching_directory(vstats_path / 'stats', cluster_correction_dir)

            if matched_dir is not None:
                cluster_correction_dir = matched_dir
                cluster_correction_path = vstats_path / 'stats' / cluster_correction_dir

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

        # Handle rev_cluster_index.nii.gz with optional hemisphere suffix
        if hemi:
            rev_cluster_index_path = cluster_correction_path / f"{cluster_correction_path.name}_rev_cluster_index_{hemi}.nii.gz"
        else:
            rev_cluster_index_path = cluster_correction_path / f"{cluster_correction_path.name}_rev_cluster_index.nii.gz"

        if rev_cluster_index_path.exists():
            dest_rev_cluster_index = dest_path / rev_cluster_index_path.name
            if not dest_rev_cluster_index.exists():
                cp(src=rev_cluster_index_path, dest=dest_rev_cluster_index)
        else: 
            print(f'\n    [red]The rev_cluster_index.nii.gz ({rev_cluster_index_path}) does not exist\n')
            import sys; sys.exit()

@print_func_name_args_times()
def organize_validation_data(sample_path, clusters_path, validation_dir_pattern, metric, target_dir, vstats_path, p_val_txt, by_subregion=False):
    """Copy the cluster validation, p value, cluster info, and rev_cluster_index files to the target directory.
    
    Args:
        - sample_path (Path): the path to the sample directory
        - clusters_path (Path): the path to the clusters directory
        - validation_dir_pattern (str): the pattern to match the validation directories
        - metric (str): the type of metric data to aggregate (e.g., cell_density, label_density, mean_in_cluster, mean_in_seg_in_cluster)
        - target_dir (Path): the path to the target directory
        - vstats_path (Path): the path to the vstats directory
        - p_val_txt (str): the name of the file with the corrected p value threshold
        - by_subregion (bool): whether to copy <metric>_by_subregion_data.csv instead of <metric>_data.csv
    """

    validation_dirs = []
    for pat in validation_dir_pattern:
        validation_dirs.extend(match_files(pat, clusters_path))

    # De-dupe while preserving order
    seen = set()
    validation_dirs = [d for d in validation_dirs if not (d in seen or seen.add(d))]

    for validation_dir in validation_dirs:
        if validation_dir.is_dir():
            dest_path = target_dir / validation_dir.name
            dest_path.mkdir(parents=True, exist_ok=True)
            suffix = '_by_subregion_data.csv' if by_subregion else '_data.csv'
            src_csv = validation_dir / f'{metric}{suffix}'

            if src_csv.exists():
                dest_csv = dest_path / f'{sample_path.name}__{metric}{suffix[:-4]}__{validation_dir.name}.csv'
                if not dest_csv.exists():
                    cp(src=src_csv, dest=dest_csv)
            else:
                print(f'\n    [red]The expected csv ({src_csv}) does not exist\n')

            if vstats_path is not None:
                copy_stats_files(validation_dir=validation_dir, dest_path=dest_path, vstats_path=vstats_path, p_val_txt=p_val_txt)

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
            organize_validation_data(sample_path=sample_path, clusters_path=clusters_path, validation_dir_pattern=args.cluster_val_dirs, metric=args.metric, target_dir=target_dir, vstats_path=args.vstats_path, p_val_txt=args.p_val_txt, by_subregion=args.by_subregion)

    verbose_end_msg()


if __name__ == '__main__':
    main()