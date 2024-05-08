#!/usr/bin/env python3

import argparse
import nibabel as nib
import numpy as np
import subprocess
from pathlib import Path
from rich import print
from rich.traceback import install
from aggregate_files_w_recursive_search import find_and_copy_files
from unravel_config import Config

from argparse_utils import SuppressMetavar, SM
from unravel_config import Configuration 
from unravel_utils import print_cmd_and_times
from valid_clusters_org_data import cp

def parse_args():
    parser = argparse.ArgumentParser(description='Aggregates and analyzes cluster validation data from validate_clusters.py', formatter_class=SuppressMetavar)
    parser.add_argument('-c', '--config', help='Path to the config.ini file. Default: valid_clusters_summary.ini', default=Path(__file__).parent / 'valid_clusters_summary.ini', action=SM)

    # valid_clusters_org_data.py -e <list of experiment directories> -cvd '*' -td <target_dir> -vd <path/vstats_dir> -v
    parser.add_argument('-e', '--exp_paths', help='List of experiment dir paths w/ sample?? dirs to process. (needed for *org_data.py)', nargs='*', action=SM)
    parser.add_argument('-cvd', '--cluster_val_dirs', help='Glob pattern matching cluster validation output dirs to copy data from (relative to ./sample??/clusters/; for *org_data.py', action=SM) 
    parser.add_argument('-vd', '--vstats_path', help='path/vstats_dir ( dir vstats.py was run from) to copy p val, info, and index files (for *org_data.py)', action=SM)

    # prepend_conditions.py -c <path/sample_key.csv> -f -r
    parser.add_argument('-sk', '--sample_key', help='path/sample_key.csv w/ directory names and conditions (for prepend_conditions.py)', action=SM)

    # valid_clusters_stats.py --groups <group1> <group2>
    parser.add_argument('--groups', help='List of group prefixes. 2 groups --> t-test. >2 --> Tukey\'s tests (The first 2 groups reflect the main comparison for validation rates; for *stats.py)',  nargs='+')
    parser.add_argument('-cp', '--condition_prefixes', help='Condition prefixes to group related data (optional for *stats.py)',  nargs='*', default=None, action=SM)

    parser.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)
    parser.epilog = """ Usage: valid_clusters_summary.py -c <path/config.ini> -e <exp dir paths> -cvd '*' -vd <path/vstats_dir> -sk <path/sample_key.csv> --groups <group1> <group2> -v

The current working directory should not have other directories when running this script for the first time. Directories from valid_clusters_org_data.py are ok though.

Runs scripts in this order:
    - valid_clusters_org_data.py
    - valid_clusters_group_bilateral_data.py
    - prepend_conditions.py
    - valid_clusters_stats.py
    - valid_clusters_index.py
    - 3D_brain.py
    - valid_clusters_prism.py
    - valid_clusters_table.py
    - valid_clusters_legend.py

The sample_key.csv file should have the following format:
    dir_name,condition
    sample01,control
    sample02,treatment

"""
    return parser.parse_args()

