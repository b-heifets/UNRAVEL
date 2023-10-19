#!/bin/bash
if [ $# == 0 ] || [ "$1" == "help" ] || [ "$1" == "--help" ] || [ "$1" == "-h" ]; then
  echo "
renumber_cluster_index.sh <input_image.nii.gz> <renumbering.csv> <output_image.nii.gz>

csv has original IDs in the first column and new IDs in the second column (no header) 

-odt char is used w/ fslmaths, so less than 255 clusters is assumed.
"
  exit 1
fi

# Input and output files
input_image="$1"
renumbering_csv="$2"
output_image="$3"

# Create a temporary copy of the input image
tmp_image="${1%???????}_tmp.nii.gz"

cp "$input_image" "$tmp_image"

# Make blank image
fslmaths "$tmp_image" -sub "$tmp_image" "$tmp_image" -odt char

# Read CSV and apply renumbering
while IFS=, read -r orig_id new_id || [[ -n "$orig_id" ]]; do 
    echo "Changing cluster ID: $orig_id -> $new_id"
    fslmaths $input_image -thr $orig_id -uthr $orig_id -bin -mul $new_id label_$new_id -odt char
    fslmaths "$tmp_image" -add label_${new_id} "$tmp_image" -odt char
    rm label_${new_id}.nii.gz
done < "$renumbering_csv"

# Move the temporary image to  the output file
mv "$tmp_image" "$output_image"

echo "Renumbering completed. Result saved to $output_image"


