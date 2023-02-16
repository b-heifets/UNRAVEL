#!/bin/bash
# (c) Daniel Ryskamp Rijsketic, Boris Heifets @ Stanford University, 2022-2023


if [ $# == 0 ] || [ $1 == "help" ]; then
  echo " 
Run from sample folder to 3D count cells in cluster: 
3d_count_cluster.sh <./clusters_folder/cluster_masks/sample??_native_cluster_X.nii.gz> <cluster #> <enter y for region specific counts in clusters or n for just counts>

First attempts to 3D count cells in cluster on GPU (Uses modified CLIJ plugin)
If GPU memory error, then subdivides cluster into ~100 slice substacks and counts on GPU
If GPU memory error persists, deletes GPU substack folder and tries again w/ CPU (slow for larger volumes)
" 
  exit 1
fi

echo " " ; echo "Running 3d_count_cluster.sh from $PWD" ; echo " " 

# Make output folders and get path
image=$(basename $1)
path=$(dirname $1)
parent_dir="${path%/*}" 
clusters_folder=$(basename $parent_dir)
crop_image=$PWD/clusters/$clusters_folder/clusters_cropped/crop_"$image"
if [ $3 == "y" ]; then consensus="ABAconsensus" ; else consensus="consensus" ; fi
crop_consensus_image=$PWD/clusters/$clusters_folder/"$consensus"_cropped/crop_"$consensus"_"$image"
counts_path=$PWD/clusters/$clusters_folder/"$consensus"_cropped/3D_counts
mkdir -p $counts_path
touch $counts_path/Cells_outside_of_cluster_masked_out_in_these_folders
output_path=$counts_path/crop_"$consensus"_"${image::-7}"_3dc
mkdir -p $output_path

sample=$(basename $PWD)
sample_path=$PWD

### Multiply cropped_cluster by consensus_cropped to zero out cells outside of cluster
if [ ! -f $output_path/crop_"$consensus"_"$sample"_native_cluster_$2.nii.gz ]; then 
  echo " " ; echo "  Making $output_path/crop_"$consensus"_"$sample"_native_cluster_$2.nii.gz" ; echo Start: $(date) ; echo " "
  /usr/local/miracl/depends/Fiji.app/ImageJ-linux64 --ij2 -macro ClusterConsensus "$crop_image"#"$crop_consensus_image"#"$output_path"
  gzip -f -9 $output_path/crop_"$consensus"_"$sample"_native_cluster_$2.nii.gz.nii
  mv $output_path/crop_"$consensus"_"$sample"_native_cluster_$2.nii.gz.nii.gz $output_path/crop_"$consensus"_"$sample"_native_cluster_$2.nii.gz
  echo " " ; echo "  Made $output_path/crop_"$consensus"_"$sample"_native_cluster_$2.nii.gz" ; echo End: $(date) ; echo " "
fi

### 3D count cells in cluster on GPU ###
if [ ! -f $output_path/crop_"$consensus"_"$sample"_native_cluster_$2_3D_cell_count.txt ]; then 
  /usr/local/miracl/depends/Fiji.app/ImageJ-linux64 --ij2 -macro 3D_count_IncludeEdges $output_path/crop_"$consensus"_"$sample"_native_cluster_$2.nii.gz

### Check for GPU memory errors 
  cd $output_path
  if grep -rq "clij" ; then 
    echo " " ; echo "  GPU ERRORs for $output_path/crop_"$consensus"_"$sample"_native_cluster_$2.nii.gz" ; echo " "
    rm -f $output_path/crop_"$consensus"_"$sample"_native_cluster_$2.nii.gz_I.csv

    ### If GPU memory error from intial count, then subdivide cluster into ~100 slice substacks and count on GPU ###
    if [ ! -d "$output_path"/crop_"$consensus"_"${image::-7}"_3dc_100slices ]; then 
      echo "Spliting cluster into ~100 slice substacks and recounting on GPU" 
      mkdir "$output_path"/crop_"$consensus"_"${image::-7}"_3dc_100slices
      cd "$output_path"/crop_"$consensus"_"${image::-7}"_3dc_100slices
      /usr/local/miracl/depends/Fiji.app/ImageJ-linux64 --ij2 -macro 100sliceSubstacks_ClusterConsensus "$crop_image"#"$crop_consensus_image"#"$output_path"/crop_"$consensus"_"${image::-7}"_3dc_100slices
      find "$output_path"/crop_"$consensus"_"${image::-7}"_3dc_100slices/ -path "*ExcludeEdges.nii" -exec gzip -f -9  "{}" \;
      find "$output_path"/crop_"$consensus"_"${image::-7}"_3dc_100slices/ -path "*IncludeEdges.nii" -exec gzip -f -9  "{}" \;
      find "$output_path"/crop_"$consensus"_"${image::-7}"_3dc_100slices/ -path "*ExcludeEdges.nii.gz" -exec /usr/local/miracl/depends/Fiji.app/ImageJ-linux64 --ij2 -macro 3D_count_ExcludeEdges  "{}" \;
      find "$output_path"/crop_"$consensus"_"${image::-7}"_3dc_100slices/ -path "*IncludeEdges.nii.gz" -exec /usr/local/miracl/depends/Fiji.app/ImageJ-linux64 --ij2 -macro 3D_count_IncludeEdges  "{}" \; 
      if grep -rq "clij" ; then 
        echo " " ; echo "  GPU ERRORs for "$output_path"_100slices/crop_"$consensus"_"$sample"_native_cluster_$2.nii.gz" ; echo " "
        cd .. 
        rm -rf "$output_path"/crop_"$consensus"_"${image::-7}"_3dc_100slices

        ### Count on CPU 
        echo " " ; echo "  Using CPU to 3D count cells in $output_path/crop_"$consensus"_"$sample"_native_cluster_$2.nii.gz" ; echo Start: $(date) ; echo " "
        /usr/local/miracl/depends/Fiji.app/ImageJ-linux64 --ij2 -macro 3D_count_CPU $output_path/crop_"$consensus"_"$sample"_native_cluster_$2.nii.gz
        count=$(cat $output_path/crop_"$consensus"_"$sample"_native_cluster_$2.nii.gz.csv | wc -l)
        count=$(($count-1))
        if (( $count == -1 )); then count=0 ; fi
        echo "$count" > $output_path/crop_"$consensus"_"$sample"_native_cluster_$2_3D_cell_count.txt #-1 due to header
        echo " " ; echo "  Used CPU to 3D count $count cells in $output_path/crop_"$consensus"_"$sample"_native_cluster_$2.nii.gz" ; echo End: $(date) ; echo " "
        
      else
        ### If substack counts are OK:
        touch "$output_path"/GPU_substack_counts_OK
        cat *csv > all.csv
        count=$(cat all.csv | wc -l)
        count=$(($count-1))
        if (( $count == -1 )); then count=0 ; fi
        echo "$count" > $output_path/crop_"$consensus"_"$sample"_native_cluster_$2_3D_cell_count.txt
        echo " " ; echo "  GPU substack count of $count cells OK for crop_"$consensus"_"$sample"_native_cluster_$2.nii.gz" ; echo End: $(date) ; echo " "
      fi
      
    fi
  else 
    ### If intial counts are OK:
    touch $output_path/GPU_counts_OK
    count=$(cat $output_path/crop_"$consensus"_"$sample"_native_cluster_$2.nii.gz_I.csv | wc -l)
    count=$(($count-1))
    if (( $count == -1 )); then count=0 ; fi
    echo "$count" > $output_path/crop_"$consensus"_"$sample"_native_cluster_$2_3D_cell_count.txt
    echo " " ; echo "  GPU count of $count cells OK for $output_path/crop_"$consensus"_"$sample"_native_cluster_$2.nii.gz" ; echo End: $(date) ; echo " "
  fi
else 
  echo "  3D count exists for $output_path/crop_"$consensus"_"$sample"_native_cluster_$2_3D_cell_count.txt, skipping"
fi

#Results for regions in cluster based on regional intensities (requires 3D counting on GPU using CLIJ plugin for FIJI w/ modifications)
cd $output_path
if [ $3 == "y" ]; then
  regional_counts=sample_"${sample: -2}"_cluster_$2_"$consensus"_3Dcounts.csv #the sample number must be 2nd element for .py script to organize regional data
  if [ ! -f $regional_counts ]; then 
    if [ -f GPU_counts_OK ] ; then cut -d, -f 16,37,39,40,42,43,45 crop_"$consensus"_"$sample"_native_cluster_$2.nii.gz_I.csv > $regional_counts ; fi
    if [ -f GPU_substack_counts_OK ] ; then cut -d, -f 16,37,39,40,42,43,45 $PWD/crop_"$consensus"_"${image::-7}"_3dc_100slices/all.csv > $regional_counts ; fi
  fi
fi
cd $sample_path


#Daniel Ryskamp Rijsketic 04/28/2022-06/26/2022 (Heifets lab)

