#!/usr/bin/env python3

""" 
Use ``cluster_summary`` from UNRAVEL to aggregate and analyze cluster validation data from ``cluster_validation``.

Usage if running directly after ``cluster_validation``:
-------------------------------------------------------
    cluster_summary -c <path/config.ini> -e <exp dir paths> -cvd 'psilocybin_v_saline_tstat1_q<asterisk>' -vd <path/vstats_dir> -sk <path/sample_key.csv> --groups <group1> <group2> -hg <higher_group> -v

Note: 
    - The current working directory should not have other directories when running this script for the first time. Directories from cluster_org_data are ok though.

Usage if running after ``cluster_validation`` and ``cluster_org_data``:
-----------------------------------------------------------------------
    cluster_summary -c <path/config.ini> -sk <path/sample_key.csv> --groups <group1> <group2> -hg <higher_group> -v

Note:
    - For the second usage, the ``-e``, ``-cvd``, and ``-vd`` arguments are not needed because the data is already in the working directory.
    - Only process one comparison at a time. If you have multiple comparisons, run this script separately for each comparison in separate directories.
    - Then aggregate the results as needed (e.g. to make a legend with all relevant abbeviations, copy the .xlsx files to a central location and run ``cluster_legend``).

The current working directory should not have other directories when running this script for the first time. Directories from cluster_org_data are ok though.

``cluster_summary`` runs commands in this order:
    - ``cluster_org_data``
    - ``cluster_group_data``
    - ``utils_prepend``
    - ``cluster_stats``
    - ``cluster_index``
    - ``cluster_brain_model``
    - ``cluster_table``
    - ``cluster_prism``
    - ``cluster_legend``

The sample_key.csv file should have the following format:
    dir_name,condition
    sample01,control
    sample02,treatment

If you need to rerun this script, delete the following directories and files in the current working directory:
find . -name _valid_clusters -exec rm -rf {} \; -o -name cluster_validation_summary_t-test.csv -exec rm -f {} \; -o -name cluster_validation_summary_tukey.csv -exec rm -f {} \; -o -name 3D_brains -exec rm -rf {} \; -o -name valid_clusters_tables_and_legend -exec rm -rf {} \; -o -name _valid_clusters_stats -exec rm -rf {} \;

If you want to aggregate CSVs for sunburst plots of valid clusters, run this in a root directory:
find . -name "valid_clusters_sunburst.csv" -exec sh -c 'cp {} ./$(basename $(dirname $(dirname {})))_$(basename {})' \;

Likewise, you can aggregate raw data (raw_data_for_t-test_pooled.csv), stats (t-test_results.csv), and prism files (cell_density_summary_for_valid_clusters.csv). 
"""

import argparse
import nibabel as nib
import numpy as np
import subprocess
from pathlib import Path
from rich import print
from rich.traceback import install

from unravel.cluster_stats.org_data import cp
from unravel.core.argparse_utils import SuppressMetavar, SM
from unravel.core.config import Configuration 
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg, load_config
from unravel.utilities.aggregate_files_recursively import find_and_copy_files


def parse_args():
    parser = argparse.ArgumentParser(formatter_class=SuppressMetavar)
    parser.add_argument('-c', '--config', help='Path to the config.ini file. Default: unravel/cluster_stats/cluster_summary.ini', default=Path(__file__).parent / 'cluster_summary.ini', action=SM)

    # cluster_org_data -e <list of experiment directories> -cvd '*' -td <target_dir> -vd <path/vstats_dir> -v
    parser.add_argument('-e', '--exp_paths', help='List of experiment dir paths w/ sample?? dirs to process. (needed for cluster_org_data)', nargs='*', action=SM)
    parser.add_argument('-cvd', '--cluster_val_dirs', help='Glob pattern matching cluster validation output dirs to copy data from (relative to ./sample??/clusters/; for cluster_org_data', action=SM) 
    parser.add_argument('-vd', '--vstats_path', help='path/vstats_dir (dir vstats was run from) to copy p val, info, and index files (for cluster_org_data)', action=SM)

    # utils_prepend -c <path/sample_key.csv> -f -r
    parser.add_argument('-sk', '--sample_key', help='path/sample_key.csv w/ directory names and conditions (for utils_prepend)', action=SM)

    # cluster_stats --groups <group1> <group2>
    parser.add_argument('--groups', help='List of group prefixes. 2 groups --> t-test. >2 --> Tukey\'s tests (The first 2 groups reflect the main comparison for validation rates; for cluster_stats)',  nargs='+')
    parser.add_argument('-cp', '--condition_prefixes', help='Condition prefixes to group related data (optional for cluster_stats)',  nargs='*', default=None, action=SM)
    parser.add_argument('-hg', '--higher_group', help='Specify the group that is expected to have a higher mean based on the direction of the p value map', required=True)

    parser.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)
    parser.epilog = __doc__
    return parser.parse_args()

# TODO: Could add a progress bar that advances after each subdir, but need to adapt running of the first few scripts for this. Include check for completeness (all samples have csvs [from both hemis]). Review outputs and output folders and consider consolidating them. Could make cells vs. labels are arg. Could add a raw data output organized for the SI table. # The valid cluster sunburst could have the val dir name and be copied to a central location
# TODO: Consider moving find_and_copy_files() to unravel/unravel/utils.py
# TODO: Move cell vs. label arg from config back to argparse and make it a required arg to prevent accidentally using the wrong metric
# TODO: Add a reset option to delete all output files and directories from the current working directory
# TODO: Aggregate CSVs for valid cluster sunburst plots
# TODO: Sort the overall valid cluster sunburst csv 


