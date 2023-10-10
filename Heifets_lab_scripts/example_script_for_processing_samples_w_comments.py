#!/usr/bin/env python3

import argparse # Organize imports alphabetically
import unravel_utils as unrvl
from glob import glob
from pathlib import Path
from rich import print
from time import sleep

def parse_args():
    parser = argparse.ArgumentParser(description='Process sample folders w/ example resample function') # Add a description to the help message
    parser.add_argument('--dir_pattern', help='Pattern for folders in working dir to process (Default: sample??)', default='sample??', metavar='') # metavar'' simplifies the help message
    parser.add_argument('--dir_list', help='Folders to process in working dir (e.g., sample01 sample02) (Default: process sample??) ', nargs='+', default=None, metavar='') # nargs='+' allows multiple arguments
    parser.add_argument('-i', '--input', help='<path/image.czi> (Optional: process just this image)', metavar='') 
    parser.add_argument('-c', '--channel', type=int, help='Channel for czi file (Default: 0 for autofluo)', default=0, metavar='') # default=0 sets the default value for the argument
    parser.epilog = "example_script_for_processing_samples_w_comments.py -i ./sample01/sample01.czi -c 1" # Add an example or more info to the end of the help message for complicated scripts
    return parser.parse_args() # Return the parsed arguments

@unrvl.print_func_name_args_times # Decorator to print function name, arguments, and duration
def example_function(sample_dir, args=None): # sample_dir is the path to the sample folder, args are the parsed arguments

    # Load autofluo image
    czi_path = Path(glob(f"{sample_dir}/*.czi")[0]).resolve() # Get the path to the czi file
    if czi_path: # If the czi file exists
        img = unrvl.load_czi_channel(czi_path, args.channel) # Load the image
        print(f"  [default]Image shape: {img.shape}\n  Channel: {args.channel}\n") # Default coloring for text

    sleep(2) # Sleep for 2 seconds to simulate processing time

@unrvl.print_cmd_and_times # Decorator to print command (example_script_for_processing_samples_w_comments.py *args) and duration
def main():
    args = parse_args() # Parse the arguments

    # Define output path relative to sample folder for skipping samples that have already been processed
    output_path = Path("reg_input", f"output.nii.gz")

    # If the input flag is provided, process only that file and exit the function
    if args.input: # If the input flag is provided
        unrvl.process_single_input(args.input, example_function, args) # args are passed to example_function()
        return # Exit the function

    # Process all samples in the working directory or only those specified.
    # If running script from in a sample folder, just process that sample.
    unrvl.process_samples_in_dir(example_function, sample_list=args.dir_list, sample_dirs_pattern=args.dir_pattern, output=output_path, args=args) # loops through each sample folder and runs example_function()

if __name__ == '__main__': # If the script is run directly (not imported)
    main() # Run the main function
