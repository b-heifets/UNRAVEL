#!/bin/bash
# (c) Daniel Ryskamp Rijsketic, Boris Heifets @ Stanford University, 2022-2023

if [ $# == 0 ] || [ $1 == "help" ]; then
  echo "
Run this from sample folder:
ABAcluster.sh <./clusters_folder/cluster_masks/sample??_native_cluster_*.nii.gz>

Multiplies warped atlas and cluster mask to convert intensities of clusters into regional intensities.

Inputs: ./reg_final/sample??_native_gubra_ano_split.nii.gz (from full_res_alas.sh) ./cluster_masks/sample??_native_cluster_i.nii.gz (from cluster masks)
Outputs: ./ABAcluster_masks/ABA_sample??_native_cluster_i.nii.gz
" 
  exit 1
fi

sample=$(basename $PWD)

#native_ABA=$(find $PWD -name native_gubra_ano_split_10um_clar_downsample.nii.gz -print -quit) #only first result
native_ABA=$PWD/reg_final/"$sample"_native_gubra_ano_split.nii.gz

clusters_folder_path="${1%/*/*}"
image=$(basename $1)

echo " " ; echo "Running ABAcluster.sh from $PWD" ; echo " " 

mkdir -p $clusters_folder_path/ABAcluster_masks

if [ ! -f $clusters_folder_path/ABAcluster_masks/ABA_$image ]; then 
  echo " " ; echo "  Making $clusters_folder_path/ABAcluster_masks/ABA_$image " ; echo Start: $(date) ; echo " " 
  /usr/local/miracl/depends/Fiji.app/ImageJ-linux64 --ij2 -macro convert_to_ABA_intensities $native_ABA#$1
  mv $1.nii $clusters_folder_path/ABAcluster_masks/ABA_${image%???}
  gzip -f -9 $clusters_folder_path/ABAcluster_masks/ABA_${image%???}
else 
  echo " " ; echo "  "$sample"_ABAconsensus.nii.gz exists, skipping" ; echo " " 
fi


#Daniel Ryskamp Rijsketic 07/01/22 & 07/06/22 (Heifets lab)
