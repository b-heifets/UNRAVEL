#!/usr/bin/env python3

import argparse
from argparse import RawTextHelpFormatter
from pathlib import Path
from rich.live import Live
from rich.traceback import install
from unravel_config import Configuration
from unravel_img_tools import load_3D_img
from unravel_utils import get_samples, initialize_progress_bar, print_cmd_and_times


def parse_args():
    parser = argparse.ArgumentParser(description='Load image (.czi, .nii.gz, or tif series) to get metadata and save to ./parameters/metadata.txt', formatter_class=RawTextHelpFormatter)
    parser.add_argument('-p', '--pattern', help='Pattern for folders to process. If no matches, use current dir. Default: sample??', default='sample??', metavar='')
    parser.add_argument('--dirs', help='List of folders to process. Overrides --pattern', nargs='*', default=None, metavar='')
    parser.add_argument('-i', '--input', help='path/img.czi, path/img.nii.gz, or path/tif_dir', metavar='')
    parser.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)
    parser.epilog = """Run this from a sample?? folder. 
Loading a full image automatically gets the metadata and saves it to ./parameters/metadata.txt if it does not already exist. 
Pass in xy_res and z_res if they are not obtainable from the metadata."""    
    return parser.parse_args()


def main(): 

    if Path(args.input).is_absolute():
        load_3D_img(args.input, desired_axis_order="xyz", xy_res=args.xy_res, z_res=args.z_res, return_metadata=True, save_metadata=True)
        return

    samples = get_samples(args.dirs, args.pattern)

    if samples == ['.']:
        samples[0] = Path.cwd().name

    progress, task_id = initialize_progress_bar(len(samples), "[red]Processing samples...")
    with Live(progress):
        for sample in samples:
            cwd = Path(".").resolve()
            sample_path = Path(sample).resolve() if sample != cwd.name else Path().resolve()

            # Define input image path
            img_path = Path(sample_path, args.input)

            load_3D_img(img_path, return_metadata=True, save_metadata=True)

            progress.update(task_id, advance=1)



if __name__ == '__main__': 
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    print_cmd_and_times(main)()