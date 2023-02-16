#!/bin/bash
# (c) Daniel Ryskamp Rijsketic, Boris Heifets @ Stanford University, 2022-2023

echo " " 
echo " Run cluster_validation.sh from experiment summary folder and follow prompts in terminal: "  
echo " Or run cluster_validation.sh <string from inputs from prior run> "
echo " Outputs copied to summary folder and $PWD/clusters/clusters_folder (defined in script by parameters)  "
echo " Requires: stats map, reg files, sample??/consensus/sample??_consensus.tif and sample??/488/tifs "
echo " If you stop processing (control+c), delete partial files in sample folders (e.g., if cluster_crop.sh killed, delete 0 kb file in ./bounding_boxes) "
echo " During warping to native space, an intermediate file (same name as starting file) is saved in clar_allen_reg, so delete it if rerunning to fix warp to native outputs" 
echo " If viewing image in FIJI and content looks black, control+shift+c -> change min to 0 and max to 1 (don't click Apply) " 
echo " If sample flipped, flip rev_cluster_index and stat_thresh before warping to native  " 
echo " Run cluster_counts.sh at ./exp_summary_folder/clusters/clusters_folder/ABAconsensus_cropped/3D_counts to organize cell counts "
echo " Run montage.sh <cluster #> from summary folder to tile most significant cropped images " 
echo " " 

echo " " ; echo " " ; echo " "

