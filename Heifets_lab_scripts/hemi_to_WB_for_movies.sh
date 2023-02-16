#!/bin/bash 
# (c) Daniel Ryskamp Rijsketic, Boris Heifets @ Stanford University, 2022-2023

if [ "$1" == "help" ]; then 
  echo '
hemi_to_WB_for_movies.sh <cluster_index_in_hemisphere.nii.gz in working dir>

Outputs: 
sig_clusters_WB.nii.gz (bilateral version of cluster index w/ ABA colors)
sig_clusters_WB_histo.csv (histogram for determining what regions are present for making DSI LUT)
'
  exit 1
fi

echo " " ; echo "Running mirror.sh $@ from $PWD" ; echo " " 

input=$(basename $1)

mirror.sh $input

fslmaths $input -add mirror_$input sig_clusters_WB.nii.gz 

fslmaths sig_clusters_WB.nii.gz -bin sig_clusters_WB.nii.gz 

cp /usr/local/miracl/atlases/ara/gubra/gubra_ano_split_25um.nii.gz $PWD/
cp /usr/local/miracl/atlases/ara/gubra/gubra_ano_combined_25um.nii.gz $PWD/
cp /usr/local/miracl/atlases/ara/gubra/gubra_ano_25um_bin.nii.gz $PWD/

fslmaths gubra_ano_split_25um.nii.gz -mul sig_clusters_WB.nii.gz sig_clusters_WB.nii.gz  

fslstats sig_clusters_WB.nii.gz -H 21142 0 21142 > sig_clusters_WB_histo.csv


#Daniel Ryskamp Rijsketic 07/01/22, 08/03/22, 08/25/22, 10/21/22 (Heifets Lab)
