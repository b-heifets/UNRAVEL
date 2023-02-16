#!/bin/bash 
# (c) Daniel Ryskamp Rijsketic, Boris Heifets @ Stanford University, 2021-2023

if [ "$1" == "help" ]; then 
  echo '
Run shift.sh to shift nii.gz content in gubra atlas space left or right by x pixels 
'
  exit 1
fi

#User inputs
echo " " 
read -p "Enter images to process (e.g., *.nii.gz or specific images separated by spaces): " inputs
echo " " 
read -p "Enter direction to shift (l or r): " direction
echo " " 
read -p "Enter # of pixels to shift by: " pixels
echo " " 

echo " " ; echo "Running shift.sh $@ from $PWD" ; echo " " 

specific_images=$(echo $inputs | sed "s/['\"]//g") # ' marks removed with sed
image_array=($specific_images)
inputs=($(for i in ${image_array[@]}; do echo $(basename $i) ; done))

echo " " ; echo "  Inputs: "${inputs[@]} "" ; echo " " 
echo "  Shifting brain(s) $direction by $pixels " ; echo " " 

#Shift
if [ "$direction" == "l" ]; then
  for i in "${inputs[@]}"; do fslroi $i L_"$pixels"_$i -"$pixels" 369 0 -1 0 -1 ; fslcpgeom $i L_"$pixels"_$i; done
else
  for i in "${inputs[@]}"; do fslroi $i R_"$pixels"_$i "$pixels" 369 0 -1 0 -1 ; fslcpgeom $i R_"$pixels"_$i; done
fi


#Daniel Ryskamp Rijsketic 11/17/21 & 07/01/22 (Heifets Lab)
