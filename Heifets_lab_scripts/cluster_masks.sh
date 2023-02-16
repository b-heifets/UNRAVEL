#!/bin/bash
# (c) Daniel Ryskamp Rijsketic, Boris Heifets @ Stanford University, 2022-2023

#make cluster masks index from sample??_native_cluster_index.nii.gz 

if [ $# == 0 ] || [ $1 == "help" ]; then
  echo "
Run this from sample folder:
cluster_masks.sh <./clusters_folder/native_cluster_index/native_rev_cluster_index.nii.gz> <./clusters_folder/cluster_masks/sample??_image_cluster_x.nii.gz> <cluster #>
"
  exit 1
fi

path=$(dirname $1)
parent_dir="${path%/*}" 
clusters_folder=$(basename $parent_dir)
sample=$(basename $PWD)

echo " " ; echo "Running cluster_masks.sh $@ from $sample" ; echo " " 

if [ ! -d $PWD/clusters/$clusters_folder/cluster_masks ]; then mkdir $PWD/clusters/$clusters_folder/cluster_masks ; fi

if [ ! -f $2 ]; then 
  echo " " ; echo "  Making $2" ; echo Start: $(date) ; echo " " 
  fslmaths -dt char $1 -thr $3 -uthr $3 -bin $2 -odt char
  echo " " ; echo "  Made $2" ; echo End: $(date) ; echo " " 
else
  echo " " ; echo "  $2 exists, skipping" ; echo " "  
fi
     

#Daniel Ryskamp Rijsketic 05/13/2022-05/20/22 (Heifets lab)
