#!/usr/bin/env python3

import argparse
from config import Configuration
from glob import glob
from pathlib import Path
from rich import print
from rich.live import Live
from time import sleep
from unravel_img_tools import load_czi_channel
from unravel_utils import print_cmd_and_times, print_func_name_args_times, get_progress_bar, get_samples


def parse_args():
    parser = argparse.ArgumentParser(description='Process sample folder(s) w/ a *.czi file')
    parser.add_argument('--dirs', help='List of folders to process. If not provided, --pattern used for matching dirs to process. If no matches, the current directory is used.', nargs='*', default=None, metavar='')
    parser.add_argument('-p', '--pattern', help='Pattern for folders in the working dir to process. Default: sample??', default='sample??', metavar='')
    parser.add_argument('-i', '--input', help='Optional: path/image.czi. If provided, the parent folder acts as the sample folder and other samples are not processed.', metavar='')
    parser.add_argument('-c', '--channel', help='Channel of the czi image to load. Default: 0 for autofluo', type=int, default=0, metavar='')
    parser.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)
    parser.epilog = "Add extra info (e.g., outputs) and/or example command here"
    return parser.parse_args()


@print_func_name_args_times(arg_index_for_basename=0)
def example_function(czi_path, channel):
    """Load a czi file, process its image, and return the image."""
    img = load_czi_channel(czi_path, channel)
    print(f"\n    [default]Image shape: {img.shape}\n")
    sleep(3) 
    return img

def main():    
    if args.input:
        czi_path = Path(args.input).resolve()
        example_function(czi_path, args.channel)
        return

    samples = get_samples(args.dirs, args.pattern)

    progress = get_progress_bar(total_tasks=len(samples))
    task_id = progress.add_task("[red]Processing samples...", total=len(samples))
    with Live(progress):
        for sample in samples:
            czi_files = glob(f"{sample}/*.czi")
            if czi_files:
                czi_path = Path(czi_files[0]).resolve() 
                example_function(czi_path, args.channel)
            else:
                print(f"    [red1 bold].czi file not found for sample: {sample}")
            progress.update(task_id, advance=1)


if __name__ == '__main__': 
    from rich.traceback import install
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    print_cmd_and_times(main)()