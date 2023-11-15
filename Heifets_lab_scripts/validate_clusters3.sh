#!/bin/bash

if [ $# == 0 ] || [ "$1" == "help" ] || [ "$1" == "--help" ] || [ "$1" == "-h" ]; then
  echo "
Run validate_clusters3.sh from experiment summary folder and follow prompts in terminal.

New arguments:
  1) path/exp_dir or path/sample?? list (e.g., 'path1 path2' or 'path1/sample01 path2/sample02')
  2) output folder name (e.g., 'stats_map_q0.05')
  3) path/rev_cluster_index.nii.gz (from fdr.sh; save params)
  4) path/segmentation_img.nii.gz relative to sample folder (e.g., cfos_seg_ilastik_1/)
  5) xy res or m
  6) z res or m 
  7) clusters to process: all, '{1..4}' (range), or '1 2 4' (select clusters) 

Other inputs:
  Transformations from reg.py 

Outputs:
  sample??/clusters/<output_folder>/ and ./cluster_validation_summary/<output_folder>/
"
  exit 1
fi

exp_summary_dir=$PWD

###### Positional args ####### 
path_array=($(echo $1 | sed "s/['\"]//g"))
output_dir_name=$(echo $2 | sed "s/['\"]//g")
rev_cluster_index_path=$(echo $3 | sed "s/['\"]//g")
seg_img_rel_path=$(echo $4 | sed "s/['\"]//g")
xy_res=$4
z_res=$5
clusters_to_process=$(echo $6 | sed "s/['\"]//g") ; clusters_to_process_inputs="'$clusters_to_process'"

inputs="validate_clusters3.sh '${path_array[@]}' $output_dir_name $rev_cluster_index_path $seg_img_rel_path $xy_res $z_res $clusters_to_process_inputs" ; echo " " ; echo " " ; 
echo "Rerun script with: " ; echo "$inputs" 

# Check if first path in path_array is for an experiment folder or a sample folder and make path/sample?? array
path1_basename=$(basename ${path_array[0]}) 
if [ "${path1_basename::-2}" == "sample" ]; then 
  samples=${path_array[@]%/}
else 
  samples=($(for d in ${path_array[@]%/}; do cd $d ; for s in $(ls -d sample??); do cd $s ; echo $PWD ; cd .. ; done ; done))
fi

# Regional volumes
sunburst.sh $rev_cluster_index
mkdir -p cluster_validation_summary $PWD/cluster_validation_summary/$output_dir_name
rsync -au ${rev_cluster_index%/*}/ $exp_summary_dir/cluster_validation_summary/$output_dir_name/cluster_index

if [ "$clusters_to_process" == "all" ]; then 
  clusters_to_process=$(uniq_intensities.py -i $rev_cluster_index -m 100) # min cluster size = 100 voxels
  clusters=$(eval echo "$clusters_to_process")
fi  

for s in ${samples[@]}; do
  cd $s

  # Warp reversed cluster index to native space
  to_native2.sh $rev_cluster_index $xy_res $z_res clusters/$output_dir_name native_cluster_index

  # Generate ./bounding_boxes/*.txt, & cropped cluster masks and segmentation images
  native_clusters_any_immunofluor_rater_abc.sh $s/clusters/$output_dir_name/native_cluster_index/native_"$output_dir_name"_rev_cluster_index.nii.gz $xy_res $z_res "$clusters"

  # 3D count cells in clusters
  for c in $(eval echo $clusters); do
    cluster_cell_counts.py #<cropped_cluster_mask> <cropped_seg_img> # Perhaps add this to native_clusters
  done

  rsync -au $s/clusters/$output_dir_name/ $exp_summary_dir/cluster_validation_summary/$output_dir_name
  echo " " ; echo "Rerun script with: " ; echo " " ; echo "$inputs" ; echo " " 
done

####### Get cell densities in clusters #######
# cd $exp_summary_dir/cluster_validation_summary/$output_dir_name
# cluster_densities2_any_immunofluor_rater_abc.sh all all $immuno_label $seg_type

cd $exp_summary_dir

printf "\n$inputs\n"