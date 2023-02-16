#!/bin/bash
# (c) Daniel Ryskamp Rijsketic, Boris Heifets @ Stanford University, 2022-2023

if [ "$1" == "help" ]; then
  echo '
Run from sample folder
ABA_histo_2xDS.sh [leave blank to process all samples or enter sample?? separated by spaces]

Inputs: 
sample??/reg_final/"$sample"_2xDS_native_gubra_ano_split.nii.gz (from ABA_to_native_2xDS.sh)

Outputs: 
sample??/sample??_ABA_histogram.csv
'
  exit 1
fi

echo " " ; echo "Running ABA_histo_2xDS.sh at $PWD $@" ; echo " " 

if [ $# -gt 0 ]; then 
  sample_array=($(echo "$@" | sed "s/['\"]//g"))
  sample_array=($(for i in ${sample_array[@]}; do echo $(basename $i) ; done)) 
else 
  sample_array=(sample??) 
fi

for sample in ${sample_array[@]}; do
  cd $sample

  if [ ! -f "$sample"_ABA_histogram.csv ] ; then 
    echo "Getting region volumes for "$sample"" ; echo Start: $(date)
    fslstats reg_final/"$sample"_2xDS_native_gubra_ano_split.nii.gz -H 21143 0 21143 > "$sample"_ABA_histogram.csv
    echo End: $(date) ; echo " "
  else 
    echo "Region volumes exist for "$sample", skipping"
  fi

  cd ..
done 

#Daniel Ryskamp Rijsketic 09/30/2022 (Heifets lab)

