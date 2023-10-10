#!/usr/bin/env python3

import argparse
import unravel_utils as unrvl
from glob import glob
from pathlib import Path
from rich import print
from time import sleep

def parse_args():
    parser = argparse.ArgumentParser(description='Process sample folders w/ example resample function') #
    parser.add_argument('--dir_pattern', help='Pattern for folders in working dir to process (Default: sample??)', default='sample??', metavar='') 
    parser.add_argument('--dir_list', help='Folders to process in working dir (e.g., sample01 sample02) (Default: process sample??) ', nargs='+', default=None, metavar='') 
    parser.add_argument('-i', '--input', help='<path/image.czi> (Optional: process just this image)', metavar='') 
    parser.add_argument('-c', '--channel', type=int, help='Channel for czi file (Default: 0 for autofluo)', default=0, metavar='')
    parser.epilog = "example_script_for_processing_samples_w_comments.py -i ./sample01/sample01.czi -c 1" 
    return parser.parse_args() 

@unrvl.print_func_name_args_times
def example_function(sample_dir, args=None): 

    czi_path = Path(glob(f"{sample_dir}/*.czi")[0]).resolve() 
    if czi_path: 
        img = unrvl.load_czi_channel(czi_path, args.channel) 
        print(f"  [default]Image shape: {img.shape}\n  Channel: {args.channel}\n")

    sleep(2) 

@unrvl.print_cmd_and_times
def main():
    args = parse_args() 

    output_path = Path("reg_input", f"output.nii.gz")

    if args.input and not output_path.exists():
        unrvl.process_single_input(args.input, example_function, args) 
        return 

    # Process all samples in the working directory or only those specified if args.input is not provided.
    unrvl.process_samples_in_dir(example_function, sample_list=args.dir_list, sample_dirs_pattern=args.dir_pattern, output=output_path, args=args) 

if __name__ == '__main__': 
    main() 
