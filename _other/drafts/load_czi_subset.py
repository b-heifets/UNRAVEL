#!/usr/bin/env python3

import argparse
import czifile
import numpy as np
from datetime import datetime

from unravel.core.argparse_utils import SuppressMetavar, SM


def parse_args():
    parser = argparse.ArgumentParser(description='Load subset of 3D image.czi', formatter_class=SuppressMetavar)
    parser.add_argument('-i', '--input', help='<./img.czi>', action=SM)
    parser.add_argument('-c', '--channel', type=int, help='Channel number (e.g., 0 for 1st channel, 1 for 2nd channel, ...)', action=SM)
    parser.add_argument('-x', '--x_start', type=int, default=0, action=SM, help='Pixel where slicing starts in x')
    parser.add_argument('-X', '--x_end', type=int, default=None, action=SM, help='Pixel where slicing ends in x')
    parser.add_argument('-y', '--y_start', type=int, default=0, action=SM)
    parser.add_argument('-Y', '--y_end', type=int, default=None, action=SM)
    parser.add_argument('-z', '--z_start', type=int, default=0, action=SM)
    parser.add_argument('-Z', '--z_end', type=int, default=None, action=SM)
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

def main():
    args = parse_args() 

    czi_subset = load_czi_subset(args.input, args.channel, args.x_start, args.x_end, args.y_start, args.y_end, args.z_start, args.z_end)

if __name__ == '__main__':
    main()


"Daniel Rijsketic 08/29/2023 (Heifets lab)"