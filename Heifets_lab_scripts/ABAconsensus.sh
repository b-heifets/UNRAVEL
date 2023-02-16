#!/bin/bash
# (c) Daniel Ryskamp Rijsketic, Boris Heifets @ Stanford University, 2021-2023

if [ $# != 0 ]; then
  echo " 
Run from sample folder:
ABAconsensus.sh

Multiplies warped atlas and consensus.tif to convert intensities of cells into regional intensities. 

Input ./reg_final/sample??_native_gubra_ano_split.nii.gz ./consensus/sample??_consensus.nii.gz 
Outputs: ./consensus/"$sample"_ABAconsensus.nii.gz
" 
  exit 1
fi

sample=$(basename $PWD)

#native_ABA=$(find $PWD -name native_gubra_ano_split_10um_clar_downsample.nii.gz -print -quit) #only first result
native_ABA=$PWD/reg_final/"$sample"_native_gubra_ano_split.nii.gz


echo " " ; echo "Running ABAconsensus.sh from $PWD" ; echo " " 

if [ ! -f $PWD/consensus/"$sample"_ABAconsensus.nii.gz ]; then 
  echo " " ; echo "  Making $PWD/consensus/"$sample"_ABAconsensus.nii.gz " ; echo Start: $(date) ; echo " " 
  /usr/local/miracl/depends/Fiji.app/ImageJ-linux64 --ij2 -macro convert_to_ABA_intensities $native_ABA#$PWD/consensus/"$sample"_consensus.nii.gz
  mv $PWD/consensus/"$sample"_consensus.nii.gz.nii $PWD/consensus/"$sample"_ABAconsensus.nii
  gzip -f -9 $PWD/consensus/"$sample"_ABAconsensus.nii
  echo " " ; echo "  Made $PWD/consensus/"$sample"_ABAconsensus.nii.gz " ; echo End: $(date) ; echo " " 
else 
  echo " " ; echo "  "$sample"_ABAconsensus.nii.gz exists, skipping" ; echo " " 
fi


#Daniel Ryskamp Rijsketic 08/26/2021 & 05/10/22-07/06/22 & 09/30/22
