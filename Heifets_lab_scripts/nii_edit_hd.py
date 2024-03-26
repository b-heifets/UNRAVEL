#!/usr/bin/env python3

import argparse
import subprocess
import nrrd
import nibabel as nib
import numpy as np
from rich.traceback import install
from argparse_utils import SuppressMetavar, SM
from unravel_config import Configuration
from unravel_utils import print_cmd_and_times, print_func_name_args_times

def parse_args():
    parser = argparse.ArgumentParser(description='.nii.gz and print header using nibabel.', formatter_class=SuppressMetavar)
    parser.add_argument('-i', '--input', help='path/img.nii.gz', required=True, action=SM)
    # parser.add_argument('-o', '--output', help='path/img.nii.gz', required=True, action=SM)
    parser.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', action='store_true', default=False)
    return parser.parse_args()




def main():

   
    # Load .nii.gz 
    nii_img = nib.load(args.input)
    print(nii_img.header)


if __name__ == '__main__':
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    print_cmd_and_times(main)()