######### Input(s) for which experiment directories to process: ########### 
if [ $# -ne 0 ]; then #if positional args provided from inputs, then use them for assigning variables, otherwise: 
  dirs=$(echo $1 | sed "s/['\"]//g") ; echo " " # ' marks removed with sed (allows for dragging and dropping foldering into the terminal to input paths)
  dirs_inputs="'$dirs'" #group dirs with ' marks for positional args w/ inputs for rerunning script
else
  read -p "If processing all samples, enter paths for each experiment directory separated by a space (otherwise enter n): " directories ; echo " " 
  if [ "$directories" != "n" ]; then 
    dirs=$(echo $directories | sed "s/['\"]//g") 
    dirs_inputs="'$dirs'" 
  else
    dirs_inputs="'n'"
  fi
fi
dir_array=($dirs)

#Get user inputs
input () {
  read -p "$1" # $1=prompt
  echo $REPLY #this allows assignment of function output to a variable
}

if [ $# -ne 0 ]; then
  samples_to_process=$(echo $2 | sed "s/['\"]//g")
  samples_to_process_inputs="'$samples_to_process'" 
else 
  samples_to_process=$(input "Process all samples? (y or each <path/sample??> separated by a space): ") ; echo " "
  samples_to_process=$(echo $samples_to_process | sed "s/['\"]//g") ; samples_to_process_inputs="'$samples_to_process'"
fi

sample_array=($samples_to_process) #just used for processing specific samples
if [ "$samples_to_process" != "y" ]; then  #if not processing all samples, then make array w/ path for each sample
  dir_array=($(for s in ${sample_array[@]}; do exp_dir_path=$(dirname $s) ; echo $exp_dir_path ; done))
fi

#Inputs for cluster_index.sh and warp_index_to_native.sh
if [ $# -ne 0 ]; then path_and_stats_map=$3 ; smoothing_stats_by_X_mm=$4 ; stats_thr=$5 min_cluster_size=$6 ; else 
  path_and_stats_map=$(echo $(input "path/stat_image.nii.gz: ") | sed "s/['\"]//g") ; echo " " #sed escapes ' marks
  smoothing_stats_by_X_mm=$(input "Kernel size in mm for smoothing stats image (e.g., 0.05) or 0 for no smoothing: ") ; echo " "
  stats_thr=$(input "Stat threshold (e.g. 1-p value of 0.999): ") ; echo " "
  min_cluster_size=$(input "Min cluster size in voxels: ") ; echo " "
fi
stats_map_path=$(dirname $path_and_stats_map)
stats_map=$(basename $path_and_stats_map)

#xyz resolution
if [ $# -ne 0 ]; then xy_res=$7 ; z_res=$8 ; else
  xy_res=$(input "xy voxel size um: ") ; echo " "
  z_res=$(input "z voxel size um: ") ; echo " "
fi

#Input for which clusters to process
# ' marks needed for multiple inputs for a parameter
if [ $# -ne 0 ]; then 
  clusters_to_process=$(echo $9 | sed "s/['\"]//g") ; clusters_to_process_inputs="'$clusters_to_process'"
else
  clusters_to_process=$(input "Which clusters to process? all (process all clusters), '{1..4}' (range), or '1 2 4' (select clusters): ") ; echo " "
  clusters_to_process=$(echo $clusters_to_process | sed "s/['\"]//g") ; clusters_to_process_inputs="'$clusters_to_process'"
fi

#Choose to process regional count cell in clusters or just cell counts
if [ $# -ne 0 ]; then 
  regional_counts=$(echo ${10}) 
else
  regional_counts=$(input "For regional cell counts in clusters enter y and for just cell counts in clusters enter n: ") ; echo " " 
fi

#Input for raw data to crop (crop_raw.sh)
if [ $# -ne 0 ]; then 
  raw_folders=$(echo ${11} | sed "s/['\"]//g") ; raw_folders_inputs="'$raw_folders'"
else
  raw_folders=$(input "For cropping raw data, list folders separated by spaces (.e.g, 'ochann ochann_rb4'. Otherwise, enter n): ") ; echo " "
  raw_folders=$(echo $raw_folders | sed "s/['\"]//g") ; raw_folders_inputs="'$raw_folders'"
fi
raw_folder_array=($(echo $raw_folders | sed "s/['\"]//g"))

#Option to warp stats to native and crop based on cluster
if [ $# -ne 0 ]; then 
  warp_and_crop_stats_map=$(echo ${12}) 
else
  warp_and_crop_stats_map=$(input "Enter y to warp stats map to tissue space, crop it for each cluster, and extract most sig slices for montage (otherwise enter n):  ") ; echo " " 
fi

#LUT for display range scaled stats image  
if [ $# -ne 0 ]; then 
  stats_LUT=$(echo ${13} | sed "s/['\"]//g") 
else
  stats_LUT=$(input "For stats montage, enter LUT: grey, hot or cool: ") ; echo " " 
fi

#z threshold for easythresh
if [ $# -ne 0 ]; then 
  cluster_z_thresh=$(echo ${14})
  brain_mask=$(echo ${15} | sed "s/['\"]//g")
else
  cluster_z_thresh=$(input "Enter z-thresh for easythres (e.g., 3.290527 for two-tail p of 0.001) or n: ") ; echo " " 
  brain_mask=$(input "If using easythresh, enter path/brain_mask.nii.gz. Otherwise, enter n: ") ; echo " " 
  brain_mask=$(echo $brain_mask | sed "s/['\"]//g")
fi

#Inputs for warping cluster index and stats map from atlas space to native space (warp_index_to_native.sh & warp_stats_to_native.sh) 
#and defining where data is saved in sample folders
kernel_in_um=$(echo "($smoothing_stats_by_X_mm*1000+0.5)/1" | bc) #(x+0.5)/1 is used for rounding in bash and bc handles floats
if (( $kernel_in_um > 0 )); then 
  output_folder="${stats_map%???????}"_s"$kernel_in_um"_statThr"$stats_thr"_MinCluster"$min_cluster_size"
  prefix_for_matching_clusters_folders="${stats_map%???????}"_s"$kernel_in_um"_statThr"$stats_thr"_MinCluster
  cluster_index="$output_folder"_cluster_index.nii.gz
  rev_cluster_index="$output_folder"_rev_cluster_index.nii.gz
else
  if [ "$cluster_z_thresh" == "n" ]; then 
    output_folder="${stats_map%???????}"_statThr"$stats_thr"_MinCluster"$min_cluster_size"
    prefix_for_matching_clusters_folders="${stats_map%???????}"_statThr"$stats_thr"_MinCluster
    cluster_index="$output_folder"_cluster_index.nii.gz
    rev_cluster_index="$output_folder"_rev_cluster_index.nii.gz
  else
    output_folder="${stats_map%???????}"_ezThr"$cluster_z_thresh" #folder naming when using ez_thr.sh
  fi
fi
summary=$PWD/cluster_validation_summary/"$output_folder"
cluster_index_path=$stats_map_path/"$output_folder"
clusters_folder=clusters/"$output_folder"

#Rerun script with parameters saved in inputs text file (e.g., if a memory error stops it during: fslstats $image -w in crop_cluster.sh)
inputs="cluster_validation.sh $dirs_inputs $samples_to_process_inputs $path_and_stats_map $smoothing_stats_by_X_mm $stats_thr $min_cluster_size $xy_res $z_res $clusters_to_process_inputs $regional_counts $raw_folders_inputs $warp_and_crop_stats_map $stats_LUT $cluster_z_thresh $brain_mask" ; echo " " ; echo " " ; echo "Rerun script with: " ; echo " " ; echo "$inputs" ; echo " " ; echo " " ; echo " " 

original_dir=$PWD

#All data and inputs copied and moved to cluster_validation_summary
if [ ! -d cluster_validation_summary ]; then mkdir cluster_validation_summary ; fi
if [ ! -d $summary ]; then mkdir $summary ; fi #Results copied to here
cd $summary

echo $inputs > inputs #positional args for rerunning script


##################################################################
######################## Run scripts #############################
##################################################################

if [ "$cluster_z_thresh" == "n" ]; then 
#### Make cluster index ###
  cd $stats_map_path
  cluster_index.sh $path_and_stats_map $smoothing_stats_by_X_mm $stats_thr $min_cluster_size $cluster_index_path  

  #### Reverse cluster index ID order (so the largest cluster has intensity/ID of 1 on so on) ###
  reverse_cluster_order.sh $path_and_stats_map $smoothing_stats_by_X_mm $stats_thr $min_cluster_size $cluster_index_path   

  #Copying cluster_index results
  rsync -au $output_folder/ $summary/cluster_index

else
  ez_thr.sh $path_and_stats_map $brain_mask $cluster_z_thresh 0.05
  rsync -au $stats_map_path/$output_folder/ $summary/cluster_index
fi

###########################################
######### Processing all samples ##########
###########################################

if [ "$samples_to_process" == "y" ]; then 
  for d in ${dir_array[@]}; do cd $d 
    for s in sample??; do cd $s
#### Warp cluster index to native space ###
#Outputs ./clusters/native_cluster_index/sample??_native_cluster_index.nii.gz (full res and 2x downsampled versions)
      if [ "$cluster_z_thresh" == "n" ]; then 
        warp_index_to_native.sh $cluster_index_path/$rev_cluster_index $xy_res $z_res $clusters_folder #Requires 488/tifs
      else
        warp_index_to_native.sh $stats_map_path/$output_folder/rev_cluster_mask_$stats_map $xy_res $z_res $clusters_folder #Requires 488/tifs
      fi 
      rsync -au $PWD/$clusters_folder/ $summary
      cd ../
    done
  done
fi

#Define range for processing all clusters (otherwise use custom list) and copy prior cluster data
if [ "$samples_to_process" == "y" ]; then 
  cd ${dir_array[0]}
  for s in sample??; do last_sample=$s ; done
  if [ "$clusters_to_process" == "all" ]; then
    float=$(fslstats ${dir_array[0]}/$last_sample/$clusters_folder/native_cluster_index/"$last_sample"_2xDS_native_cluster_index.nii.gz -R | awk '{print $2;}') # get 2nd word of output (max value in volume)
    num_of_clusters=${float%.*} # convert to integer
    clusters_to_process="{1..$num_of_clusters}"
  fi
fi

### If reanalyzing data with new MinCluster criteria, prior cluster data (matching stat map, smoothing level, and statThr) will be copied to new MinCluster folder, and prior clusters smaller than MinCluster criteria will be deleted ###
if [ "$samples_to_process" == "y" ]; then 
  for d in ${dir_array[@]}; do cd $d
    for s in sample??; do 
      cd $s
        if [ "$cluster_z_thresh" == "n" ]; then 
          cp_prior_clusters.sh $prefix_for_matching_clusters_folders $cluster_index_path
        fi 
      cd ../ 
    done
  done
fi

### Generate cluster masks ###
if [ "$samples_to_process" == "y" ]; then 
  for d in ${dir_array[@]}; do cd $d
    for s in sample??; do cd $s
      for i in $(eval echo "$clusters_to_process"); do
        cluster_masks.sh $PWD/$clusters_folder/native_cluster_index/"$s"_native_cluster_index.nii.gz $PWD/$clusters_folder/cluster_masks/"$s"_native_cluster_"$i".nii.gz $i 
      done
      rsync -au $PWD/$clusters_folder/ $summary
      cd ../
    done
  done
fi

### Crop clusters ###
if [ "$samples_to_process" == "y" ]; then 
  for d in ${dir_array[@]}; do cd $d
    for s in sample??; do cd $s
      for i in $(eval echo "$clusters_to_process"); do
        crop_cluster.sh $PWD/$clusters_folder/cluster_masks/"$s"_native_cluster_"$i".nii.gz
      done
      rsync -au $PWD/$clusters_folder/ $summary
      cd ../
    done
  done
fi

### Crop consensus/ABAconsensus ###
if [ "$samples_to_process" == "y" ]; then 
  for d in ${dir_array[@]}; do cd $d 
    for s in sample??; do cd $s
      if [ "$regional_counts" == "y" ]; then full_res_atlas.sh $xy_res $z_res ; ABAconsensus.sh ; fi
      for i in $(eval echo "$clusters_to_process"); do
        if [ "$regional_counts" == "y" ]; then crop_ABAconsensus.sh $PWD/$clusters_folder/bounding_boxes/"$s"_native_cluster_"$i"_fslstats_w.txt ; else crop_consensus.sh $PWD/$clusters_folder/bounding_boxes/"$s"_native_cluster_"$i"_fslstats_w.txt ; fi
      done
      rsync -au $PWD/$clusters_folder/ $summary
      cd ../
    done
  done
fi

### 3D count cells in cropped consensus/ABAconsensus images ###
if [ "$samples_to_process" == "y" ]; then 
  for d in ${dir_array[@]}; do cd $d 
    for s in sample??; do cd $s
      for i in $(eval echo "$clusters_to_process"); do
        3d_count_cluster.sh $PWD/$clusters_folder/cluster_masks/"$s"_native_cluster_"$i".nii.gz $i $regional_counts
      done
      rsync -au $PWD/$clusters_folder/ $summary
      cd ../
    done
  done
fi

if [ "$warp_and_crop_stats_map" == "y" ]; then 
  #### Warp thresholded stats map to native space ###
  #Outputs ./clusters/native_stats/stats_thr_sample??_native.nii.gz
  if [ "$samples_to_process" == "y" ]; then 
    for d in ${dir_array[@]}; do cd $d 
      for s in sample??; do cd $s
        if [ "$cluster_z_thresh" == "n" ]; then 
          warp_stats_to_native.sh $cluster_index_path/${cluster_index%????????????????????}thresh.nii.gz $xy_res $z_res $clusters_folder #Requires 488/tifs
        else
          warp_stats_to_native.sh $stats_map_path/$output_folder/thresh_${stats_map%???????}.nii.gz $xy_res $z_res $clusters_folder #Requires 488/tifs
        fi
        rsync -au $PWD/$clusters_folder/ $summary
        cd ../
      done
    done
  fi

  #### Crop stats ###
  if [ "$samples_to_process" == "y" ]; then 
    for d in ${dir_array[@]}; do cd $d 
      for s in sample??; do cd $s
        for i in $(eval echo "$clusters_to_process"); do
          crop_stats.sh $PWD/$clusters_folder/bounding_boxes/"$s"_native_cluster_"$i"_fslstats_w.txt
          get_most_sig_slice.sh $PWD/$clusters_folder/stats_cropped/crop_stats_thr_"$s"_native_cluster_"$i".nii.gz
          extract_most_sig_slice.sh $PWD/$clusters_folder/stats_cropped/crop_stats_thr_"$s"_native_cluster_"$i".nii.gz $PWD/$clusters_folder/stats_cropped/crop_stats_thr_"$s"_native_cluster_"$i".nii.gz_IntDen-Max_most-sig-slice.csv $stats_thr $stats_LUT
          if [ "$regional_counts" == "y" ]; then extract_most_sig_slice.sh $PWD/$clusters_folder/ABAconsensus_cropped/crop_ABAconsensus_"$s"_native_cluster_"$i".nii.gz $PWD/$clusters_folder/stats_cropped/crop_stats_thr_"$s"_native_cluster_"$i".nii.gz_IntDen-Max_most-sig-slice.csv "min" "grey" ; else extract_most_sig_slice.sh $PWD/$clusters_folder/consensus_cropped/crop_consensus_"$s"_native_cluster_"$i".nii.gz $PWD/$clusters_folder/stats_cropped/crop_stats_thr_"$s"_native_cluster_"$i".nii.gz_IntDen-Max_most-sig-slice.csv "min" "grey" ; fi
        done
        rsync -au $PWD/$clusters_folder/ $summary
        cd ../
      done
    done
  fi
fi 

### Convert clusters to atlas regional intensities and crop ###
if [ "$regional_counts" == "y" ]; then 
  if [ "$samples_to_process" == "y" ]; then 
    for d in ${dir_array[@]}; do cd $d 
      for s in sample??; do cd $s
        for i in $(eval echo "$clusters_to_process"); do
          ABAcluster.sh $PWD/$clusters_folder/cluster_masks/"$s"_native_cluster_"$i".nii.gz
          crop_ABAcluster.sh $PWD/$clusters_folder/bounding_boxes/"$s"_native_cluster_"$i"_fslstats_w.txt
        done
        rsync -au $PWD/$clusters_folder/ $summary
        cd ../
      done
    done
  fi
fi

### Crop raw data ###
if [ "$raw_folders" != "n" ]; then
  if [ "$samples_to_process" == "y" ]; then 
    for d in ${dir_array[@]}; do cd $d 
      for s in sample??; do cd $s
        for folder in "${raw_folder_array[@]}"; do
          for i in $(eval echo "$clusters_to_process"); do
            crop_raw.sh $PWD/$clusters_folder/bounding_boxes/"$s"_native_cluster_"$i"_fslstats_w.txt $folder $PWD/$clusters_folder/"$folder"_cropped
            if [ "$warp_and_crop_stats_map" == "y" ]; then extract_most_sig_slice.sh $PWD/$clusters_folder/"$folder"_cropped/crop_"$folder"_"$s"_native_cluster_"$i".nii.gz $PWD/$clusters_folder/stats_cropped/crop_stats_thr_"$s"_native_cluster_"$i".nii.gz_IntDen-Max_most-sig-slice.csv "min" "grey" ; fi
          done
          rsync -au $PWD/$clusters_folder/ $summary
        done
        cd ../
      done
    done
  fi
fi
 
###################################################
########## Processing a specific sample ###########
###################################################

if [ "$samples_to_process" != "y" ]; then
  for s in "${sample_array[@]}"; do 
    cd $s
### Warp cluster index to native space
    #Outputs reg_final: full res and 2x downsampled sample??_native_cluster_index.nii.gz
    if [ "$cluster_z_thresh" == "n" ]; then 
      warp_index_to_native.sh $cluster_index_path/$rev_cluster_index $xy_res $z_res $clusters_folder #Requires 488/tifs
    else
      warp_index_to_native.sh $stats_map_path/$output_folder/rev_cluster_mask_$stats_map $xy_res $z_res $clusters_folder #Requires 488/tifs
    fi 
    rsync -au $PWD/$clusters_folder/ $summary
  done
fi

### Define range for processing all clusters (otherwise use custom list) ###
if [ "$samples_to_process" != "y" ]; then
  if [ "$clusters_to_process" == "all" ]; then
    sample1=$(basename "${sample_array[0]}")
    float=$(fslstats "${sample_array[0]}"/$clusters_folder/native_cluster_index/"$sample1"_2xDS_native_cluster_index.nii.gz -R | awk '{print $2;}')
    num_of_clusters=${float%.*}
    clusters_to_process="{1..$num_of_clusters}"
  fi 
fi

### If reanalyzing data with new MinCluster criteria, prior cluster data (matching stat map, smoothing level, and statThr) will be copied to new MinCluster folder, and prior clusters smaller than MinCluster criteria will be deleted ###
if [ "$samples_to_process" != "y" ]; then
  for s in "${sample_array[@]}"; do 
    cd $s
    if [ "$cluster_z_thresh" == "n" ]; then 
      cp_prior_clusters.sh $clusters_folder $prefix_for_matching_clusters_folders $cluster_index_path
    fi 
    cd ../
  done
fi

### Processing specific sample(s) ###New Folder
if [ "$samples_to_process" != "y" ]; then
  for sample in "${sample_array[@]}"; do 
    cd $sample
    s=$(basename $sample)

### Generate cluster masks ###
    for i in $(eval echo "$clusters_to_process"); do
      cluster_masks.sh $PWD/$clusters_folder/native_cluster_index/"$s"_native_cluster_index.nii.gz $PWD/$clusters_folder/cluster_masks/"$s"_native_cluster_"$i".nii.gz $i      
    done
    rsync -au $PWD/$clusters_folder/ $summary
 
### Crop clusters ###
    for i in $(eval echo "$clusters_to_process"); do
      crop_cluster.sh $PWD/$clusters_folder/cluster_masks/"$s"_native_cluster_"$i".nii.gz
    done
    rsync -au $PWD/$clusters_folder/ $summary

### Crop consensus/ABAconsensus ###
    if [ "$regional_counts" == "y" ]; then full_res_atlas.sh $xy_res $z_res ; ABAconsensus.sh ; fi
    for i in $(eval echo "$clusters_to_process"); do
      if [ "$regional_counts" == "y" ]; then crop_ABAconsensus.sh $PWD/$clusters_folder/bounding_boxes/"$s"_native_cluster_"$i"_fslstats_w.txt ; else crop_ABAconsensus.sh $PWD/$clusters_folder/bounding_boxes/"$s"_native_cluster_"$i"_fslstats_w.txt ; fi
    done
    rsync -au $PWD/$clusters_folder/ $summary

### 3D count cells in cropped consensus/ABAconsensus images ###
    for i in $(eval echo "$clusters_to_process"); do
      3d_count_cluster.sh $PWD/$clusters_folder/cluster_masks/"$s"_native_cluster_"$i".nii.gz $i $regional_counts
    done
    rsync -au $PWD/$clusters_folder/ $summary

    if [ "$warp_and_crop_stats_map" == "y" ]; then
      ### Warp thresholded stats map to native space
      #Outputs ./clusters/native_stats/stats_thr_native.nii.gz (full res and 2x downsampled versions)
      if [ "$cluster_z_thresh" == "n" ]; then 
        warp_stats_to_native.sh $cluster_index_path/${cluster_index%????????????????????}thresh.nii.gz $xy_res $z_res $clusters_folder #Requires 488/tifs
      else
        warp_stats_to_native.sh $stats_map_path/$output_folder/thresh_${stats_map%???????}.nii.gz $xy_res $z_res $clusters_folder #Requires 488/tifs
      fi
      rsync -au $PWD/$clusters_folder/ $summary

      ### Crop stats ###
      for i in $(eval echo "$clusters_to_process"); do
        crop_stats.sh $PWD/$clusters_folder/bounding_boxes/"$s"_native_cluster_"$i"_fslstats_w.txt
        get_most_sig_slice.sh $PWD/$clusters_folder/stats_cropped/crop_stats_thr_"$s"_native_cluster_"$i".nii.gz
        extract_most_sig_slice.sh $PWD/$clusters_folder/stats_cropped/crop_stats_thr_"$s"_native_cluster_"$i".nii.gz $PWD/$clusters_folder/stats_cropped/crop_stats_thr_"$s"_native_cluster_"$i".nii.gz_IntDen-Max_most-sig-slice.csv $stats_thr $stats_LUT
        if [ "$regional_counts" == "y" ]; then extract_most_sig_slice.sh $PWD/$clusters_folder/ABAconsensus_cropped/crop_ABAconsensus_"$s"_native_cluster_"$i".nii.gz $PWD/$clusters_folder/stats_cropped/crop_stats_thr_"$s"_native_cluster_"$i".nii.gz_IntDen-Max_most-sig-slice.csv "min" "grey" ; else extract_most_sig_slice.sh $PWD/$clusters_folder/consensus_cropped/crop_consensus_"$s"_native_cluster_"$i".nii.gz $PWD/$clusters_folder/stats_cropped/crop_stats_thr_"$s"_native_cluster_"$i".nii.gz_IntDen-Max_most-sig-slice.csv "min" "grey" ; fi
      done
      rsync -au $PWD/$clusters_folder/ $summary
    fi

### Convert clusters to atlas regional intensities and crop ###
    if [ "$regional_counts" == "y" ]; then 
      for i in $(eval echo "$clusters_to_process"); do
        ABAcluster.sh $PWD/$clusters_folder/cluster_masks/"$s"_native_cluster_"$i".nii.gz
        crop_ABAcluster.sh $PWD/$clusters_folder/bounding_boxes/"$s"_native_cluster_"$i"_fslstats_w.txt ; 
      done
      rsync -au $PWD/$clusters_folder/ $summary
    fi

### Crop raw data ###
    if [ "$raw_folders" != "n" ]; then
      for folder in "${raw_folder_array[@]}"; do
        for i in $(eval echo "$clusters_to_process"); do
          crop_raw.sh $PWD/$clusters_folder/bounding_boxes/"$s"_native_cluster_"$i"_fslstats_w.txt $folder $PWD/$clusters_folder/"$folder"_cropped
          if [ "$warp_and_crop_stats_map" == "y" ]; then extract_most_sig_slice.sh $PWD/$clusters_folder/"$folder"_cropped/crop_"$folder"_"$s"_native_cluster_"$i".nii.gz $PWD/$clusters_folder/stats_cropped/crop_stats_thr_"$s"_native_cluster_"$i".nii.gz_IntDen-Max_most-sig-slice.csv "min" "grey" ; fi
        done
        rsync -au $PWD/$clusters_folder/ $summary
      done
    fi

  done
fi

cd $original_dir


#Daniel Ryskamp Rijsketic 05/16/2022-06/21/2022

