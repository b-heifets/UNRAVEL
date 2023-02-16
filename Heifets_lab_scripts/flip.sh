#!/bin/bash 
# (c) Daniel Ryskamp Rijsketic, Boris Heifets @ Stanford University, 2022-2023

#For help message run: flip.sh help
if [ "$1" == "help" ]; then 
  echo '
From folder w/ nii.gz files to flip in x (horizontally) run:
flip.sh <input(s)>  

Default: *.nii.gz, but can provide multiple inputs separated by spaces
'
    exit 1
fi

echo " " ; echo "Running flip.sh $@ from $PWD" ; echo " " 

#if no positional args provided, then: 
if [ $# -ne 0 ]; then 
  specific_images=$(echo $* | sed "s/['\"]//g") # ' marks removed with sed
  image_array=($specific_images)
  inputs=($(for i in ${image_array[@]}; do echo $(basename $i) ; done))
else 
  inputs=(*.nii.gz) 
fi

echo " " ; echo "  Inputs: ${inputs[@]} " ; echo " " 

#Flip file in x
for i in "${inputs[@]}"; do fslswapdim $i -x y z flip_$i ; done

#Apply header from original file
for i in "${inputs[@]}"; do fslcpgeom $i flip_$i ; done


#Daniel Ryskamp Rijsketic 11/17/21 & 07/01/22 (Heifets lab)
