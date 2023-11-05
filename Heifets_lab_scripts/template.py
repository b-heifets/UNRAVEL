#!/usr/bin/env python3

import argparse
from unravel_config import Configuration
from rich.live import Live
from rich import print
from unravel_img_tools import load_image_and_metadata
from unravel_utils import print_cmd_and_times, print_func_name_args_times, initialize_progress_bar, get_samples

from time import sleep


def parse_args():
    parser = argparse.ArgumentParser(description='<Script purpose>')
    parser.add_argument('--dirs', help='List of folders to process. If not provided, --pattern used for matching dirs to process. If no matches, the current directory is used.', nargs='*', default=None, metavar='')
    parser.add_argument('-p', '--pattern', help='Pattern for folders in the working dir to process. Default: sample??', default='sample??', metavar='')
    parser.add_argument('-i', '--input', help='# of seconds to sleep to mimic processing each sample', default=3, metavar='')
    parser.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)
    parser.epilog = "Usage: <> ; Outputs: <> "
    return parser.parse_args()


@print_func_name_args_times(arg_index_for_basename=0)
def example_function(sample, seconds):
    print(f"\n    [default]Processing sample: {sample}\n")
    sleep(seconds) 


def main():    
    samples = get_samples(args.dirs, args.pattern)

    progress, task_id = initialize_progress_bar(len(samples), "[red]Processing samples...")
    with Live(progress):
        for sample in samples:
            example_function(sample, args.input)
            progress.update(task_id, advance=1)


if __name__ == '__main__': 
    from rich.traceback import install
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    print_cmd_and_times(main)()

    