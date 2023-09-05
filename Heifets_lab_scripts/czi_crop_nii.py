#!/usr/bin/env python3

import argparse
import czifile
import nibabel as nib
import numpy as np
from datetime import datetime
from pathlib import Path
from unravel_utils import print_cmd

def parse_args():
    parser = argparse.ArgumentParser(description='Load subset of 3D image.czi')
    parser.add_argument('-i', '--input', help='<./img.czi>', metavar='')
    parser.add_argument('-c', '--channel', type=int, help='Channel number (e.g., 0 for 1st channel, 1 for 2nd channel, ...)', metavar='')
    parser.add_argument('-x', '--x_start', type=int, default=0, metavar='', help='Pixel where slicing starts in x')
    parser.add_argument('-X', '--x_end', type=int, default=None, metavar='', help='Pixel where slicing ends in x')
    parser.add_argument('-y', '--y_start', type=int, default=0, metavar='')
    parser.add_argument('-Y', '--y_end', type=int, default=None, metavar='')
    parser.add_argument('-z', '--z_start', type=int, default=0, metavar='')
    parser.add_argument('-Z', '--z_end', type=int, default=None, metavar='')
    return parser.parse_args()

def load_czi_subset(input, channel, x_start, x_end, y_start, y_end, z_start, z_end):
    with czifile.CziFile(input) as czi:
        print("  Loading image.czi starting at " +datetime.now().strftime("%H:%M:%S"))
        czi_array = czi.asarray()
        print("  czi.asarray() finished. Squeezing and transposing at " +datetime.now().strftime("%H:%M:%S"))
        czi_subset = czi_array[..., channel, z_start:z_end, y_start:y_end, x_start:x_end, :]
        czi_subset_squeezed = np.squeeze(czi_subset)
        czi_subset = np.transpose(czi_subset_squeezed, (2, 1, 0))
        print("  Squeezing and transposing finished at " +datetime.now().strftime("%H:%M:%S") + "\n")    
    return czi_subset

def save_as_nifti(ndarray, output):
    print("  Saving as .nii.gz starting at " +datetime.now().strftime("%H:%M:%S"))
    img = nib.Nifti1Image(ndarray, np.eye(4))
    img.to_filename(output)
    print("  Finished saving at " +datetime.now().strftime("%H:%M:%S") + "\n")

def main():
    args = parse_args() 
    print_cmd()

    czi_subset = load_czi_subset(args.input, args.channel, args.x_start, args.x_end, args.y_start, args.y_end, args.z_start, args.z_end)

    # Save cropped ndarray as nifti
    input_path = Path(args.input)
    output = input_path.parent / f'{input_path.stem}_{args.x_start}_{args.x_end}_{args.y_start}_{args.y_end}_{args.z_start}_{args.z_end}.nii.gz'
    save_as_nifti(czi_subset, output)

if __name__ == '__main__':
    main()


"Daniel Rijsketic 08/29/2023 (Heifets lab)"