def run_script(script_name, script_args):
    """Run a command/script using subprocess that respects the system's PATH and captures output."""
    # Convert all script arguments to string
    script_args = [str(arg) for arg in script_args]
    command = [script_name] + script_args
    subprocess.run(command, check=True, stdout=None, stderr=None)


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    cfg = load_config(args.config)
    
    # Run cluster_org_data
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
        run_script('cluster_org_data', org_data_args)

    # Run cluster_group_data
    if args.verbose:
        run_script('cluster_group_data', ['-v'])
    else:
        run_script('cluster_group_data', [])

    # Run utils_prepend
    if args.sample_key:
        prepend_conditions_args = [
            '-sk', args.sample_key,
            '-f',
            '-r'
        ]
        if args.verbose:
            prepend_conditions_args.append('-v')
        run_script('utils_prepend', prepend_conditions_args)

    # Run cluster_stats
    if args.groups:
        stats_args = [
            '--groups', *args.groups,
            '-alt', cfg.stats.alternate,
            '-pvt', cfg.org_data.p_val_txt, 
            '-hg', args.higher_group
        ]
        if args.condition_prefixes:
            stats_args.append(['-cp', *args.condition_prefixes])
        if args.verbose:
            stats_args.append('-v')
        run_script('cluster_stats', stats_args)

    dsi_dir = Path().cwd() / '3D_brains'
    dsi_dir.mkdir(parents=True, exist_ok=True) 
    
    # Iterate over all subdirectories in the current working directory and run the following scripts
    for subdir in [d for d in Path.cwd().iterdir() if d.is_dir() and d.name != '3D_brains' and d.name != 'valid_clusters_tables_and_legend']:

        # Load all .csv files in the current subdirectory
        csv_files = list(subdir.glob('*.csv'))
        if not csv_files:
            continue  # Skip directories with no CSV files

        stats_output = subdir / '_valid_clusters_stats'
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
            print(f"    No valid cluster index file found in {subdir}. Skipping...")
            continue  # Skip this directory and move to the next

        valid_clusters_index_dir = subdir / cfg.index.valid_clusters_dir
        
        if len(valid_cluster_ids) == 0: 
            print(f"    No clusters were valid for {subdir}. Skipping...")
            continue

        # Run cluster_index
        index_args = [
            '-ci', rev_cluster_index_path,
            '-ids', *valid_cluster_ids,
            '-vcd', valid_clusters_index_dir,
            '-a', cfg.index.atlas,
            '-scsv', cfg.index.sunburst_csv_path,
            '-in', cfg.index.info_csv_path
        ]
        if cfg.index.output_rgb_lut:
            index_args.append('-rgb')
        if args.verbose:
            index_args.append('-v')
        run_script('cluster_index', index_args)

        # Run cluster_brain_model
        valid_cluster_index_path = valid_clusters_index_dir / str(rev_cluster_index_path.name).replace('.nii.gz', f'_{cfg.index.valid_clusters_dir}.nii.gz')
        brain_args = [
            '-i', valid_cluster_index_path,
            '-ax', cfg.brain.axis,
            '-s', cfg.brain.shift,
            '-sa', cfg.brain.split_atlas,
            '-csv', cfg.brain.csv_path
        ]
        if cfg.brain.mirror: 
            brain_args.append('-m')
        if args.verbose:
            brain_args.append('-v')
        run_script('cluster_brain_model', brain_args)

        # Aggregate files from cluster_brain_model
        if cfg.brain.mirror: 
            find_and_copy_files(f'*{cfg.index.valid_clusters_dir}_ABA_WB.nii.gz', subdir, dsi_dir)
        else:
            find_and_copy_files(f'*{cfg.index.valid_clusters_dir}_ABA.nii.gz', subdir, dsi_dir)
        find_and_copy_files(f'*{cfg.index.valid_clusters_dir}_rgba.txt', subdir, dsi_dir)

        # Run cluster_table
        table_args = [
            '-vcd', valid_clusters_index_dir,
            '-t', cfg.table.top_regions,
            '-pv', cfg.table.percent_vol,
            '-csv', cfg.index.info_csv_path,
            '-rgb', cfg.table.rgbs
        ]
        if args.verbose:
            table_args.append('-v')
        run_script('cluster_table', table_args)
        find_and_copy_files('*_valid_clusters_table.xlsx', subdir, Path().cwd() / 'valid_clusters_tables_and_legend')
    
        if Path('valid_clusters_tables_and_legend').exists():

            # Run cluster_prism
            valid_cluster_ids_sorted_txt = valid_clusters_index_dir / 'valid_cluster_IDs_sorted_by_anatomy.txt'
            if valid_cluster_ids_sorted_txt.exists():
                with open(valid_cluster_ids_sorted_txt, 'r') as f:
                    valid_cluster_ids_sorted = f.read().split()
            else: 
                valid_cluster_ids_sorted = valid_cluster_ids
            if len(valid_cluster_ids_sorted) > 0:
                prism_args = [
                    '-ids', *valid_cluster_ids_sorted,
                    '-p', subdir,
                ]
                if args.verbose:
                    prism_args.append('-v')
                run_script('cluster_prism', prism_args)
            else:
                print(f"\n    No valid cluster IDs found for {subdir}. Skipping cluster_prism...\n")

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

        # Run cluster_legend
        if Path('valid_clusters_tables_and_legend').exists():
            legend_args = [
                '-p', 'valid_clusters_tables_and_legend',
                '-csv', cfg.index.info_csv_path
            ]
            run_script('cluster_legend', legend_args)

    verbose_end_msg()


if __name__ == '__main__':
    main()