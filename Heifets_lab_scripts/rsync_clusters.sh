#!/bin/bash
# (c) Daniel Ryskamp Rijsketic, Austen Casey, Boris Heifets @ Stanford University, 2022-2023

if [ "$1" == "help" ]; then
echo ' 
Run validate_clusters.sh from experiment summary folder and follow prompts in terminal.

It copies all validate_clusters.sh data to cluster_validation_summary/$output_folder
'
  exit 1
fi

exp_summary_dir=$PWD

echo " "  ; echo "Running rsync_clusters.sh $@ from $PWD" ; echo " " 

###### Input(s) for which experiment folders or samples to process: ####### 
if [ $# -ne 0 ]; then #if positional args provide, then
  path_array=($(echo $1 | sed "s/['\"]//g"))
  path_and_stats_map=$2
  q_value=$3
  ez_thr=$4
  min_cluster_size=$5
else #Accept user inputs
  read -p "Enter path/exp_dir list (process all samples) or path/sample?? list (for specific samples) separated by spaces: " paths ; echo " " 
  read -p "Enter path/stat_image.nii.gz for cluster validation: " path_and_stats_map ; echo " "
  read -p "Enter q value for voxel-wise FDR correction (e.g., 0.05 or 0.01) or n for using cluster correction: " q_value ; echo " "
  if [ "$q_value" == "n" ]; then 
    read -p "Enter z-thresh (e.g., 3.290527 for 2-tail p of 0.001) for ez_thr.sh: " ez_thr ; echo " " 
    min_cluster_size="n"
  else 
    ez_thr="n"
    read -p "Enter min cluster size in voxels: " min_cluster_size ; echo " "
  fi
  path_and_stats_map=$(echo ${path_and_stats_map%/} | sed "s/['\"]//g")
  path_array=($(echo $paths | sed "s/['\"]//g")) #remove ' marks from dragging and dropping folders/files into the terminal
fi
stats_map=${path_and_stats_map##*/}

# Check if first path in path_array is for an experiment folder or a sample folder and make path/sample?? array
path1_basename=$(basename ${path_array[0]}) 
if [ "${path1_basename::-2}" == "sample" ]; then 
  samples=${path_array[@]%/}
else 
  samples=($(for d in ${path_array[@]%/}; do cd $d ; for s in $(ls -d sample??); do cd $s ; echo $PWD ; cd .. ; done ; done))
fi

#Define output folder
if [ "$q_value" != "n" ]; then 
  output_folder="${stats_map::-7}"_FDR"$q_value"_MinCluster"$min_cluster_size"
else
  output_folder="${stats_map::-7}"_ezThr"$ez_thr"
fi 

####### Copy all validate_clusters.sh data to cluster_validation_summary/$output_folder #######
for s in ${samples[@]}; do
  cd $s
  rsync -au $s/clusters/$output_folder/ $exp_summary_dir/cluster_validation_summary/$output_folder
done 

cd $exp_summary_dir


#Daniel Ryskamp Rijsketic 05/16/2022-06/21/2022 07/27/22-07/29/22 & Austen Casey (added cluster_summary scripts 8/2/22) (Heifets lab)
