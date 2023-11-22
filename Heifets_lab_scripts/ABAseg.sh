#!/bin/bash

if [ $# == 0 ] || [ "$1" == "-h" ] || [ "$1" == "--help" ] || [ "$1" == "help" ]; then
  echo '
Run from experiment folder:
ABAseg_3dc_IF.sh <path/[rev_shift_log]gubra_ano_split_25um.nii.gz> <immunofluor label> <rater #> [leave blank to process all samples or enter sample?? separated by spaces]

First run reg.sh and ilastik.sh

If shift2.sh is used for IF images in atlas space, then use rev_shift.sh on the atlas before 3D counting. 

Other input:
${2}_seg_ilastik_${3}/IlastikSegmentation/<1st_tif>

Outputs: 
sample??/sample??_${2}_ABAseg_${3}_stacks_25slices.csv

Use this script for region based 3D cell counts from a single rater
'
  exit 1
fi

echo " " ; echo "Running ABAseg.sh $@ from $PWD" ; echo " "

if [ $# -gt 3 ]; then 
  sample_array=($(echo "${@:4}" | sed "s/['\"]//g"))
  sample_array=($(for i in ${sample_array[@]}; do echo $(basename $i) ; done)) 
else 
  sample_array=(sample??) 
fi

for sample in ${sample_array[@]}; do
  cd $sample
  SampleDir="$PWD"

  native_atlas=$(echo $1 | sed "s/['\"]//g")
  if [ -f $native_atlas ]; then
    echo "  Native atlas: $native_atlas" ; echo " " 
  else 
    echo "  Native atlas ($native_atlas) does not exist" ; exit 1 
  fi

  echo $1 >> $PWD/parameters/atlas_used_for__${2}_seg_ilastik_${3}__ABAseg.txt

  seg=$PWD/${2}_seg_ilastik_${3}/${sample}_${2}_seg_ilastik_${3}.nii.gz
  if [ -f $seg ]; then
    echo "  Segmentation: $seg" ; echo " " 
  else 
    echo "  Native atlas ($native_atlas) does not exist" ; exit 1 
  fi

  # Multiply atlas by segmentation
  ABAseg=$PWD/${2}_seg_ilastik_${3}/${sample}_ABA_${2}_seg_ilastik_${3}.nii.gz
  if [ ! -f $ABAseg ]; then 
    echo " " ; echo "  Making $ABAseg " ; echo Start: $(date) ; echo " " 
    echo "  /usr/local/miracl/depends/Fiji.app/ImageJ-linux64 --ij2 -macro convert_to_ABA_intensities $native_atlas#$seg" 
    /usr/local/miracl/depends/Fiji.app/ImageJ-linux64 --ij2 -macro convert_to_ABA_intensities $native_atlas#$seg > /dev/null 2>&1
    mv $seg.nii ${ABAseg::-3}
    gzip -f -9 ${ABAseg::-3}
    echo " " ; echo "  Made $ABAseg " ; echo End: $(date) ; echo " " 
  else 
    echo " " ; echo "  $ABAseg exists, skipping" ; echo " " 
  fi

  # Convert seg objects to ABA intensities and generate 25 slice substacks using full verion of FIJI
  if [ ! -d ${2}_seg_ilastik_${3}/ABAseg_stacks_25slices ]; then 
    echo "  Making $PWD/${2}_seg_ilastik_${3}/ABAseg_stacks_25slices" ; echo Start: $(date) ; echo " " 
    echo "  /usr/local/miracl/depends/Fiji.app/ImageJ-linux64 --ij2 -macro 25sliceSubstacks $ABAseg#ABAseg"
    /usr/local/miracl/depends/Fiji.app/ImageJ-linux64 --ij2 -macro 25sliceSubstacks $ABAseg#ABAseg > /dev/null 2>&1
    gzip -f -9 $PWD/${2}_seg_ilastik_${3}/ABAseg_stacks_25slices/*.nii
    echo "  Made $PWD/${2}_seg_ilastik_${3}/ABAseg_stacks_25slices" ; echo End: $(date) ; echo " " 
  fi 

  cd ..
done 

#Daniel Ryskamp Rijsketic 09/23/22, 04/26/23, & 09/20-27/23 (Heifets lab)
