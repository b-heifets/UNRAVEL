#!/bin/bash
# (c) Daniel Ryskamp Rijsketic, Boris Heifets @ Stanford University, 2021-2023

if [ $# == 0 ] || [ "$1" == "help" ]; then
  echo '
From experiment folder containing ./sample??/488/tifs, run:
488_to_nii.sh <x/y voxel size in microns or m for metadata> <z voxel size or m> [leave blank to process all samples or enter sample?? separated by spaces]
 
Outputs: ./sample??/niftis/sample??_02x_down_autofl_chan.nii.gz 

x and y dimensions need an even number of pixels for tif to nii.gz conversion. First run czi_to_tifs.sh or prep_tifs.sh if needed
'
  exit 1
fi 

echo " " ; echo "Running 488_to_nii.sh $@ from $PWD" ; echo " "

if [ $# -gt 2 ]; then 
  sample_array=($(echo "${@:3}" | sed "s/['\"]//g"))
  sample_array=($(for i in ${sample_array[@]}; do echo $(basename $i) ; done)) 
else 
  sample_array=(sample??) 
fi

for sample in ${sample_array[@]}; do
  cd $sample
    if [ ! -f niftis/"$sample"_02x_down_autofl_chan.nii.gz ] ; then
      echo "  Converting 488 tifs to nii.gz for $sample"

      #x and y dimensions need an even number of pixels for tif to nii.gz conversion
      if [ "$1" == "m" ]; then 
        metadata.sh
        xy_res=$(grep "Voxel size: " parameters/metadata | cut -d" " -f3 | cut -dx -f1)
        z_res=$(grep "Voxel size: " parameters/metadata | cut -d" " -f3 | cut -dx -f3)
      else
        xy_res=$1
        z_res=$2
      fi 

      miracl_conv_convertTIFFtoNII.py -f 488 -o $sample -d 2 -ch autofl -vx $xy_res -vz $z_res
    fi
  cd ..
done 


#Daniel Ryskamp Rijsketic 09/10/2021 & 07/07/2022 (Heifets lab)



