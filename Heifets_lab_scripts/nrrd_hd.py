#!/usr/bin/env python3



import nrrd
import sys

# Path to your NRRD file
nrrd_file_path = sys.argv[1]

print(f'{nrrd_file_path=}')

# Read NRRD file and its header
data, header = nrrd.read(nrrd_file_path)

# Print the header to see metadata
print(header)

# Specifically, check for 'space' or 'space directions' to understand orientation
if 'space' in header:
    print("Space (orientation):", header['space'])
if 'space directions' in header:
    print("Space directions (orientation vectors):", header['space directions'])