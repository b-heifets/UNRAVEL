#!/bin/bash
# (c) Daniel Ryskamp Rijsketic, Boris Heifets @ Stanford University, 2021-2023

if [ "$1" == "help" ]; then  
  echo '
Run this from experiment folder:
consensus_tif_to_nii.sh [leave blank to process all samples or enter sample?? separated by spaces]
'
  exit 1
fi

echo " " ; echo "Running consensus_tif_to_nii.sh $@ from $PWD" ; echo " " 

if [ $# -gt 0 ]; then 
  sample_array=($(echo "${@:1}" | sed "s/['\"]//g"))
  sample_array=($(for i in ${sample_array[@]}; do echo $(basename $i) ; done)) 
else 
  sample_array=(sample??) 
fi

for sample in ${sample_array[@]}; do
  cd $sample

  if [ -f consensus/"$sample"_consensus.tif.nii ] && [ ! -f consensus/"$sample"_consensus.nii.gz ]; then 
    mv consensus/"$sample"_consensus.tif.nii consensus/"$sample"_consensus.nii
    gzip -9 -f consensus/"$sample"_consensus.nii
  fi 

  if [ -f consensus/consensus.tif ] && [ ! -f consensus/"$sample"_consensus.nii.gz ]; then 
    mv consensus/consensus.tif consensus/"$sample"_consensus.tif
  fi

  if [ -f consensus/"$sample"_consensus.tif ] && [ ! -f consensus/"$sample"_consensus.nii.gz ]; then 
    /usr/local/miracl/depends/Fiji.app/ImageJ-linux64 --ij2 -macro tif_to_nii $PWD/consensus/"$sample"_consensus.tif
    mv consensus/"$sample"_consensus.tif.nii consensus/"$sample"_consensus.nii
    gzip -9 -f consensus/"$sample"_consensus.nii
  fi

  cd ..
done  


#Daniel Ryskamp Rijsketic 09/16/21 & 07/11/22 (Heifets Lab)





