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
from unravel_utils import print_cmd_and_times, initialize_progress_bar, get_samples


def parse_args():
    parser = argparse.ArgumentParser(description='Aggregates csv outputs from validate_clusters.py', formatter_class=SuppressMetavar)
    parser.add_argument('-e', '--exp_paths', help='List of experiment dir paths w/ sample?? dirs to process.', nargs='*', default=None, action=SM)
    parser.add_argument('-p', '--pattern', help='Pattern for sample?? dirs. Use cwd if no matches.', default='sample??', action=SM)
    parser.add_argument('-d', '--dirs', help='List of sample?? dir names or paths to dirs to process', nargs='*', default=None, action=SM)
    parser.add_argument('-i', '--input', help='Glob pattern matching cluster validation output dirs to copy data from', required=True, default=None, action=SM)
    parser.add_argument('-dt', '--density_type', help='Type of density data to aggregate (cell [default] or label).', default='cell', action=SM)
    parser.add_argument('-o', '--output', help='path/dir to copy results. If omitted, copy data to the cwd', default=None, action=SM)
    parser.add_argument('-v', '--verbose', help='Increase verbosity.', action='store_true', default=False)
    parser.epilog = """Usage: valid_clusters_org_data.py -e <list of experiment directories> -i '*' -o <output_dir> -v
"""
    return parser.parse_args()


def main():

    target_dir = Path(args.output)
    target_dir.mkdir(exist_ok=True, parents=True)

    samples = get_samples(args.dirs, args.pattern, args.exp_paths)
    
    progress, task_id = initialize_progress_bar(len(samples), "[red]Processing samples...")
    with Live(progress):
        for sample in samples:

            sample_path = Path(sample).resolve() if sample != Path.cwd().name else Path.cwd()

            clusters_path = sample_path / 'clusters'
            if clusters_path.exists():
                for item in clusters_path.glob(args.input):
                    if item.is_dir():
                        new_dir = target_dir / item.name
                        new_dir.mkdir(parents=True, exist_ok=True)
                        src_file = item / f'{args.density_type}_density_data.csv'
                        if src_file.exists():
                            dest_file = new_dir / f'{sample_path.name}__{args.density_type}_density_data__{item.name}.csv'
                            shutil.copy(src_file, dest_file)
                            if args.verbose:
                                print(f"Copied {src_file} to {dest_file}")

            progress.update(task_id, advance=1)


if __name__ == '__main__':
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    print_cmd_and_times(main)()