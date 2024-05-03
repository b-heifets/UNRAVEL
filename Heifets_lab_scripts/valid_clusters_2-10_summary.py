#!/usr/bin/env python3

import argparse
import runpy
import sys
from pathlib import Path
from rich import print
from rich.traceback import install
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
    parser.add_argument('-csv', '--sample_key_csv', help='path/sample_key.csv w/ directory names and conditions', required=True, action=SM)

    # valid_clusters_5_stats.py --groups <group1> <group2>
    parser.add_argument('--groups', help='List of group prefixes. 2 groups --> t-test. >2 --> Tukey\'s tests (The first 2 groups reflect the main comparison for validation rates)',  nargs='+', required=True)
    parser.add_argument('-cp', '--condition_prefixes', help='Condition prefixes to group data (e.g., see valid_clusters_5_stats.py)',  nargs='*', default=None, action=SM)

    # valid_clusters_6_index.py -ci path/rev_cluster_index.nii.gz -ids 1 2 3
    # parser.add_argument('-ci', '--cluster_idx', help='Path to the reverse cluster index NIfTI file.', required=True, action=SM)

    parser.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)
    return parser.parse_args()


def run_script(script_path, script_args):
    """Run a script with arguments using runpy."""
    # Temporarily replace sys.argv
    original_argv = sys.argv
    sys.argv = [script_path] + script_args
    runpy.run_path(script_path, run_name="__main__")
    # Restore original sys.argv
    sys.argv = original_argv


def main(config):
    # Load settings for each script from the config file
    cfg = Config(args.config)
    
    # valid_clusters_2_org_data.py
    pattern = cfg.org_data.pattern
    density_type = cfg.org_data.density_type
    p_val_txt = cfg.org_data.p_val_txt

    # valid_clusters_4_prepend_conditions.py
    file = cfg.prepend_conditions.file
    recursive = cfg.prepend_conditions.recursive

    # valid_clusters_5_stats.py
    alternate = cfg.stats.alternate
    
    # valid_clusters_6_index.py
    output = cfg.index.output # valid_clusters output directory
    atlas = cfg.index.atlas
    output_rgb_lut = cfg.index.output_rgb_lut

    # valid_clusters_7_table.py
    top_regions = cfg.table.top_regions
    percent_vol = cfg.table.percent_vol

    # valid_clusters_8_table.py
    top_regions = cfg.prism.top_regions
    percent_vol = cfg.prism.percent_vol

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

    

if __name__ == '__main__':
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    print_cmd_and_times(main)()