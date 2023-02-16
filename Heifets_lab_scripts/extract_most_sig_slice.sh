#!/bin/bash
# (c) Daniel Ryskamp Rijsketic, Boris Heifets @ Stanford University, 2022-2023

if [ $# == 0 ] || [ $1 == "help" ]; then
  echo " 
Run to extract slice from volumes cropped based on clusters:  
get_most_sig_slice_from_crop.sh <./path/image_to_extract_slice_from.nii.gz> <./path/crop_stats_thr_sample??_native_cluster_*.nii.gz_IntDen-Max_most-sig-slice.csv>
" 
  exit 1
fi

echo " " ; echo "Running extract_most_sig_slice.sh for $1 " ; echo " "

image=$(basename $1) 
path=$(dirname $1)

if [ ! -f $path/most_sig_slice_${image%???????}.tif ]; then 

  echo " " ; echo "  Extracting most sig slice from $image" ; echo Start: $(date) ; echo " "

  #Extract most sig slice
  most_sig_slice=$(cat $2)
  
  /usr/local/miracl/depends/Fiji.app/ImageJ-linux64 --ij2 -macro extract_most_sig_slice $1#$most_sig_slice

  mv $path/most_sig_slice_${image%???}.tif $path/most_sig_slice_${image%???????}.tif

  echo " " ; echo "  Extracted most sig slice from $image" ; echo End: $(date) ; echo " "

fi 


#Daniel Ryskamp Rijsketic 05/31/22 (Heifets lab)




