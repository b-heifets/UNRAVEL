#!/usr/bin/env python3

import argparse
from rich import print
from rich.live import Live
from rich.traceback import install
from unravel_config import Configuration
from unravel_utils import print_cmd_and_times, print_func_name_args_times, initialize_progress_bar, get_samples

def parse_args():
    parser = argparse.ArgumentParser(description='<Script purpose>')
    parser.add_argument('-p', '--pattern', help='Pattern for folders to process. If no matches, use current dir. Default: sample??', default='sample??', metavar='')
    parser.add_argument('--dirs', help='List of folders to process. Overrides --pattern', nargs='*', default=None, metavar='')
    parser.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)
    parser.epilog = "Usage: <> ; Outputs: <> "
    return parser.parse_args()


@print_func_name_args_times()
def example_function(sample):
    from time import sleep
    print(f"\n    [default]Processing sample: {sample}\n")
    sleep(1) 


def main():    
    samples = get_samples(args.dirs, args.pattern)

    progress, task_id = initialize_progress_bar(len(samples), "[red]Processing samples...")
    with Live(progress):
        for sample in samples:
            example_function(sample)
            progress.update(task_id, advance=1)


if __name__ == '__main__': 
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    print_cmd_and_times(main)()