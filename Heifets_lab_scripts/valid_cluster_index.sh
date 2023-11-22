#!/bin/bash

if [ $# == 0 ] || [ $1 == "help" ] || [ $1 == "-h" ] || [ $1 == "--help" ]; then
  echo " 
valid_cluster_index.sh <[path/]rev_cluster_index.nii.gz> <output_suffix & dir name (e.g., valid_clusters> <space separated list of valid_clusters>

Outputs: ./valid_clusters_<suffix>/

Output data type set to char (8-bit), so change to short if > 255 clusters
" 
  exit 1
fi

rev_cluster_index=$(echo $1 | sed "s/['\"]//g")
rev_cluster_index_basename=${rev_cluster_index##*/}
suffix=$(echo $2 | sed "s/['\"]//g")
valid_cluster_array=($(echo "${@:3}" | sed "s/['\"]//g"))

output=$(echo ${rev_cluster_index_basename%???????}_${2}.nii.gz)

mkdir -p $2
cp $rev_cluster_index $2/

cd $2

echo "${valid_cluster_array[@]}" > valid_clusters.txt

for c in ${valid_cluster_array[@]}; do
  fslmaths $rev_cluster_index_basename -thr $c -uthr $c cluster_${c} -odt char
done

# Make blank image
fslmaths cluster_${valid_cluster_array[0]} -sub cluster_${valid_cluster_array[0]} $output -odt char

# Add clusters to make valid_cluster_index and cp each cluster label to folder for sunburst.sh
for i in cluster_*; do
  fslmaths $output -add $i $output -odt char  
  mkdir -p ${i%???????}
  mv $i ${i%???????}/
  cd ${i%???????}
  # Make sunburst csv for each valid cluster
  sunburst.sh $PWD/${i}
  cd ..
done

# Make subnbust csv for valid_cluster_index
sunburst.sh $PWD/$output

cd .. 


#Daniel Ryskamp Rijsketic 10/27/2023 (Heifets lab)
