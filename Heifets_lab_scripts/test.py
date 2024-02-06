#!/usr/bin/env python3

import argparse
from argparse import RawTextHelpFormatter
from rich.traceback import install
from unravel_config import Configuration
from unravel_img_io import load_image_metadata_from_txt
from unravel_utils import print_cmd_and_times


def parse_args():
    parser = argparse.ArgumentParser(description='Load metadata from text file', formatter_class=RawTextHelpFormatter)
    parser.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)
    return parser.parse_args()

def main():    
    metadata = load_image_metadata_from_txt()
    print(f'\n{metadata=}\n')


if __name__ == '__main__': 
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    print_cmd_and_times(main)()