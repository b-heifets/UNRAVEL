#!/bin/bash

if [ $# == 0 ] || [ "$1" == "-h" ] || [ "$1" == "--help" ] || [ "$1" == "help" ]; then
  echo 'invert_nii.sh <path/image.nii.gz>'
  exit 1
fi

image=$(echo $1 | sed "s/['\"]//g")

echo " " ; echo "invert_nii.sh $@" ; echo " " 

/usr/local/miracl/depends/Fiji.app/ImageJ-linux64 --ij2 -macro invert_nii $image > /dev/null 2>&1

gzip -9 -f $image.nii

mv $image.nii.gz $image

#Daniel Ryskamp Rijsketic 10/05/23 (Heifets lab)

