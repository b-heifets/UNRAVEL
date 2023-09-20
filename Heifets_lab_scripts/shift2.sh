#!/bin/bash 

if [ $# == 0 ] || [ "$1" == "-h" ] || [ "$1" == "--help" ] || [ "$1" == "help" ]; then
  echo "
Run shift2.sh to shift nii.gz content in gubra atlas space by x pixels:

shift2.sh <input)>  <list: <direction> <# of pixels to shift by>>

For one shift: 
shift2.sh path/img.nii.gz R 1

For multiple shifts (R 1 shift performed first, then A 2): 
shift2.sh path/img.nii.gz R 1 A 2

R = right; L = left; A = anterior; P = posterior; S = superior; I = inferior
"
  exit 1
fi

echo " " ; echo "Running shift2.sh $@ from $PWD" ; echo " " 

img=$(echo $1 | sed "s/['\"]//g")

shift_array=($(echo "${@:2}" | sed "s/['\"]//g"))

img_path=$(dirname "$1")
img_base=$(basename "$1")
prev_img="$1"

shift_log=""

# For loop with a step of 2 to process each direction & pixel shift pair: 
for ((i=0; i<${#shift_array[@]}; i+=2)); do
  direction=${shift_array[i]}
  pixels=${shift_array[i+1]}
  
  # Append direction and pixels to shift log
  shift_log+="${direction}_${pixels}_"

  tmp="${img_path}/TEMP_${shift_log}${img_base}"

  echo "  Shifting $prev_img $direction by $pixels " ; echo " " 

  if [ "$direction" == "L" ]; then
    fslroi $prev_img $tmp -"$pixels" 369 0 -1 0 -1 ; fslcpgeom $prev_img $tmp
  elif [ "$direction" == "R" ]; then
    fslroi $prev_img $tmp "$pixels" 369 0 -1 0 -1 ; fslcpgeom $prev_img $tmp
  elif [ "$direction" == "P" ]; then
    fslroi $prev_img $tmp 0 -1 -"$pixels" 497 0 -1 ; fslcpgeom $prev_img $tmp
  elif [ "$direction" == "A" ]; then
    fslroi $prev_img $tmp 0 -1 "$pixels" 497 0 -1 ; fslcpgeom $prev_img $tmp
  elif [ "$direction" == "S" ]; then
    fslroi $prev_img $tmp 0 -1 0 -1 -"$pixels" 258 ; fslcpgeom $prev_img $tmp
  elif [ "$direction" == "I" ]; then
    fslroi $prev_img $tmp 0 -1 0 -1 "$pixels" 258 ; fslcpgeom $prev_img $tmp
  else
    echo "  Rerun and enter a valid direction: L = left, R = right, P = posterior, A = anterior, A = superior, I = inferior" 
  fi


  # If this isn't the first loop iteration, remove the previous intermediate image
  if [ "$prev_img" != "$1" ]; then
    rm -f "$prev_img"
  fi

  # Update prev_img to point to the current intermediate file
  prev_img="$tmp"
done

# Rename the last intermediate image to include the shift log
mv "$prev_img" "${img_path}/${shift_log}${img_base}"


#Daniel Rijsketic 11/17/21, 07/01/22, 09/01/23, 09/19/23 (Heifets Lab)
