#!/bin/bash

if [ "$1" == "help" ]; then
  echo '
Run from sample folder
ABA_histo_full_res.sh <path/native_atlas.nii.gz> [leave blank to process all samples or enter sample?? separated by spaces]

Inputs: 
sample??/reg_final/"$sample"_native_gubra_ano_split.nii.gz (from ABA_to_native.sh) or a custom native atlas

Outputs: 
sample??/sample??_ABA_histogram_total.csv
'
  exit 1
fi

echo " " ; echo "Running ABA_histo_full_res.sh at $PWD $@" ; echo " " 

if [ $# -gt 1 ]; then 
  sample_array=($(echo "${@:2}" | sed "s/['\"]//g"))
  sample_array=($(for i in ${sample_array[@]}; do echo $(basename $i) ; done)) 
else 
  sample_array=(sample??) 
fi

native_atlas=$(echo $1 | sed "s/['\"]//g")

for sample in ${sample_array[@]}; do
  cd $sample

  if [ ! -f "$sample"_ABA_histogram_total.csv ] ; then 
    echo "Getting region volumes for "$sample"" ; echo Start: $(date)
    fslstats $native_atlas -H 21143 0 21143 > "$sample"_ABA_histogram_total.csv 
    echo $1 >> parameters/atlas_used_for__ABA_histo_full_res.txt
    echo End: $(date)
  else 
    echo "Region volumes exist for "$sample", skipping"
  fi

  cd ..
done 

#Daniel Ryskamp Rijsketic 09/28/22 & 09/20-27/23 (Heifets lab)

