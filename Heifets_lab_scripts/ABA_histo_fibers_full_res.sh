#!/bin/bash

if [ $# == 0 ] || [ "$1" == "-h" ] || [ "$1" == "--help" ] || [ "$1" == "help" ]; then
  echo '
Run from experiment folder:
ABA_histo_fibers_full_res.sh <path/native_atlas.nii.gz> <immunofluor label> <rater #> [leave blank to process all samples or enter sample?? separated by spaces]

Inputs: 
sample??/reg_final/"$sample"_native_gubra_ano_split.nii.gz (from ABA_to_native.sh) or a custom native atlas (e.g., from to_native2.sh)

Outputs: 
sample??/sample??_ABA_histogram_fibers_total.csv
'
  exit 1
fi

if [ $# -gt 3 ]; then 
  sample_array=($(echo "${@:4}" | sed "s/['\"]//g"))
  sample_array=($(for i in ${sample_array[@]}; do echo $(basename $i) ; done)) 
else 
  sample_array=(sample??) 
fi

for sample in ${sample_array[@]}; do
  cd $sample

  if [ ! -f "$sample"_ABA_histogram_fibers_total.csv ] ; then 

    echo " " ; echo "Running ABA_histo_fibers_full_res.sh $@ at $PWD " ; echo Start: $(date) ; echo " " 

    native_atlas=$(echo $1 | sed "s/['\"]//g")
    if [ -f $native_atlas ]; then
      echo "  Native atlas: $native_atlas" ; echo " " 
      native_atlas_path=$(dirname "$native_atlas")
      echo $1 >> parameters/atlas_used_for__ABA_histo_fibers_full_res.txt
    else 
      echo "  Native atlas ($native_atlas) does not exist" ; exit 1 
    fi

    seg=$PWD/${2}_seg_ilastik_${3}/${sample}_${2}_seg_ilastik_${3}.nii.gz
    if [ -f $seg ]; then
      echo "  Segmentation: $seg" ; echo " " 
    else 
      echo "  Native atlas ($native_atlas) does not exist" ; exit 1 
    fi

    # Multiply atlas by segmentation
    ABAseg=$PWD/${2}_seg_ilastik_${3}/${sample}_ABA_${2}_seg_ilastik_${3}.nii.gz
    if [ ! -f $ABAseg ]; then 
      echo " " ; echo "  Making $ABAseg " ; echo " " 
      echo "  /usr/local/miracl/depends/Fiji.app/ImageJ-linux64 --ij2 -macro convert_to_ABA_intensities $native_atlas#$seg" 
      /usr/local/miracl/depends/Fiji.app/ImageJ-linux64 --ij2 -macro convert_to_ABA_intensities $native_atlas#$seg > /dev/null 2>&1
      mv $seg.nii ${ABAseg::-3}
      gzip -f -9 ${ABAseg::-3}
      echo " " ; echo "  Made $ABAseg " ; echo End: $(date) ; echo " " 
    else 
      echo " " ; echo "  $ABAseg exists, skipping" ; echo " " 
    fi

    echo "  Getting regional fiber volumes for "$sample""
    fslstats $ABAseg -H 21143 0 21143 > "$sample"_ABA_histogram_fibers_total.csv

    echo "  Finished measuring regional fiber volumes for "$sample""
    echo End: $(date)

    
  else 
    echo "  Regional fiber volumes exist for "$sample", skipping"
  fi

  cd ..
done 

#Daniel Ryskamp Rijsketic 09/28/2022, 09/20-27/23, & 10/04/23 (Heifets lab)