# TODO: Could add a progress bar that advances after each subdir, but need to adapt running of the first few scripts for this. Include check for completeness (all samples have csvs [from both hemis]). Review outputs and output folders and consider consolidating them. Could make cells vs. labels are arg. 


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

    # Run valid_clusters_org_data.py
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
        run_script('valid_clusters_org_data.py', org_data_args)

    # Run valid_clusters_group_bilateral_data.py
    if args.verbose:
        run_script('valid_clusters_group_bilateral_data.py', ['-v'])
    else:
        run_script('valid_clusters_group_bilateral_data.py', [])

    # Run prepend_conditions.py
    if args.sample_key:
        prepend_conditions_args = [
            '-sk', args.sample_key,
            '-f',
            '-r'
        ]
        if args.verbose:
            prepend_conditions_args.append('-v')
        run_script('prepend_conditions.py', prepend_conditions_args)

    # Run valid_clusters_stats.py
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
        run_script('valid_clusters_stats.py', stats_args)

    dsi_dir = Path().cwd() / '3D_brains'
    dsi_dir.mkdir(parents=True, exist_ok=True) 
    
    # Iterate over all subdirectories in the current working directory and run the following scripts
    for subdir in [d for d in Path.cwd().iterdir() if d.is_dir() and d.name != '3D_brains' and d.name != 'valid_clusters_tables_and_legend']:

        # Load all .csv files in the current subdirectory
        csv_files = list(subdir.glob('*.csv'))
        if not csv_files:
            continue  # Skip directories with no CSV files

        stats_output = subdir / '_cluster_validation_info'
        valid_clusters_ids_txt = stats_output / 'valid_cluster_IDs_t-test.txt' if len(args.groups) == 2 else stats_output / 'valid_cluster_IDs_tukey.txt'

        if valid_clusters_ids_txt.exists():
            with open(valid_clusters_ids_txt, 'r') as f:
                valid_cluster_ids = f.read().split()

        rev_cluster_index_path = subdir / f'{subdir.name}_rev_cluster_index.nii.gz'
        if not Path(rev_cluster_index_path).exists():
            rev_cluster_index_path = subdir / f'{subdir.name}_rev_cluster_index_RH.nii.gz'
        if not Path(rev_cluster_index_path).exists():        
            rev_cluster_index_path = subdir / f'{subdir.name}_rev_cluster_index_LH.nii.gz'
        if not Path(rev_cluster_index_path).exists():
            rev_cluster_index_path = next(subdir.glob("*rev_cluster_index*"))

        if rev_cluster_index_path is None:
            print(f"No valid cluster index file found in {subdir}. Skipping...")
            continue  # Skip this directory and move to the next

        valid_clusters_index_dir = subdir / cfg.index.valid_clusters_dir
        
        # Run valid_clusters_index.py
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
        run_script('valid_clusters_index.py', index_args)

        # Run 3D_brain.py
        valid_cluster_index_path = valid_clusters_index_dir / str(rev_cluster_index_path.name).replace('.nii.gz', f'_{cfg.index.valid_clusters_dir}.nii.gz')
        brain_args = [
            '-i', valid_cluster_index_path,
            '-ax', cfg.brain.axis,
            '-s', cfg.brain.shift,
            '-sa', cfg.brain.split_atlas
        ]
        if cfg.brain.mirror: 
            brain_args.append('-m')
        if args.verbose:
            brain_args.append('-v')
        run_script('3D_brain.py', brain_args)

        # Aggregate files from 3D_brains.py
        if cfg.brain.mirror: 
            find_and_copy_files(f'*{cfg.index.valid_clusters_dir}_ABA_WB.nii.gz', subdir, dsi_dir)
        else:
            find_and_copy_files(f'*{cfg.index.valid_clusters_dir}_ABA.nii.gz', subdir, dsi_dir)
        find_and_copy_files(f'*{cfg.index.valid_clusters_dir}_rgba.txt', subdir, dsi_dir)

        # Run valid_clusters_prism.py
        prism_args = [
            '-ids', *valid_cluster_ids,
            '-p', subdir,
        ]
        if cfg.prism.save_all:
            prism_args.append('-sa')
        if args.verbose:
            prism_args.append('-v')
        run_script('valid_clusters_prism.py', prism_args)

        # Run valid_clusters_table.py
        table_args = [
            '-vcd', valid_clusters_index_dir,
            '-t', cfg.table.top_regions,
            '-pv', cfg.table.percent_vol
        ]
        if args.verbose:
            table_args.append('-v')
        run_script('valid_clusters_table.py', table_args)

        find_and_copy_files('*_valid_clusters_table.xlsx', subdir, Path().cwd() / 'valid_clusters_tables_and_legend')

    # Copy the atlas and binarize it for visualization in DSI studio
    dest_atlas = dsi_dir / Path(cfg.index.atlas).name
    if not dest_atlas.exists():
        cp(cfg.index.atlas, dsi_dir)
        atlas_nii = nib.load(dest_atlas)
        atlas_img = np.asanyarray(atlas_nii.dataobj, dtype=atlas_nii.header.get_data_dtype()).squeeze()
        atlas_img[atlas_img > 0] = 1
        atlas_img.astype(np.uint8)
        atlas_nii_bin = nib.Nifti1Image(atlas_img, atlas_nii.affine, atlas_nii.header)
        atlas_nii_bin.header.set_data_dtype(np.uint8)
        nib.save(atlas_nii_bin, str(dest_atlas).replace('.nii.gz', '_bin.nii.gz'))

    # Run valid_clusters_legend.py
   
    legend_args = [
        '-p', 'valid_clusters_tables_and_legend'
    ]
    run_script('valid_clusters_legend.py', legend_args)


if __name__ == '__main__':
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    print_cmd_and_times(main)()