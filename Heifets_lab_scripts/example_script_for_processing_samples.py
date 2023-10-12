#!/usr/bin/env python3

import argparse
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
    parser.add_argument('-c', '--channel', help='Channel of the czi image to load. Default: 0 for autofluo', type=int, default=0, metavar='')
    parser.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)
    parser.epilog = "Add extra info or example command here"
    return parser.parse_args()

@print_func_name_args_times
def img_shape(img): 
    print(f"  [default]Image shape: {img.shape}\n")
    sleep(1) 

def main():    
    args = parse_args()

    samples = get_samples(args.dirs, args.pattern)

    decorated_load_czi_channel = print_func_name_args_times(load_czi_channel)

    progress = get_progress_bar(total_tasks=len(samples))
    task_id = progress.add_task("  [red]Processing samples...", total=len(samples))
    with Live(progress):
        for sample in samples:
            czi_files = glob(f"{sample}/*.czi")
            if czi_files:
                czi_path = Path(czi_files[0]).resolve() 
                img = decorated_load_czi_channel(czi_path, args.channel)
                img_shape(img)
            else:
                print(f"  [red1 bold].czi file not found for sample: {sample}")
            progress.update(task_id, advance=1)

if __name__ == '__main__': 
    from rich.traceback import install
    install()
    
    args = parse_args()
    print_cmd_and_times.verbose = args.verbose
    print_func_name_args_times.verbose = args.verbose
    
    print_cmd_and_times(main)()