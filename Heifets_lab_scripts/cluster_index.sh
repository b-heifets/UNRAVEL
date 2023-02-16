#!/bin/bash
# (c) Daniel Ryskamp Rijsketic, Boris Heifets @ Stanford University, 2022-2023

if [ $# == 0 ] || [ $1 == "help" ]; then
  echo ' 
Run from ./glm/stats image to make cluster index:
cluster_index.sh <path/stat_image.nii.gz> <stat thresh (e.g. 0.99)> <min cluster size in voxels>
' 
  exit 1
fi

echo " " ; echo "Running cluster_index.sh for $1" ; echo " " 

image=$(basename $1)
image_path=$(dirname $1)
cd $image_path
results="${image%???????}"_statThr"$2"_MinCluster"$3"
mkdir -p "$results"
cp $image $results

#make clusters from stats image
if [ ! -f $results/"$results"_cluster_index.nii.gz ]; then 
  echo " " ; echo "  Making cluster index for $results" ; echo Start: $(date) ; echo " "
  cluster --in=$image --thresh=$2 --oindex="$results"_cluster_index --olmax="$results"_lmax.txt --osize="$results"_cluster_size --othresh="$results"_thresh --minextent=$3 > "$results"_cluster_info.txt 
  cat "$results"_cluster_info.txt #print cluster info in terminal
  mv "$results"_cluster_index.nii.gz $results
  mv "$results"_thresh.nii.gz $results
  mv "$results"_cluster_size.nii.gz $results
  mv "$results"_lmax.txt $results
  mv "$results"_cluster_info.txt $results
  echo " " ; echo "  Made cluster index for $results" ; echo End: $(date) ; echo " "
else 
  echo " " ; echo "  Cluster index exists for $results, skipping"  ; echo " " 
fi

#Daniel Ryskamp Rijsketic 05/10/2022 - 05/23/2022 & 07/27/22
