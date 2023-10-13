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
    parser.add_argument('-p', '--pattern', help='Pattern for folders in the working dir to process. Default: sample??', default='sample??', metavar='') # default='sample??' is the default value if no argument is provided
    parser.add_argument('-i', '--input', help='Optional: path/image.czi. If provided, the parent folder acts as the sample folder and other samples are not processed.', metavar='')
    parser.add_argument('-c', '--channel', help='Channel of the czi image to load. Default: 0 for autofluo', type=int, default=0, metavar='') # metavar='' cleans up the help message
    parser.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False) # action='store_true' means that if the flag is provided, the value is set to True
    parser.epilog = "Add extra info (e.g., outputs) and/or example command here"
    return parser.parse_args()


# Example of a function that is only used in this script
@print_func_name_args_times(arg_index_for_basename=0)
def example_function(czi_path, channel): # czi_path and channel are passed to this function from main()
    """Load a czi file, process its image, and return the image."""
    img = load_czi_channel(czi_path, channel) # This loads the autofluo image from the .czi file
    print(f"  [default]Image shape: {img.shape}\n") # This prints the shape of the image
    sleep(1) # This simulates processing time
    return img # This returns the image to main()


def main(): # This is the main function that is called at the bottom of the script

    if args.input: # If the --input flag is provided, load the image and print its shape
        czi_path = Path(args.input).resolve() # This gets the absolute path to the .czi file even if the path is relative
        example_function(czi_path, args.channel) # This calls the example_function() function defined above
        return # This exits the main() function

    samples = get_samples(args.dirs, args.pattern) # get_samples() returns a list of sample directories

    progress = get_progress_bar(total_tasks=len(samples)) # This creates a progress bar object
    task_id = progress.add_task("  [red]Processing samples...", total=len(samples)) # This adds a task to the progress bar
    with Live(progress): # This starts the progress bar
        for sample in samples: # This iterates through each sample directory
            czi_files = glob(f"{sample}/*.czi") # This returns a list of .czi files in the sample directory
            if czi_files: # If there are .czi files in the sample directory
                czi_path = Path(czi_files[0]).resolve() # This gets the path to the first .czi file
                example_function(czi_path, args.channel) # This calls the example_function() function defined above
            else:
                print(f"  [red1 bold].czi file not found for sample: {sample}")
            progress.update(task_id, advance=1) # This updates the progress bar


if __name__ == '__main__': # This is the standard way to call the main() function
    from rich.traceback import install
    install() # This enables rich to print a stylized traceback if there is an error (easier to read than the default traceback)
    args = parse_args() # args is a Namespace object that contains the arguments passed to the script
    Configuration.verbose = args.verbose  # Set verbosity for all decorators in unravel_utils.py
    print_cmd_and_times(main)() # This calls the main() function and prints the command and execution time