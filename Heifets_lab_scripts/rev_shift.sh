#!/bin/bash

# Check input parameters
if [ $# == 0 ] || [ "$1" == "-h" ] || [ "$1" == "--help" ] || [ "$1" == "help" ]; then
  echo "
Usage: rev_shift.sh <path/image_to_shift.nii.gz> <shift_history_with_underscores or n> [path/mask.nii.gz]

path/mask.nii.gz could for example be a mask of dopamine cell regions 

"
  exit 1
fi

# Image path and filename extraction
img=$(echo $1 | sed "s/['\"]//g")

# Apply custom mask to the image if specified
if [ ! -z "$3" ]; then
  mask=$(echo $3 | sed "s/['\"]//g")
  mask_name=$(basename "$mask")
  fslmaths $img -mas $mask ${img::-7}_${mask_name::-7}
  img=${img::-7}_${mask_name::-7}.nii.gz
fi

# Output image printed to stdout for use in validate_clusters.sh
if [ "$2" == "n" ]; then 
  echo $1
  exit 1
fi

img_path=$(dirname "$1")
img_base=$(basename "$img")

# Extract shift history
shift_history="$2"
# Convert shift history into array
IFS='_' read -ra shift_array <<< "$shift_history"

# Reverse the shift array
for ((i=${#shift_array[@]}-1; i>=0; i-=2)); do
  reversed_array+=("${shift_array[i-1]}" "${shift_array[i]}")
done

rev_shift_log=""

# Reserve shift loop
prev_img="$img"
for ((i=0; i<${#reversed_array[@]}; i+=2)); do
  direction="${reversed_array[i]}"
  pixels="${reversed_array[i+1]}"

  # Determine inverse direction
  case "$direction" in
    L) inv_direction="R" ;;
    R) inv_direction="L" ;;
    P) inv_direction="A" ;;
    A) inv_direction="P" ;;
    S) inv_direction="I" ;;
    I) inv_direction="S" ;;
    *) echo "Invalid direction in history!" >&2; exit 1 ;;
  esac

  # Append direction and pixels to shift log
  rev_shift_log+="${inv_direction}_${pixels}_"

  # Image name for the temporary reverse shifted image
  tmp="${img_path}/UNSHIFT_${direction}_${pixels}_${img_base}"

  # Perform the reverse shift
  case "$inv_direction" in
    L) fslroi $prev_img $tmp -"$pixels" 369 0 -1 0 -1 ; fslcpgeom $prev_img $tmp ;;
    R) fslroi $prev_img $tmp "$pixels" 369 0 -1 0 -1 ; fslcpgeom $prev_img $tmp ;;
    P) fslroi $prev_img $tmp 0 -1 -"$pixels" 497 0 -1 ; fslcpgeom $prev_img $tmp ;;
    A) fslroi $prev_img $tmp 0 -1 "$pixels" 497 0 -1 ; fslcpgeom $prev_img $tmp ;;
    S) fslroi $prev_img $tmp 0 -1 0 -1 -"$pixels" 258 ; fslcpgeom $prev_img $tmp ;;
    I) fslroi $prev_img $tmp 0 -1 0 -1 "$pixels" 258 ; fslcpgeom $prev_img $tmp ;;
  esac

  # If this isn't the first loop iteration, remove the previous intermediate image
  if [ "$prev_img" != "$img" ]; then
    rm -f "$prev_img"
  fi

  # Update prev_img to point to the current intermediate file
  prev_img="$tmp"
done

# Rename the output with reverse shift log information
mkdir -p "${img_path}/rev_shifted_images/" ### this folder can also hold masked images (including non-shifted ones), so rename when refactoring to be more informative
output_file="${img_path}/rev_shifted_images/${rev_shift_log}${img_base}"
mv "$prev_img" "$output_file"

echo "$output_file"


#Daniel Rijsketic 09/20/23, 09/28/23, 10/03/23 (Heifets Lab)
