#!/usr/bin/env python3

import argparse
import subprocess
from pathlib import Path
from rich import print
from rich.traceback import install
from aggregate_files_w_recursive_search import find_and_copy_files
from unravel_config import Config

from argparse_utils import SuppressMetavar, SM
from unravel_config import Configuration 
from unravel_utils import print_cmd_and_times

def parse_args():
    parser = argparse.ArgumentParser(description='Aggregates and analyzes cluster validation data from valid_clusters_1_cell_or_label_densities.py', formatter_class=SuppressMetavar)
    parser.add_argument('-c', '--config', help='Path to the config.ini file. Default: valid_clusters_2-10_summary.ini', default=Path(__file__).parent / 'valid_clusters_2-10_summary.ini', action=SM)

    # valid_clusters_2_org_data.py -e <list of experiment directories> -cvd '*' -td <target_dir> -vd <path/vstats_dir> -v
    parser.add_argument('-e', '--exp_paths', help='List of experiment dir paths w/ sample?? dirs to process.', nargs='*', default=None, action=SM)
    parser.add_argument('-cvd', '--cluster_val_dirs', help='Glob pattern matching cluster validation output dirs to copy data from (relative to ./sample??/clusters/)', required=True, action=SM) 
    parser.add_argument('-vd', '--vstats_path', help='path/vstats_dir (the dir vstats.py was run from) to copy p val, info, and index files', required=True, action=SM)

    # valid_clusters_4_prepend_conditions.py -c <path/sample_key.csv> -f -r
    parser.add_argument('-sk', '--sample_key', help='path/sample_key.csv w/ directory names and conditions', required=True, action=SM)

    # valid_clusters_5_stats.py --groups <group1> <group2>
    parser.add_argument('--groups', help='List of group prefixes. 2 groups --> t-test. >2 --> Tukey\'s tests (The first 2 groups reflect the main comparison for validation rates)',  nargs='+', required=True)
    parser.add_argument('-cp', '--condition_prefixes', help='Condition prefixes to group data (e.g., see valid_clusters_5_stats.py)',  nargs='*', default=None, action=SM)

    # valid_clusters_6_index.py -ci path/rev_cluster_index.nii.gz -ids 1 2 3
    # parser.add_argument('-ci', '--cluster_idx', help='Path to the reverse cluster index NIfTI file.', required=True, action=SM)

    parser.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)
    return parser.parse_args()


# def run_script(script_name, script_args):
#     """Run a script using subprocess that respects the system's PATH."""
#     command = [script_name] + script_args
#     subprocess.run(command, check=True)

def run_script(script_name, script_args):
    """Run a script using subprocess that respects the system's PATH and captures output."""
    command = [script_name] + script_args
    subprocess.run(command, check=True, stdout=None, stderr=None)

