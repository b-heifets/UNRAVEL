#!/usr/bin/env python3

# library imports in alphabetical order (can use the pythong library black to format scripts automatically)
import argparse
from pathlib import Path
from rich import print
from rich.live import Live

from unravel.core.argparse_utils import SuppressMetavar, SM
from unravel.core.config import Configuration
from unravel.core.img_io import load_3D_img
from unravel.core.utils import print_cmd_and_times, print_func_name_args_times, initialize_progress_bar, get_samples

from time import sleep # for example_function

def parse_args(): # This function defines the arguments that can be passed to the script
    parser = argparse.ArgumentParser(description='Process sample folder(s) w/ a *.czi, tif series, or .nii.gz  image', formatter_class=SuppressMetavar) # formatter_class allows for multiline epilog
    parser.add_argument('-p', '--pattern', help='Pattern for folders to process. If no matches, use current dir. Default: sample??', default='sample??', action=SM)
    parser.add_argument('--dirs', help='List of folders to process. Overrides --pattern', nargs='*', default=None, action=SM) # SM is a custom action that suppresses the metavar in the help message
    parser.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False) # action='store_true' means that if the flag is provided, the value is set to True
    parser.epilog = """
Run prep_reg.py from the experiment directory containing sample?? folders or a sample?? folder.
inputs: ...
outputs: ..."""
    return parser.parse_args()


# Example of a function that is only used in this script
@print_func_name_args_times()
def example_function(img_path):
    """Load a 3D image in the sample folder (first *.czi, *.tif, or *.nii.gz match), print shape and resolution, and mimic processing time"""
    img, xy_res, z_res = load_3D_img(img_path, return_res=True) # This loads the autofluo image from the .czi file (channel 0 by default). Returns ndarray and resolution in microns
    print(f"\n    [default]Image shape: {img.shape}, xy_res: {xy_res}, z_res: {z_res}\n")
    sleep(0.5) # This simulates processing time
    return img # This returns the image to main()


def main(): # This is the main function that is called at the bottom of the script
    args = parse_args()
    samples = get_samples(args.dirs, args.pattern) # get_samples() returns a list of sample directories
    progress, task_id = initialize_progress_bar(len(samples), "[red]Processing samples...")
    with Live(progress): # This starts the progress bar
        for sample in samples: # This iterates through each sample directory
            example_function(Path(sample).resolve()) # This calls the example_function() function defined above, passing the path to sample directory as an argument (e.g., the sample dir could contain a .czi file)
            progress.update(task_id, advance=1) # This updates the progress bar


if __name__ == '__main__': # This is the standard way to call the main() function
    from rich.traceback import install
    install() # This enables rich to print a stylized traceback if there is an error (easier to read than the default traceback)
    args = parse_args() # args is a Namespace object that contains the arguments passed to the script
    Configuration.verbose = args.verbose  # Set verbosity for all decorators in unravel_utils.py
    print_cmd_and_times(main)() # This calls the main() function and prints the command and execution time