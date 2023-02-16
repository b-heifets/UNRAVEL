#!/bin/bash
# (c) Daniel Ryskamp Rijsketic, Boris Heifets @ Stanford University, 2022-2023

if [ $# == 0 ] || [ $1 == "help" ]; then
  echo " 
Run from sample folder to 3D count cells in cluster: 
3d_count_cluster.sh <./sample??/clusters/clusters_folder/consensus_cropped/3D_counts/crop_consensus_sample??_native_cluster_*_3dc/crop_consensus_sample??_native_cluster_*.nii.gz> <cluster #> <enter y for region specific counts in clusters or n for just counts>

First attempts to 3D count cells in cluster on GPU (Uses modified CLIJ plugin)
If GPU memory error, then subdivides cluster into ~100 slice substacks and counts on GPU
If GPU memory error persists, subdivides stack again and/or rerun processing later when GPU is not in use
" 
  exit 1
fi

echo " " ; echo "Running 3d_count_cluster2.sh $@ from $PWD" ; echo " " 

# Make output folders and get path
sample=$(basename $PWD)
sample_path=$PWD
path=$(dirname $1)
parent_dir="${path%/*}" 
if [ $3 == "y" ]; then consensus="ABAconsensus" ; else consensus="consensus" ; fi

max_value=$(fslstats $1 -R | cut -d' ' -f2)
if [ "$max_value" == "0.000000" ]; then touch $parent_dir/Image_is_empty ; else touch $parent_dir/Image_has_content ; fi

### 3D count cells in cluster on GPU ###
if [ ! -f ${1%/*}/crop_"$consensus"_"$sample"_native_cluster_"$2"_3D_cell_count.txt ]; then 
  /usr/local/miracl/depends/Fiji.app/ImageJ-linux64 --ij2 -macro 3D_count_IncludeEdges $1

### Check for GPU memory errors 
  cd ${1%/*}
  if grep -rq "clij" ; then 
    echo " " ; echo "  GPU ERRORs for ${1%/*}/crop_"$consensus"_"$sample"_native_cluster_"$2".nii.gz" ; echo " "
    rm -f ${1%/*}/crop_"$consensus"_"$sample"_native_cluster_"$2".nii.gz_I.csv

    ### If GPU memory error from intial count, then subdivide cluster into ~100 slice substacks and count on GPU ###
    if [ ! -d "${1%/*}"/crop_"$consensus"_"$sample"_native_cluster_"$2"_3dc_100slices ]; then 
      echo "Spliting cluster into ~100 slice substacks and recounting on GPU" 
      mkdir "${1%/*}"/crop_"$consensus"_"$sample"_native_cluster_"$2"_3dc_100slices
      cd "${1%/*}"/crop_"$consensus"_"$sample"_native_cluster_"$2"_3dc_100slices
      /usr/local/miracl/depends/Fiji.app/ImageJ-linux64 --ij2 -macro 100sliceSubstacks_ClusterConsensus2 $1#${1%/*}/crop_"$consensus"_"$sample"_native_cluster_"$2"_3dc_100slices
      find "${1%/*}"/crop_"$consensus"_"$sample"_native_cluster_"$2"_3dc_100slices/ -path "*ExcludeEdges.nii" -exec gzip -f -9  "{}" \;
      find "${1%/*}"/crop_"$consensus"_"$sample"_native_cluster_"$2"_3dc_100slices/ -path "*IncludeEdges.nii" -exec gzip -f -9  "{}" \;
      find "${1%/*}"/crop_"$consensus"_"$sample"_native_cluster_"$2"_3dc_100slices/ -path "*ExcludeEdges.nii.gz" -exec /usr/local/miracl/depends/Fiji.app/ImageJ-linux64 --ij2 -macro 3D_count_ExcludeEdges  "{}" \;
      find "${1%/*}"/crop_"$consensus"_"$sample"_native_cluster_"$2"_3dc_100slices/ -path "*IncludeEdges.nii.gz" -exec /usr/local/miracl/depends/Fiji.app/ImageJ-linux64 --ij2 -macro 3D_count_IncludeEdges  "{}" \; 
      if grep -rq "clij" ; then 
        echo " " ; echo "  GPU ERRORs for "${1%/*}"_100slices/crop_"$consensus"_"$sample"_native_cluster_"$2".nii.gz" ; echo " "
        3d_count_100_slice_stacks_w_errors.sh
        if grep -rq "clij" ; then 
          echo "GPU ERRORS remain. Rerun when GPU not in use or subdivide stacks further" 
          cd ..
          echo "cd $sample_path ; 3d_count_cluster2.sh $@" > Count_failed_from_full_GPU_memory 
        else 
          ### If substack counts are OK after splitting 100 slice substacks: 
          touch "${1%/*}"/GPU_substack_counts_OK
          rm -f all.csv
          cat *csv > all.csv
          count=$(cat all.csv | wc -l)
          count=$(($count-1))
          if (( $count == -1 )); then count=0 ; fi
          echo "$count" > ${1%/*}/crop_"$consensus"_"$sample"_native_cluster_"$2"_3D_cell_count.txt 
          echo " " ; echo "  GPU substack count of $count cells OK for crop_"$consensus"_"$sample"_native_cluster_"$2".nii.gz" ; echo End: $(date) ; echo " "
        fi 
      else
        ### If substack counts are OK after counting 100 slice substacks: 
        touch "${1%/*}"/GPU_substack_counts_OK
        rm -f all.csv
        cat *csv > all.csv
        count=$(cat all.csv | wc -l)
        count=$(($count-1))
        if (( $count == -1 )); then count=0 ; fi 
        echo "$count" > ${1%/*}/crop_"$consensus"_"$sample"_native_cluster_"$2"_3D_cell_count.txt
        echo " " ; echo "  GPU substack count of $count cells OK for crop_"$consensus"_"$sample"_native_cluster_"$2".nii.gz" ; echo End: $(date) ; echo " "
      fi
      
    fi
  else 
    ### If intial counts are OK:
    touch ${1%/*}/GPU_counts_OK
    count=$(cat ${1%/*}/crop_"$consensus"_"$sample"_native_cluster_"$2".nii.gz_I.csv | wc -l)
    count=$(($count-1))
    if (( $count == -1 )); then count=0 ; fi
    echo "$count" > ${1%/*}/crop_"$consensus"_"$sample"_native_cluster_"$2"_3D_cell_count.txt
    echo " " ; echo "  GPU count of $count cells OK for ${1%/*}/crop_"$consensus"_"$sample"_native_cluster_"$2".nii.gz" ; echo End: $(date) ; echo " "
  fi
else 
  echo "  3D count exists for ${1%/*}/crop_"$consensus"_"$sample"_native_cluster_"$2"_3D_cell_count.txt, skipping"
fi

#Results for regions in cluster based on regional intensities (requires 3D counting on GPU using CLIJ plugin for FIJI w/ modifications)
cd ${1%/*}
if [ $3 == "y" ]; then
  regional_counts=sample_"${sample: -2}"_cluster_"$2"_"$consensus"_3Dcounts.csv #the sample number must be 2nd element for .py script to organize regional data
  if [ ! -f $regional_counts ]; then 
    if [ -f GPU_counts_OK ] ; then cut -d, -f 16,37,39,40,42,43,45 crop_"$consensus"_"$sample"_native_cluster_"$2".nii.gz_I.csv > $regional_counts ; fi
    if [ -f GPU_substack_counts_OK ] ; then cut -d, -f 16,37,39,40,42,43,45 $PWD/crop_"$consensus"_"$sample"_native_cluster_"$2"_3dc_100slices/all.csv > $regional_counts ; fi
  fi
fi
cd $sample_path


#Daniel Ryskamp Rijsketic 04/28/2022-06/26/2022 12/12/22 (Heifets lab)
