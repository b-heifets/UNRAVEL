#!/bin/bash

if [ $# == 0 ] || [ "$1" == "help" ]; then
  echo '
From experiment folder run:
adjust_dr.sh <min of display range> <max of display range> [leave blank to process all samples or enter sample?? separated by spaces]
 
Sets and applies display range of 488 tifs with Fiji

Outputs: ./sample??/niftis/sample??_02x_down_autofl_chan_dr_x-y.nii.gz and sample??_02x_down_autofl_chan.nii.gz (same, but ready as input for reg.sh)
'
  exit 1
fi 

echo " " ; echo "Running adjust_dr.sh $@ from $PWD" ; echo " "

if [ $# -gt 2 ]; then 
  sample_array=($(echo "${@:3}" | sed "s/['\"]//g"))
  sample_array=($(for i in ${sample_array[@]}; do echo $(basename $i) ; done)) 
else 
  sample_array=(sample??) 
fi

for sample in ${sample_array[@]}; do
  cd $sample
    if [ ! -f 488_dr_"$1"_"$2" ] ; then
      echo "  Adjusting 488 display range and linearly scaling intensities for $sample"
      if [ ! -d 488_original ]; then mkdir 488_original ; cp ./488/* ./488_original/ ; fi
      cd 488
      first_tif=$(ls *.tif | head -1)
      shopt -s nullglob ; for f in *\ *; do mv "$f" "${f// /_}"; done ; shopt -u nullglob #remove spaces from tif series
      cd ..
      /usr/local/miracl/depends/Fiji.app/ImageJ-linux64 --ij2 -macro adjust_dr $PWD/488/$first_tif#$1#$2
      touch 488_dr_"$1"_"$2"
    fi
  cd ..
done 


#Daniel Ryskamp Rijsketic 01/06/2022 (Heifets lab)



