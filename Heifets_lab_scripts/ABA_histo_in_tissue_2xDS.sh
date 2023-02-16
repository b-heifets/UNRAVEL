#!/bin/bash
# (c) Daniel Ryskamp Rijsketic, Boris Heifets @ Stanford University, 2022-2023

if [ "$1" == "help" ]; then
  echo '
Run from sample folder
ABA_histo_in_tissue_2xDS.sh <Threshold for tissue mask> [leave blank to process all samples or enter sample?? separated by spaces]

Inputs: 
sample??/reg_final/clar_downsample_res10um.nii.gz 
sample??/reg_final/"$sample"_2xDS_native_gubra_ano_split.nii.gz (from ABA_to_native_2xDS.sh)


Outputs: 
sample??/sample??_ABA_histogram_in_tissue.csv
'
  exit 1
fi

echo " " ; echo "Running ABA_histo_in_tissue_2xDS.sh at $PWD $@" ; echo " " 

if [ $# -gt 1 ]; then 
  sample_array=($(echo "${@:2}" | sed "s/['\"]//g"))
  sample_array=($(for i in ${sample_array[@]}; do echo $(basename $i) ; done)) 
else 
  sample_array=(sample??) 
fi

for sample in ${sample_array[@]}; do
  cd $sample

  first_488_tif=$(ls 488 | head -1)

  if [ ! -f "$sample"_ABA_histogram_in_tissue.csv ] ; then 
    echo "Getting region volumes in tissue for "$sample"" ; echo Start: $(date)

    /usr/local/miracl/depends/Fiji.app/ImageJ-linux64 --ij2 -macro 2xDS_488 $PWD/488/$first_488_tif
    mv $PWD/488/2xDS_488.nii $PWD/reg_final/2xDS_488.nii
    gzip -f -9 $PWD/reg_final/2xDS_488.nii

    fslmaths $PWD/reg_final/2xDS_488.nii.gz -thr $1 -bin $PWD/reg_final/2xDS_488_thr$1_bin.nii.gz -odt char
    fslmaths $PWD/reg_final/2xDS_488_thr$1_bin.nii.gz -mul reg_final/"$sample"_2xDS_native_gubra_ano_split.nii.gz reg_final/"$sample"_2xDS_native_gubra_ano_split_in_tissue.nii.gz -odt short 

    fslstats reg_final/"$sample"_2xDS_native_gubra_ano_split_in_tissue.nii.gz -H 21143 0 21143 > "$sample"_ABA_histogram_in_tissue.csv

    echo End: $(date) ; echo " "
  else 
    echo "Region volumes in tissue exist for "$sample", skipping"
  fi

  cd ..
done 

#Daniel Ryskamp Rijsketic 09/30/2022 (Heifets lab)

