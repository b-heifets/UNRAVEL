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
    parser.add_argument('-e', '--exp_paths', help='List of experiment dir paths w/ sample?? dirs to process. (needed for *_2_org_data.py)', nargs='*', action=SM)
    parser.add_argument('-cvd', '--cluster_val_dirs', help='Glob pattern matching cluster validation output dirs to copy data from (relative to ./sample??/clusters/; for *_2_*.py', action=SM) 
    parser.add_argument('-vd', '--vstats_path', help='path/vstats_dir ( dir vstats.py was run from) to copy p val, info, and index files (for *_2_*.py)', action=SM)

    # valid_clusters_4_prepend_conditions.py -c <path/sample_key.csv> -f -r
    parser.add_argument('-sk', '--sample_key', help='path/sample_key.csv w/ directory names and conditions (for *_4_prepend_conditions.py)', action=SM)

    # valid_clusters_5_stats.py --groups <group1> <group2>
    parser.add_argument('--groups', help='List of group prefixes. 2 groups --> t-test. >2 --> Tukey\'s tests (The first 2 groups reflect the main comparison for validation rates; for *_5_prepend_stats.py)',  nargs='+')
    parser.add_argument('-cp', '--condition_prefixes', help='Condition prefixes to group related data (optional for *_5_prepend_stats.py)',  nargs='*', default=None, action=SM)

    parser.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)
    return parser.parse_args()


def run_script(script_name, script_args):
    """Run a script using subprocess that respects the system's PATH and captures output."""
    # Convert all script arguments to string
    script_args = [str(arg) for arg in script_args]
    command = [script_name] + script_args
    subprocess.run(command, check=True, stdout=None, stderr=None)

def main():
    # Load settings from the config file
    if Path(args.config).exists():
        cfg = Config(args.config)
    else:
        print(f'\n    [red]{args.config} does not exist\n')
        import sys ; sys.exit()

    # Run valid_clusters_2_org_data.py
    if args.exp_paths and args.cluster_val_dirs and args.vstats_path:
        org_data_args = [
            '-e', *args.exp_paths,
            '-p', cfg.org_data.pattern,
            '-cvd', args.cluster_val_dirs,
            '-vd', args.vstats_path,
            '-dt', cfg.org_data.density_type,
            '-pvt', cfg.org_data.p_val_txt
        ]
        if args.verbose:
            org_data_args.append('-v')
        run_script('valid_clusters_2_org_data.py', org_data_args)

    # Run valid_clusters_3_group_bilateral_data.py
    if args.verbose:
        run_script('valid_clusters_3_group_bilateral_data.py', ['-v'])
    else:
        run_script('valid_clusters_3_group_bilateral_data.py', [])

    # Run valid_clusters_4_prepend_conditions.py
    if args.sample_key:
        prepend_conditions_args = [
            '-sk', args.sample_key,
            '-f',
            '-r'
        ]
        if args.verbose:
            prepend_conditions_args.append('-v')
        run_script('valid_clusters_4_prepend_conditions.py', prepend_conditions_args)

    # Run valid_clusters_5_stats.py
    if args.groups:
        stats_args = [
            '--groups', *args.groups,
            '-alt', cfg.stats.alternate,
            '-pvt', cfg.org_data.p_val_txt
        ]
        if args.condition_prefixes:
            stats_args.append(['-cp', *args.condition_prefixes])
        if args.verbose:
            stats_args.append('-v')
        run_script('valid_clusters_5_stats.py', stats_args)
    
    # Iterate over all subdirectories in the current working directory for scripts 6-9
    for subdir in [d for d in Path.cwd().iterdir() if d.is_dir()]:
        stats_output = subdir / '_cluster_validation_info'
        valid_clusters_ids_txt = stats_output / 'valid_cluster_IDs_t-test.txt' if len(args.groups) == 2 else stats_output / 'valid_cluster_IDs_tukey.txt'

        if valid_clusters_ids_txt.exists():
            with open(valid_clusters_ids_txt, 'r') as f:
                valid_cluster_ids = f.read().split()

        rev_cluster_index_path = next(subdir.glob('*rev_cluster_index*.nii.gz'))
        valid_clusters_index_dir = subdir / cfg.index.valid_clusters_dir
        
        # Run valid_clusters_6_index.py
        index_args = [
            '-ci', rev_cluster_index_path,
            '-ids', *valid_cluster_ids,
            '-vcd', valid_clusters_index_dir,
            '-a', cfg.index.atlas
        ]
        if cfg.index.output_rgb_lut:
            index_args.append('-rgb')
        if args.verbose:
            index_args.append('-v')
        run_script('valid_clusters_6_index.py', index_args)

        # # Run valid_clusters_7_3D_brain.py
        # brain_args = [
        #     '-vci', rev_cluster_index_path,
        #     '-m', cfg.brain.mirror,
        #     '-ax', cfg.brain.axis,
        #     '-s', cfg.brain.shift,
        #     '-sa', cfg.brain.split_atlas
        # ]
        # if args.verbose:
        #     brain_args.append('-v')
        # run_script('valid_clusters_7_3D_brain.py', brain_args)

        # # Run valid_clusters_8_prism.py
        # prism_args = [
        #     '-ids', *valid_cluster_ids,
        #     '-p', Path().cwd() / subdir,
        # ]
        # if cfg.prism.save_all:
        #     prism_args.append('-sa')
        # run_script('valid_clusters_8_prism.py', prism_args)

        # # Run valid_clusters_9_table.py
        # table_args = [
        #     '-vcd', valid_clusters_dir,
        #     '-t', cfg.table.top_regions,
        #     '-pv', cfg.table.percent_vol
        # ]
        # if args.verbose:
        #     table_args.append('-v')
        # run_script('valid_clusters_9_table.py', table_args)


    import sys ; sys.exit()

    # Run valid_clusters_10_legend.py
    find_and_copy_files('*_valid_clusters_table.xlsx', Path().cwd(), 'valid_clusters_tables_and_legend')
    legend_args = [
        '-p', 'valid_clusters_tables_and_legend'
    ]
    run_script('valid_clusters_10_legend.py', legend_args)

    #################### Would this be helpful? #####################################
    # Aggregate *_ABA.nii.gz files and the rgba.txt file into a new directory #### WB
    # find_and_copy_files('*_ABA.nii.gz', Path().cwd(), '3D_brain_images')
    # Need to rename the rgba.txt file so it has the same name as the corresponding NIfTI file


if __name__ == '__main__':
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    print_cmd_and_times(main)()


# Scripts 4 and 7 are more general (also relevant to rstats). --> rename
