#!/usr/bin/env python3

import argparse
import subprocess
from rich.traceback import install
from argparse_utils import SuppressMetavar, SM
from unravel_config import Configuration
from unravel_utils import print_cmd_and_times, print_func_name_args_times

def parse_args():
    parser = argparse.ArgumentParser(description='Reorient an .nii.gz to RAS and zero out global position in sform and qform.', formatter_class=SuppressMetavar)
    parser.add_argument('-i', '--input', help='path/img.nii.gz', required=True, action=SM)
    parser.add_argument('-o', '--output', help='path/img.nii.gz', required=True, action=SM)
    parser.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)
    return parser.parse_args()


@print_func_name_args_times()
def run_command(command):
    """Run a command using subprocess."""
    result = subprocess.run(command, shell=True, text=True, capture_output=True) # text=True to decode stdout/stderr to str
    if result.stderr:
        raise Exception("Error executing command: ", result.stderr)
    return result.stdout.strip() # Remove leading/trailing whitespaces

@print_func_name_args_times()
def reorient_image(input_image, output_image):
    # Reorient the image to standard space
    run_command(f"fslreorient2std {input_image} {output_image}")
    
    # Get the sform matrix from the output image
    sform = run_command(f"fslorient -getsform {output_image}")
    
    # Parse the sform to a list, assume it's space separated
    sform_values = sform.split()
    
    # Set the global position elements (4th column in the 4x4 matrix) to 0, keeping other values unchanged
    sform_values[3] = "0"
    sform_values[7] = "0"
    sform_values[11] = "0"
    
    # Reconstruct the sform command with modified values
    sform_command = f"fslorient -setsform {' '.join(sform_values)} {output_image}"
    run_command(sform_command)
    
    # Set the qform using the same values as the sform
    qform_command = f"fslorient -setqform {' '.join(sform_values)} {output_image}"
    run_command(qform_command)


def main():
    reorient_image(args.input, args.output)
    print("\n    Image reorientation and header update complete.\n")

if __name__ == '__main__':
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    print_cmd_and_times(main)()