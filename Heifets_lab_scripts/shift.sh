#!/bin/bash 

if [ "$1" == "help" ]; then 
  echo '
Run shift2.sh to shift nii.gz content in gubra atlas space by x pixels 

From folder w/ nii.gz files run:
shift2.sh <input(s)>  

Default: *.nii.gz, but can provide multiple inputs separated by spaces
'
  exit 1
fi

#if no positional args provided, then: 
if [ $# -ne 0 ]; then 
  specific_images=$(echo $* | sed "s/['\"]//g") # ' marks removed with sed
  image_array=($specific_images)
  inputs=($(for i in ${image_array[@]}; do echo $(basename $i) ; done))
else 
  inputs=(*.nii.gz) 
fi

#User inputs
echo " " 
read -p "Enter direction to shift (l, r, p, a, s, i): " direction
echo " " 
read -p "Enter # of pixels to shift by: " pixels
echo " " 

echo " " ; echo "Running shift2.sh $@ from $PWD" ; echo " " 

echo " " ; echo "  Inputs: "${inputs[@]} "" ; echo " " 
echo "  Shifting brain(s) $direction by $pixels " ; echo " " 

#Shift left or right
if [ "$direction" == "l" ]; then
  for i in "${inputs[@]}"; do fslroi $i L_"$pixels"_$i -"$pixels" 369 0 -1 0 -1 ; fslcpgeom $i L_"$pixels"_$i; done
elif [ "$direction" == "r" ]; then
  for i in "${inputs[@]}"; do fslroi $i R_"$pixels"_$i "$pixels" 369 0 -1 0 -1 ; fslcpgeom $i R_"$pixels"_$i; done
elif [ "$direction" == "p" ]; then
  for i in "${inputs[@]}"; do fslroi $i P_"$pixels"_$i 0 -1 -"$pixels" 497 0 -1 ; fslcpgeom $i P_"$pixels"_$i; done
elif [ "$direction" == "a" ]; then
  for i in "${inputs[@]}"; do fslroi $i A_"$pixels"_$i 0 -1 "$pixels" 497 0 -1 ; fslcpgeom $i A_"$pixels"_$i; done
elif [ "$direction" == "s" ]; then
  for i in "${inputs[@]}"; do fslroi $i S_"$pixels"_$i 0 -1 0 -1 -"$pixels" 258 ; fslcpgeom $i S_"$pixels"_$i; done
elif [ "$direction" == "i" ]; then
  for i in "${inputs[@]}"; do fslroi $i I_"$pixels"_$i 0 -1 0 -1 "$pixels" 258 ; fslcpgeom $i I_"$pixels"_$i; done
else
  echo "  Rerun and enter a valid direction: l = left, r = right, p = posterior, a = anterior, s = superior, i = inferior" 
fi







#Daniel Rijsketic 11/17/21, 07/01/22, & 09/01/23 (Heifets Lab)
