#!/bin/bash

# Check input parameters
if [ $# != 2 ] || [ "$1" == "-h" ] || [ "$1" == "--help" ] || [ "$1" == "help" ]; then
  echo "Usage: rev_shift.sh  <img_to_unshift.nii.gz> <shift_history_with_underscores>"
  exit 1
fi

echo " " ; echo "Running rev_shift.sh $@ from $PWD" ; echo " " 

# Image path and filename extraction
img=$(echo $1 | sed "s/['\"]//g")
img_path=$(dirname "$img")
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
    *) echo "Invalid direction in history!"; exit 1 ;;
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
output_file="${img_path}/${rev_shift_log}${img_base}"
mv "$prev_img" "$output_file"

echo "  Reverse shifts applied: ${rev_shift_log}"
echo "  Output saved as: ${output_file}" ; echo " " 


#Daniel Rijsketic 09/20/23 (Heifets Lab)