def main():
    # Load settings for each script from the config file
    cfg = Config(args.config)

    # valid_clusters_2_org_data.py
    pattern = cfg.org_data.pattern
    density_type = cfg.org_data.density_type
    p_val_txt = cfg.org_data.p_val_txt

    # valid_clusters_5_stats.py
    alternate = cfg.stats.alternate
    
    # valid_clusters_6_index.py
    atlas = cfg.index.atlas
    output_rgb_lut = cfg.index.output_rgb_lut

    # valid_clusters_7_table.py
    top_regions = cfg.table.top_regions
    percent_vol = cfg.table.percent_vol

    # valid_clusters_9_prism.py
    save_all = cfg.prism.save_all

    # valid_clusters_10_3D_brain.py
    mirror = cfg.brain.mirror
    axis = cfg.brain.axis
    shift = cfg.brain.shift
    split_atlas = cfg.brain.split_atlas

    # Run valid_clusters_2_org_data.py
    org_data_args = [
        '-e', ' '.join(args.exp_paths),
        '-p', pattern,
        '-cvd', args.cluster_val_dirs,
        '-vd', args.vstats_path,
        '-dt', density_type,
        '-pvt', p_val_txt
    ]
    if args.verbose:
        org_data_args.append('-v')
    run_script('valid_clusters_2_org_data.py', org_data_args)


    ### rev_cluster_index not copied. Troubleshoot this. #############################





    # Run valid_clusters_3_group_bilateral_data.py
    run_script('valid_clusters_3_group_bilateral_data.py', [])

    # Run valid_clusters_4_prepend_conditions.py
    prepend_conditions_args = [
        '-sk', args.sample_key,
        '-f', True,
        '-r', True
    ]
    run_script('valid_clusters_4_prepend_conditions.py', prepend_conditions_args)

    # Run valid_clusters_5_stats.py
    stats_args = [
        '--groups', ' '.join(args.groups),
        '-cp', ' '.join(args.condition_prefixes),
        '-alt', alternate,
        '-pvt', p_val_txt
    ]
    if args.verbose:
        stats_args.append('-v')
    run_script('valid_clusters_5_stats.py', stats_args)

    # Run valid_clusters_6_index.py
    test_type = 't-test' if len(args.groups) == 2 else 'Tukey' if len(args.groups) > 2 else 'Invalid number of groups'
    if test_type == 'Invalid number of groups':
        print(f'\n    [red]{test_type}[/]\n')
        return

    
    # Iterate over all subdirectories in the current working directory
    for subdir in [d for d in Path.cwd().iterdir() if d.is_dir()]:
        stats_output = subdir / '_cluster_validation_info'
        valid_clusters_ids_txt = stats_output / 'valid_cluster_IDs_t-test.txt' if len(args.groups) == 2 else stats_output / 'valid_cluster_IDs_tukey.txt'
        if valid_clusters_ids_txt.exists():
            with open(valid_clusters_ids_txt, 'r') as f:
                valid_cluster_ids = f.read().split()

        # Get the corresponding reverse cluster index file
        if str(subdir).endswith('_LH'):
            rev_cluster_index_path = subdir / f'{subdir.name}_rev_cluster_index_LH.nii.gz'
        elif str(subdir).endswith('_RH'):
            rev_cluster_index_path = subdir / f'{subdir.name}_rev_cluster_index_RH.nii.gz'
        else:
            rev_cluster_index_path = subdir / f'{subdir.name}_rev_cluster_index.nii.gz'

        valid_clusters_dir = subdir / 'valid_clusters'

        index_args = [
            '-ci', rev_cluster_index_path,
            '-ids', ' '.join(valid_cluster_ids),
            '-vcd', valid_clusters_dir,
            '-a', atlas
        ]
        if output_rgb_lut:
            index_args.append('-rgb')
        run_script('valid_clusters_6_index.py', index_args)

        # Run valid_clusters_7_table.py
        table_args = [
            '-vcd', valid_clusters_dir,
            '-t', top_regions,
            '-pv', percent_vol
        ]
        if args.verbose:
            table_args.append('-v')
        run_script('valid_clusters_7_table.py', table_args)

    # Aggregate *_valid_clusters_table.xlsx files
    find_and_copy_files('*_valid_clusters_table.xlsx', Path().cwd(), 'valid_clusters_tables_and_legend')

    # Run valid_clusters_8_legend.py
    legend_args = [
        '-p', 'valid_clusters_tables_and_legend'
    ]
    run_script('valid_clusters_8_legend.py', legend_args)

    
    for subdir in [d for d in Path.cwd().iterdir() if d.is_dir()]:
        stats_output = subdir / '_cluster_validation_info'
        valid_clusters_ids_txt = stats_output / 'valid_cluster_IDs_t-test.txt' if len(args.groups) == 2 else stats_output / 'valid_cluster_IDs_tukey.txt'
        if valid_clusters_ids_txt.exists():
            with open(valid_clusters_ids_txt, 'r') as f:
                valid_cluster_ids = f.read().split()

        # Run valid_clusters_9_prism.py
        prism_args = [
            '-ids', ' '.join(valid_cluster_ids),
            '-p', Path().cwd() / subdir,
        ]
        if save_all:
            prism_args.append('-sa')
        run_script('valid_clusters_9_prism.py', prism_args)

        # Get the corresponding reverse cluster index file
        if str(subdir).endswith('_LH'):
            rev_cluster_index_path = subdir / f'{subdir.name}_rev_cluster_index_LH.nii.gz'
        elif str(subdir).endswith('_RH'):
            rev_cluster_index_path = subdir / f'{subdir.name}_rev_cluster_index_RH.nii.gz'
        else:
            rev_cluster_index_path = subdir / f'{subdir.name}_rev_cluster_index.nii.gz'

        valid_clusters_dir = subdir / 'valid_clusters'

        # Run valid_clusters_10_3D_brain.py
        brain_args = [
            '-vci', rev_cluster_index_path,
            '-m', mirror,
            '-ax', axis,
            '-s', shift,
            '-sa', split_atlas
        ]
        if args.verbose:
            brain_args.append('-v')
        run_script('valid_clusters_10_3D_brain.py', brain_args)

    # Aggregate *_ABA.nii.gz files and the rgba.txt file into a new directory #### WB
    find_and_copy_files('*_ABA.nii.gz', Path().cwd(), '3D_brain_images')
    # Need to rename the rgba.txt file so it has the same name as the corresponding NIfTI file

if __name__ == '__main__':
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    print_cmd_and_times(main)()
