#!/bin/bash 
# (c) Daniel Ryskamp Rijsketic, Boris Heifets @ Stanford University, 2021-2023

if [ "$1" == "help" ]; then 
  echo '
To flip volume in gubra atlas space (e.g., convert LH to RH), run:
mirror.sh <leave blank for *.nii.gz or provide multiple inputs separated by spaces>

Output: mirror_<input.nii.gz>

To just flip w/o 2 px L shift, use flip.sh
To contol direction and extent of shift, use shift.sh
'
  exit 1
fi

echo " " ; echo "Running mirror.sh $@ from $PWD" ; echo " " 

if [ ! $# -eq 0 ]; then 
  specific_images=$(echo $* | sed "s/['\"]//g")
  image_array=($specific_images)
  inputs=($(for i in ${image_array[@]}; do echo $(basename $i) ; done))
else 
  inputs=(*.nii.gz) 
fi

echo " " ; echo "  Inputs: "${inputs[@]}" " ; echo " " 

for i in "${inputs[@]}"; do
  if [ ! -f mirror_$i ]; then 
  #Flip file in x
  fslswapdim $i -x y z flip_$i

  #Apply header from original file
  fslcpgeom $i flip_$i 

  #Nudge two pixels to the left
  fslroi flip_$i L_2_flip_$i -2 369 0 -1 0 -1 ; fslcpgeom $i L_2_flip_$i

  #rename 
  mv L_2_flip_$i mirror_$i

  rm -f flip_$i
  fi 
done 


#Daniel Ryskamp Rijsketic 07/01/22 08/03/22 (Heifets Lab)
