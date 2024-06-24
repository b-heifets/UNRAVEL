#!/usr/local/fsl/fslpython/envs/fslpython/bin/python

import argparse
import os
import subprocess
from glob import glob

from unravel.core.argparse_utils import SuppressMetavar, SM

def parse_args():
    parser = argparse.ArgumentParser(description='Run fsleyes with given display range and files.', formatter_class=SuppressMetavar)
    parser.add_argument('-i', '--inputs', help='List of .nii.gz files to view or if empty all .nii.gz files in the current directory.', nargs='*', default=None)
    parser.add_argument('-min', '--display_range_min', help='Minimum display range value.', default=0, type=float)
    parser.add_argument('-max', '--display_range_max', help='Maximum display range value.', required=True, type=float)
    parser.add_argument('-a', '--atlas', help='path/atlas.nii.gz (Default: /usr/local/unravel/atlases/gubra/gubra_ano_combined_25um.nii.gz)', default='/usr/local/unravel/atlases/gubra/gubra_ano_combined_25um.nii.gz', action=SM)
    return parser.parse_args()

def main():
    args = parse_args()
    
    # If no files are specified, use all .nii.gz files in the current directory
    if not args.inputs:
        image_files = glob('*.nii.gz')
    else:
        # Clean file names from quotes and get basename
        image_files = [os.path.basename(file.replace("'", "").replace('"', '')) for file in args.inputs]
    
    # Build the fsleyes command
    fsleyes_command = ['fsleyes']
    for image_file in image_files:
        fsleyes_command.extend([image_file, '-dr', str(args.display_range_min), str(args.display_range_max)])
    fsleyes_command.extend([args.atlas, '-ot', 'label', '-o'])
    
    # Run fsleyes command
    subprocess.run(fsleyes_command)

if __name__ == "__main__":
    main()
