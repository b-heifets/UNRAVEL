#!/bin/bash

if [ $# == 0 ] || [ "$1" == "-h" ] || [ "$1" == "--help" ] || [ "$1" == "help" ]; then
  echo '
Run from experiment folder:
ABA_histo_in_tissue_full_res.sh <path/native_atlas.nii.gz> <Threshold for tissue mask> [leave blank to process all samples or enter sample?? separated by spaces]

Inputs: 
sample??/reg_final/"$sample"_native_gubra_ano_split.nii.gz (from ABA_to_native.sh) or a custom native atlas
sample??/488/tifs

Outputs: 
sample??/sample??_ABA_histogram_total.csv
'
  exit 1
fi

echo " " ; echo "Running ABA_histo_in_tissue_full_res.sh $@ at $PWD " ; echo " " 

if [ $# -gt 2 ]; then 
  sample_array=($(echo "${@:3}" | sed "s/['\"]//g"))
  sample_array=($(for i in ${sample_array[@]}; do echo $(basename $i) ; done)) 
else 
  sample_array=(sample??) 
fi

native_atlas=$(echo $1 | sed "s/['\"]//g")
native_atlas_path=$(dirname "$native_atlas")

for sample in ${sample_array[@]}; do
  cd $sample
  if [ ! -f "$sample"_ABA_histogram_in_tissue_total.csv ] ; then 
    echo "Getting region volumes for "$sample""
    first_488_tif=$(ls 488 | head -1)
    /usr/local/miracl/depends/Fiji.app/ImageJ-linux64 --ij2 -macro ABA_within_tissue_full_res $native_atlas#$PWD/488/$first_488_tif#$2 > /dev/null 2>&1
    gzip -9 -f $native_atlas_path/"$sample"_native_gubra_ano_split_in_tissue.nii
    fslstats $native_atlas_path/"$sample"_native_gubra_ano_split_in_tissue.nii.gz -H 21143 0 21143 > "$sample"_ABA_histogram_in_tissue_total.csv
    echo $1 >> parameters/atlas_used_for__ABA_histo_in_tissue_full_res.txt
  else 
    echo "Region volumes exist for "$sample", skipping"
  fi

  cd ..
done 

#Daniel Ryskamp Rijsketic 09/28/2022 & 09/20-27/23   (Heifets lab)

