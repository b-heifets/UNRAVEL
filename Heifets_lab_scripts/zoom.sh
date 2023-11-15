#!/bin/bash
if [ $# == 0 ] || [ "$1" == "help" ]; then
  echo "
zoom.sh <path/image> <x res or m> <y res or m> <z res or m> <new xyz voxel size> [dtype]

res = resolution (i.e., voxel size in microns)

Enter m to get res from metadata

This script makes it easier to use the zoom function from SciPy
https://docs.scipy.org/doc/scipy/reference/generated/scipy.ndimage.zoom.html

Example of additional zoom arg:
', order=0'  #default order = 1 (bilinear), whereas 0 = nearest neighbor

Output: <path/image_*um>
"
  exit 1
fi

echo " " ; echo "Running zoom.sh $@ " ; echo " " 

if [ ! -f "${1::-7}"_"$5"um.nii.gz ]; then 
  echo " " ; echo "  Resampling ${1%*/} to $5 um resolution" ; echo " " 
  python3 /usr/local/miracl/miracl/seg/zoom.py $1 $2 $3 $4 $5 $6
  echo " " ; echo "  Resampled "${1::-7}"_"$5"um.nii.gz" ; echo " " 
else 
  echo " " ; echo ""${1::-7}"_"$5"um.nii.gz exists, skipping" ; echo " " 
fi 

#Daniel Ryskamp Rijsketic 2/13/23-3/2/23 (Heifets lab)
