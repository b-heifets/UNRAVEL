#!/bin/bash 
# (c) Daniel Ryskamp Rijsketic, Boris Heifets @ Stanford University, 2022-2023

if [ $# == 0 ] || [ "$1" == "help" ]; then
   echo '
From folder w/ .nii.gz inputs, run:
fsleyes.sh <display range min> <display range max> [leave blank to process all .nii.gz files or enter specific files separated by spaces]

For example to check alignment of ./<EXP>_summary/ochann_rb*_gubra_space_z/sample??_ochann_rb*_z_gubra_space.nii.gz files
'
  exit 1
fi 

if [ $# -gt 2 ]; then 
  image_array=($(echo "${@:3}" | sed "s/['\"]//g")) 
  image_array=($(for i in ${image_array[@]}; do echo $(basename $i) ; done)) 
else 
  image_array=(*.nii.gz) 
fi

echo " " ; echo "Running fsleyes.sh $@ from $PWD" ; echo " " 

fsleyes $(for i in ${image_array[@]} ; do echo $i -dr $1 $2 ; done) /usr/local/miracl/atlases/ara/gubra/gubra_ano_combined_25um.nii.gz -ot label -o


#Daniel Ryskamp Rijsketic 07/07/22 (Heifets Lab)
