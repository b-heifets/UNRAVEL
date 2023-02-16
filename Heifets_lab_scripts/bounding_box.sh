#!/bin/bash
# (c) Daniel Ryskamp Rijsketic, Boris Heifets @ Stanford University, 2022-2023

if [ $# == 0 ] || [ "$1" == "help" ]; then
  echo '
Run this from sample folder:  
bounding_box.sh <./clusters_folder
/cluster_masks/sample??_native_cluster_*.nii.gz>

Make text file with bounding box info for cluster
'
  exit 1
fi

echo " " ; echo "Running bounding_box.sh $@ from $PWD" ; echo " " 

image=$(basename $1)
path=$(dirname $1)
parent_dir="${path%/*}" 
clusters_folder=$(basename $parent_dir)

mkdir -p $parent_dir/bounding_boxes

txt="$parent_dir/bounding_boxes/"${image::-7}"_fslstats_w.txt"

#delete txt file if exists and is empty
if [ -f $txt ]; then if [[ -z $(grep '[^[:space:]]' $txt) ]] ; then rm $txt ; fi ; fi

if [ ! -f $txt ]; then
  #Get <xmin>#<xsize>#<ymin>#<ysize>#<zmin>#<zsize> 
  echo " " ; echo "  Making "${image::-7}"_fslstats_w.txt" ; echo Start: $(date) ; echo " " 
  fslstats $1 -w > $txt 
  echo " " ; echo "  Made "${image::-7}"_fslstats_w.txt" ; echo End: $(date) ; echo " "
else
  echo " " ; echo "  $txt exists, skipping" ; echo " " 
fi


#Daniel Ryskamp Rijsketic 05/05/2022 & 05/13/2022 & 05/17/22 (Heifets lab)

