#!/bin/bash
# (c) Daniel Ryskamp Rijsketic, Boris Heifets @ Stanford University, 2022-2023

if [ $# == 0 ] || [ $1 == "help" ]; then
  echo " 
extract_full_most_sig__slice.sh <path/sample??/clusters/unique_cluster_validation_folder> <cluster #> [_rb*]
" 
  exit 1
fi

sample_dir=${1%/*/*} 
sample=${sample_dir##*/} 

echo " " ; echo "  Extracting full most sig tif from $sample_dir and drawing outline for cluster $2" ; echo " "

first_slice_of_cluster_in_tif_series=$(cat $1/bounding_boxes/"$sample"_native_cluster_"$2"_fslstats_w.txt | cut -d' ' -f5)
slice_w_most_sig_slice_in_cluster=$(cat $1/stats_cropped/crop_stats_thr_"$sample"_native_cluster_"$2".nii.gz_IntDen-Max_most-sig-slice.csv)
most_sig_slice=$(($first_slice_of_cluster_in_tif_series+$slice_w_most_sig_slice_in_cluster))
echo Most sig slice: $most_sig_slice ; echo " " 

mkdir -p $1/most_sig_ochann"$3"_tifs

find $sample_dir/ochann"$3" -name "*$most_sig_slice.tif" -exec /usr/local/miracl/depends/Fiji.app/ImageJ-linux64 --ij2 -macro draw_cluster_outline_in_full_tif $1/cluster_masks/"$sample"_native_cluster_"$2".nii.gz#"$most_sig_slice"#{}#$1/most_sig_ochann"$3"_tifs/ \;

echo " " ; echo "  Extracted full most sig tif from $sample_dir and drawing outline for cluster $2" ; echo " "

#Daniel Ryskamp Rijsketic 05/31/22 (Heifets lab)




