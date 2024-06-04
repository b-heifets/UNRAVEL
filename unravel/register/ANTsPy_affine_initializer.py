#!/usr/bin/env python3

import argparse
import os
import ants
from contextlib import redirect_stderr
from multiprocessing import Process, Queue
from pathlib import Path
from rich import print
from rich.traceback import install

from unravel.core.argparse_utils import SM, SuppressMetavar


def parse_args():
    parser = argparse.ArgumentParser(description='Run ants.affine_initializer as a seperate process to kill it after a time out', formatter_class=SuppressMetavar)
    parser.add_argument('-f', '--fixed_img', help='path/fixed_image.nii.gz (e.g., autofl_50um_masked_fixed_reg_input.nii.gz)', required=True, action=SM)
    parser.add_argument('-m', '--moving_img', help='path/moving_image.nii.gz (e.g., template)', required=True, action=SM)
    parser.add_argument('-o', '--output', help='path/init_tform_py.nii.gz', required=True, action=SM)
    parser.add_argument('-t', '--time_out', help='Duration in seconds to allow this script to run. Default: 10', default=10, type=int, action=SM)
    parser.epilog = """This also allows for suppressing error messages. 

Usage: ANTsPy_affine_initialized.py -f reg_outputs/autofl_50um_masked_fixed_reg_input.nii.gz -m /usr/local/unravel/atlases/gubra/gubra_template_25um.nii.gz -o reg_outputs/ANTsPy_init_tform.nii.gz -t 10
with open(os.devnull, 'w') as devnull:

    
Python usage: 
import subprocess
import os

command = ['python', 'ANTsPy_affine_initialized.py', '-f', 'reg_outputs/autofl_50um_masked_fixed_reg_input.nii.gz', '-m', '/usr/local/unravel/atlases/gubra/gubra_template_25um.nii.gz', '-o', 'reg_outputs/ANTsPy_init_tform.nii.gz', '-t', '10' ]
with open(os.devnull, 'w') as devnull:
    subprocess.run(command, stderr=devnull)
"""
    return parser.parse_args()

def affine_initializer_wrapper(fixed_image_path, moving_image_path, reg_outputs_path, queue):

    # Load the fixed and moving images
    fixed_image = ants.image_read(str(fixed_image_path))
    moving_image = ants.image_read(str(moving_image_path))

    # Suppress stderr
    with open(os.devnull, 'w') as f, redirect_stderr(f):
        # Perform affine initialization
        txfn = ants.affine_initializer(
            fixed_image=fixed_image,
            moving_image=moving_image,
            search_factor=1, # Degree of increments on the sphere to search
            radian_fraction=1, # Defines the arc to search over
            use_principal_axis=False, # Determines whether to initialize by principal axis
            local_search_iterations=500, # Number of iterations for local optimization at each search point
            txfn=reg_outputs_path # Path to save the transformation matrix
        )
        # Use a queue to pass the result back to the main process
        queue.put(txfn)

def run_with_timeout(fixed_image, moving_image, reg_outputs_path, timeout):

    # Queue for inter-process communication
    queue = Queue()

    # Create and start the process
    p = Process(target=affine_initializer_wrapper, args=(fixed_image, moving_image, reg_outputs_path, queue))
    p.start()

    # Wait for the process to complete or timeout
    p.join(timeout)

    if p.is_alive():
        # If the process is still alive after the timeout, terminate it
        p.terminate()
        p.join()
        # print(f"Process timed out after {timeout} seconds and was terminated.")
        return None
    else:
        # If the process completed within the timeout, get the result
        return queue.get()


def main(): 
    args = parse_args()
    
    # Run the affine initializer with a specified timeout (in seconds)
    run_with_timeout(args.fixed_img, args.moving_img, args.output, timeout=args.time_out)
    if not Path(args.output).exists():
        print("The affine initializer did not complete successfully w/ 10 second timeout. Lengthen the timeout period of ANTsPy_affine_initializer.py (.e.g, 180 seconds)")


if __name__ == '__main__': 
    install()
    main()