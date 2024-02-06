#!/usr/bin/env python3

import argparse
from argparse import RawTextHelpFormatter
from pathlib import Path
from rich.live import Live
from rich.traceback import install
from unravel_config import Configuration
from unravel_img_tools import load_3D_img, resolve_relative_path
from unravel_utils import get_samples, initialize_progress_bar, print_cmd_and_times


def parse_args():
    parser = argparse.ArgumentParser(description='Load full res image (.czi, .nii.gz, or tif series) to get metadata and save to ./parameters/metadata.txt', formatter_class=RawTextHelpFormatter)
    parser.add_argument('-p', '--pattern', help='Pattern for folders to process. If no matches, use current dir. Default: sample??', default='sample??', metavar='')
    parser.add_argument('--dirs', help='List of folders to process. Overrides --pattern', nargs='*', default=None, metavar='')
    parser.add_argument('-i', '--input', help='path/full_res_img.extension.', required=True, metavar='')
    parser.add_argument('-m', '--metad_path', help='path/metadata.txt. Default: parameters/metadata.txt', default="parameters/metadata.txt", metavar='')
    parser.add_argument('-x', '--xy_res', help='xy resolution in um', type=float, default=None, metavar='')
    parser.add_argument('-z', '--z_res', help='z resolution in um', type=float, default=None, metavar='')
    parser.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)
    parser.epilog = """Run this from an experiment or sample?? folder if using a relative input path. 

inputs: .czi, .nii.gz, or tif series (path should be relative to ./sample??)
outputs: ./parameters/metadata.txt (path should be relative to ./sample??)

Pass in xy_res and z_res if they are not obtainable from the metadata."""    
    return parser.parse_args()

def print_metadata(metadata_path):
    with open(metadata_path, "r") as f:
        contents = f.read()
    print(f'\n{contents}\n')

def main(): 

    samples = get_samples(args.dirs, args.pattern)

    progress, task_id = initialize_progress_bar(len(samples), "[red]Processing samples...")
    with Live(progress):
        for sample in samples:
            sample_path = Path(sample).resolve() if sample != Path.cwd().name else Path().resolve()

            # Resolve path to image
            img_path = resolve_relative_path(sample_path, rel_path_or_glob_pattern=args.input)

            # Resolve path to metadata file
            metadata_path = resolve_relative_path(sample_path, rel_path_or_glob_pattern=args.metad_path, make_parents=True)

            if metadata_path.exists():
                print(f'\n\n{metadata_path} exists. Skipping...')
                print_metadata(metadata_path)
            else: 
                # Load image and save metadata to file
                if img_path.exists():
                    load_3D_img(img_path, desired_axis_order="xyz", xy_res=args.xy_res, z_res=args.z_res, return_metadata=True, save_metadata=metadata_path)
                    print(f'\n\n{metadata_path}:')
                    print_metadata(metadata_path)
                else:
                    print(f"    [red1]No match found for {args.input} in {sample_path}. Skipping...")



            progress.update(task_id, advance=1)


if __name__ == '__main__': 
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    print_cmd_and_times(main)()