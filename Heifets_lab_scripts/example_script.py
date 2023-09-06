#!/usr/bin/env python3

import argparse
import os
from time import sleep
import unravel_utils as unrvl

def parse_args():
    parser = argparse.ArgumentParser(description='Process sample folders')
    parser.add_argument('-i', '--input', help='<path/image>', metavar='')
    parser.add_argument('-d', '--ds_factor', type=int, help='Downsampling factor', metavar='')
    parser.add_argument('-r', '--resample', type=int, help='Resample to this resolution (microns)', metavar='')
    return parser.parse_args()

@unrvl.function_decorator(message="")
def downsample(sample_folder_path, input, ds_factor):
    sleep(1)
    print(f"\n  Loading {input} and downsampling {ds_factor}x")

@unrvl.function_decorator(message="")
def resample(sample_folder_path, input, resample):
    sleep(1)
    print(f"\n  Resample {input} to {resample} micron resolution")

@unrvl.main_function_decorator(pattern="sample??")
def main(sample_folder_path):
    args = parse_args() 

    downsample(sample_folder_path, args.input, args.ds_factor)
    resample(sample_folder_path, args.input, args.resample)

if __name__ == '__main__':
    main()

"Daniel Rijsketic 08/31/2023 (Heifets lab)"