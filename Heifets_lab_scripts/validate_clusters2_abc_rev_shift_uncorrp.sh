#!/bin/bash

echo " 
Run validate_clusters2_abc_rev_shift.sh from experiment summary folder and follow prompts in terminal.

Enter path/sample?? instead of dir list for one sample

validate_clusters2_abc_rev_shift.sh <./exp_or_sample_dir list> <seg (s), val (v), both> <./stats_map> <uncorr p value or n> <easythresh z thresh or n> <l, r, both, or ./custom_mask> <min cluster size in voxels> <xy res in um> <z res> <IF label> <consensus or specific rater #s> <clusters to process> <y for regional volumes or n> <y for regional counts or n> <y to montage tiles or n> <'ochann ochann_rb4'> <shift_history> <path/region_mask>

This script aims to validate clusters of significant voxels (hot/cold spots) identified from voxel-wise stats (find_clusters.sh -> glm.sh). validate_clusters2_abc_rev_shift.sh consists of two main phases (segmentation of cells in raw data and measuring cell density in clusters). See ilastik.sh help and consensus.sh help for how to set up phase 1 (ochann/tif series is required). For more info on phase 2 (requires output(s) from glm.sh, reg.sh, consensus.sh as well as 488/tifs), run: validate_clusters2_abc_rev_shift.sh help  

"

if [ "$1" == "help" ]; then
  echo "
This script can run ilastik.sh and consensus.sh as part of the segmentation phase and can separately or serially run subscripts for cell density measurements ect. Scripts for the second phase include: 

uncorr_p_index.sh or ez_thr.sh (voxel-wise or cluster-wise correction for multiple comparisons, respectively)
ABA_volumes.sh (regional volumes histogram output to csv)
sunburst.sh (regional volumes in csv format for making sunburst w/ Flourish)
rev_shift.sh (optionally apply region mask to cluster index and then if content of atlas space IF images was shifted, apply opposite shifts to atlas and rev_cluster_index.nii.gz)
to_native.sh (warp cluster index image [w/ IDs reversed] and the thresholded stats map to tissue space and scale to full res. Also scales warped atlas to full res)
native_clusters.sh (for each cluster, mask it, crop it, measure its volume in cubic mm, use it to crop and zero out the cell segmentation)
ABAcluster.sh (binary cluster mask multiplied by the ABA intensities)
ABAconsensus.sh (multiplies the warped atlas by the consensus image, converting intensities of cells into the unique brain region intensity where they are located)
3d_count_cluster.sh (fast 3D cell counting on the GPU. Cell intensities can be used for region specific counts)
cluster_densities.sh (generates CSVs with cell counts, cluster volumes, and cell densities in clusters saved in exp_summary/cluster_validation_summary/unique_dir/cluster_outputs)
get_most_sig_slice.sh (finds the 'most significant' slice in the thresholded stats image for a cluster by measuring integrated density of each slice)
extract_most_sig_slice.sh (saves the 'most sig' slice for raw, rb*, consensus, and thresholded stats data)

Outputs saved in sample??/clusters/unique_folder/
Outputs copied to ./sample??/clusters/ & copied to ./cluster_validation_summary/

Notes: This requires stats map, reg.sh outputs, sample??/consensus/sample??_consensus.nii.gz and sample??/488/tifs. If you stop processing (control+c), delete partial files if any (e.g., in ./sample??/clusters/unique_cluster_folder/...). If rerunning warp to native with inputs that have been fixed, delete an intermediate file (same name as input) in clar_allen_reg. If viewing image in FIJI and content looks black, control+shift+c -> change min to 0 and max to 1 (don't click Apply). If sample is flipped, copy and flip rev_cluster_index & stat_thresh. Rename flipped images as the original before warping to native. Just process the flipped samples and, after warping, revert input names to avoid warping a flipped image to native for non-flipped samples. If outside of Heifets lab, update path to template masks in script or use custom masks. If you want cell densities for all samples and clusters, run cluster_densities.sh all all from the unique_folder/

"
  exit 1
fi

exp_summary_dir=$PWD

###### Input(s) for which experiment folders or samples to process: ####### 
if [ $# -ne 0 ]; then #if positional args provided, then
  path_array=($(echo $1 | sed "s/['\"]//g"))
  seg_or_val=$2
  path_and_stats_map=$3
  p_value=$4
  ez_thr=$5
  mask=$(echo $6 | sed "s/['\"]//g") # mask for cluster correction
  min_cluster_size=$7
  xy_res=$8
  z_res=$9

  immuno_label=$(echo ${10} | sed "s/['\"]//g")  ### ABC Add
  seg_type=$(echo ${11} | sed "s/['\"]//g") ### ABC Add

  clusters_to_process=$(echo ${12} | sed "s/['\"]//g") ; clusters_to_process_inputs="'$clusters_to_process'" #was 10
  regional_volumes=${13} #was 11
  regional_counts=${14} #was 12
  make_montage=${15} #was 13
  raw_folders=$(echo ${16} | sed "s/['\"]//g") #was 14

  shift_history=${17}
  region_mask=${18} # optional: mask for rev_cluster_index (e.g., to process specific anatomical regions)
  
else #Accept user inputs
  read -p "Enter path/exp_dir list (process all samples) or path/sample?? list (for specific samples) separated by spaces: " paths ; echo " " 
  read -p "Enter s to segment ochann & run consensus.sh, v for cluster validation, or both: " seg_or_val ; echo " "
  if [ "$seg_or_val" == "v" ] || [ "$seg_or_val" == "both" ] ; then 
    read -p "Enter path/stat_image.nii.gz for cluster validation: " path_and_stats_map ; echo " "
    read -p "Enter uncorr p value or n for using cluster correction: " p_value ; echo " "
    if [ "$p_value" == "n" ]; then 
      read -p "Enter z-thresh (e.g., 3.290527 for 2-tail p of 0.001) for ez_thr.sh: " ez_thr ; echo " " 
      min_cluster_size="n"
    else 
      ez_thr="n"
      read -p "Enter min cluster size in voxels: " min_cluster_size ; echo " "
    fi
    read -p "Enter side of the brain (l, r, both, or ./custom_mask.nii.gz) for cluster correction mask: " mask ; echo " "
    read -p "Enter xy voxel size (um), s to get once from sample_overview.csv, or m for metadata for each sample: " xy_res ; echo " "
    if [ $xy_res != "s" ] && [ $xy_res != "m" ]; then read -p "Enter z voxel size: " z_res ; echo " " ; fi

    read -p "What is immunofluor label name? for example, 'cfos' or 'npas4', etc (only enter one): " immuno_label ; echo " " ###########
    read -p "What type of segmentation method to validate? If consensus, type 'consensus', if rater1, type '1': " seg_type ; echo " " #############

    read -p "Which clusters to process? all, '{1..4}' (range), or '1 2 4' (select clusters): " clusters_to_process ; echo " "
    clusters_to_process=$(echo $clusters_to_process | sed "s/['\"]//g") ; clusters_to_process_inputs="'$clusters_to_process'"
    read -p "Enter y for regional volumes in clusters or n for just total cluster volumes: " regional_volumes ; echo " " 
    read -p "Enter y for regional cell counts in clusters or n for just total cell counts: " regional_counts ; echo " " 
    read -p "Enter y to warp stats to native, crop it, and find/get most sig slices for montage (else: n): " make_montage ; echo " "
    read -p "For raw/rb* montage tiles, list folders separated by spaces (.e.g, 'ochann ochann_rb4') (else: n): " raw_folders ; echo " "
    path_and_stats_map=$(echo ${path_and_stats_map%/} | sed "s/['\"]//g")
    raw_folders=$(echo $raw_folders | sed "s/['\"]//g")
    read -p "Enter shift history for path/sample??: " shift_history ; echo " "
    read -p "Enter path/region_mask.nii.gz or leave blank: " region_mask ; echo " "
  fi
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

if [ "$seg_or_val" == "v" ] || [ "$seg_or_val" == "both" ]; then 
  # Determine xyz voxel size 
  if [ "$xy_res" == "s" ]; then 
    xy_res=$(grep ${samples[0]: -2} sample_overview.csv | cut -d, -f7)
    z_res=$(grep ${samples[0]: -2} sample_overview.csv | cut -d, -f8)
  elif [ "$xy_res" == "m" ]; then 
    z_res="m"
  fi

  # Inputs for warping cluster index/stats and defining where data is saved in sample/summary folders
  if [ "$p_value" != "n" ]; then 
    output_folder="${stats_map::-7}"_uncorrp"$p_value"_MinCluster"$min_cluster_size"
    echo output_folder: $output_folder ; echo " " 

  else
    output_folder="${stats_map::-7}"_ezThr"$ez_thr"
  fi

  # All data and inputs copied and moved to cluster_validation_summary
  mkdir -p cluster_validation_summary $PWD/cluster_validation_summary/$output_folder

fi

inputs="validate_clusters2_abc_rev_shift.sh '${path_array[@]}' $seg_or_val $path_and_stats_map $p_value $ez_thr $mask $min_cluster_size $xy_res $z_res $immuno_label $seg_type $clusters_to_process_inputs $regional_volumes $regional_counts $make_montage '$raw_folders' $shift_history $region_mask" ; echo " " ; echo " " ; 
echo "Rerun script with: " ; echo " " ; 
echo "###############################################"
echo "$inputs" 
echo "###############################################"
echo " " ; echo " " ; echo "validate_clusters2_abc_rev_shift.sh <./exp_or_sample_dir list> <seg (s), val (v), both> <./stats_map> <uncorr p value or n> <easythresh z thresh or n> <l, r, both, or ./custom_mask> <min cluster size in voxels> <xy res in um> <z res> <IF label> <consensus or specific rater #s> <clusters to process> <y for regional volumes or n> <y for regional counts or n> <y to montage tiles or n> <'ochann ochann_rb4'> <shift_history> <path/region_mask>" ; echo " " ; mkdir -p rerun_validate_clusters ; echo $inputs > rerun_validate_clusters/rerun_validate_clusters_$(date +"%Y_%m_%d_%I_%M_%p") ; echo " " ; echo " " ; echo " " 


#####################################################################
########################### Run scripts #############################
#####################################################################

####### Segment cFos+ cells or other label and make consensus #######
if [ "$seg_or_val" == "s" ] || [ "$seg_or_val" == "both" ] ; then 
  cd $exp_summary_dir
  ilastik_project1=$(ls *_rater?.ilp | head -1)
  for s in ${samples[@]}; do
    cd ${s%/*} #path/exp_folder
    ilastik.sh $exp_summary_dir/$ilastik_project1 '{1..5}' $s
    consensus.sh $s
  done
fi

####################### Validate clusters ###########################
if [ "$seg_or_val" == "v" ] || [ "$seg_or_val" == "both" ] ; then 

  ####### Make cluster index & reverse cluster ID order #######
  if [ "$p_value" != "n" ]; then 
    uncorr_p_index.sh $path_and_stats_map $mask $min_cluster_size $p_value 
  else
    ez_thr.sh $path_and_stats_map $mask $ez_thr 0.05
  fi

  ABA_volumes.sh ${path_and_stats_map%/*}/$output_folder/"$output_folder"_cluster_index.nii.gz

  sunburst.sh ${path_and_stats_map%/*}/$output_folder/"$output_folder"_cluster_index.nii.gz

  rsync -au ${path_and_stats_map%/*}/$output_folder/ $exp_summary_dir/cluster_validation_summary/$output_folder/cluster_index

  ####### Cluster index/[atlas] to native, crop clusters, [consensus to ABA intensities], crop [ABA]consensus, & 3D count #######
  for s in ${samples[@]}; do
    cd $s

    # If shifts were applied to atlas space IF image, apply reverse shifts to cluster index:
    echo "Running rev_shift.sh ${path_and_stats_map%/*}/$output_folder/"$output_folder"_rev_cluster_index.nii.gz $shift_history $region_mask" ; echo " " 
    index=$(rev_shift.sh ${path_and_stats_map%/*}/$output_folder/"$output_folder"_rev_cluster_index.nii.gz $shift_history $region_mask)

    # Set $clusters_to_process 
    if [ "$clusters_to_process" == "all" ]; then 
       clusters_to_process=$(uniq_intensities.py -i $index -m $min_cluster_size)
    fi  

    # Warp reversed cluster index to native
    to_native2.sh $index $xy_res $z_res clusters/$output_folder native_cluster_index

    # Generate clusters masks, ./bounding_boxes/"${image::-7}"_fslstats_w.txt, & cropped clusters
    ###ABC Edited to chunk cluster index into groups of clusters that are easier to process at once
    clusters=($(eval echo "$clusters_to_process"))
    chunk_size=25
    total_clusters=${#clusters[@]}
      for ((start=0; $start < $total_clusters ; start+=chunk_size)); do 
        end=$((start+chunk_size))
        if ((end > $total_clusters)); then end=$total_clusters ; fi
        cluster_chunk=("${clusters[@]:start:chunk_size}") ; 
        #cluster_chunk=$(IFS=" "; echo "${cluster_chunk[*]}")
        cluster_string="${cluster_chunk[*]}"
        native_clusters_any_immunofluor_rater_abc.sh $s/clusters/$output_folder/native_cluster_index/native_$(basename $index) $xy_res $z_res "$cluster_string" $immuno_label $seg_type 
      done

    # [Scale up native atlas and use it to convert clusters and/or consensus segementation to ABA intensties for region specific data]
    if [ "$regional_volumes" == "y" ] || [ "$regional_counts" == "y" ]; then 
      to_native.sh $s/reg_final/gubra_ano_split_10um_clar_downsample.nii.gz $xy_res $z_res clusters/$output_folder native_atlas
    fi

    if [ "$regional_counts" == "y" ]; then 
      ABAconsensus.sh
      for i in $(eval echo "$clusters_to_process"); do
        crop_cluster.sh $s/clusters/$output_folder/bounding_boxes/"${s##*/}"_native_cluster_"$i"_fslstats_w.txt ABAconsensus $s/consensus/"${s##*/}"_ABAconsensus.nii.gz
      done
    fi 

    # 3D count cells in clusters (CLIJ plugin uses GPU for speed & edits enable fractional assignment of counts at region boundaries)  
    for i in $(eval echo "$clusters_to_process"); do
      if [ $seg_type != "consensus" ] ; then
        seg_folder="$immuno_label"_seg_ilastik_"$seg_type" ; 
           else
        seg_folder=consensus
      fi
      3d_count_cluster2_any_immunofluor_rater_abc.sh $s/clusters/$output_folder/"$seg_folder"_cropped/3D_counts/crop_"$seg_folder"_"${s##*/}"_native_cluster_"$i"_3dc/crop_"$seg_folder"_"${s##*/}"_native_cluster_"$i".nii.gz $i n
    done

    rsync -au $s/clusters/$output_folder/ $exp_summary_dir/cluster_validation_summary/$output_folder
    echo " " ; echo "Rerun script with: " ; echo " " ; echo "$inputs" ; echo " " 
  done

  # Convert clusters to atlas regional intensities and crop
  for s in ${samples[@]}; do
    cd $s
    if [ "$regional_volumes" == "y" ]; then
      for i in $(eval echo "$clusters_to_process"); do
        ABAcluster.sh $s/clusters/$output_folder/cluster_masks/"${s##*/}"_native_cluster_"$i".nii.gz
        crop_cluster.sh $s/clusters/$output_folder/bounding_boxes/"${s##*/}"_native_cluster_"$i"_fslstats_w.txt ABAcluster $s/clusters/$output_folder/ABAcluster_masks/ABA_"${s##*/}"_native_cluster_"$i".nii.gz
      done

      cd $exp_summary_dir/cluster_validation_summary/$output_folder  
      ABAcluster_volumes.sh
    fi
    rsync -au $s/clusters/$output_folder/ $exp_summary_dir/cluster_validation_summary/$output_folder
  done 

  ####### Get cell densities in clusters #######
  echo " " ; echo "For getting cell densities for specific/all samples and clusters, see: cluster_densities.sh help" ; echo " " 
  cd $exp_summary_dir/cluster_validation_summary/$output_folder
  cluster_densities2_any_immunofluor_rater_abc.sh all all $immuno_label $seg_type

  ####### [Generate tiles for montage] #######
  for s in ${samples[@]}; do
    cd $s

    # Warp stats map to native, crop it, and find most sig slice, save it for stats
    if [ "$make_montage" == "y" ]; then 
      to_native2.sh ${path_and_stats_map%/*}/$output_folder/"$output_folder"_thresh.nii.gz $xy_res $z_res clusters/$output_folder native_stats
      for i in $(eval echo "$clusters_to_process"); do
        crop_cluster.sh $s/clusters/$output_folder/bounding_boxes/"${s##*/}"_native_cluster_"$i"_fslstats_w.txt stats $s/clusters/$output_folder/native_stats/native_"$output_folder"_thresh.nii.gz
        get_most_sig_slice.sh $s/clusters/$output_folder/stats_cropped/crop_stats_thr_"${s##*/}"_native_cluster_"$i".nii.gz
        extract_most_sig_slice.sh $s/clusters/$output_folder/stats_cropped/crop_stats_thr_"${s##*/}"_native_cluster_"$i".nii.gz $s/clusters/$output_folder/stats_cropped/crop_stats_thr_"${s##*/}"_native_cluster_"$i".nii.gz_IntDen-Max_most-sig-slice.csv  
      done
    fi 

    # Make montage tiles for consensus
    if [ "$regional_counts" == "y" ] && [ "$make_montage" == "y" ]; then
      extract_most_sig_slice.sh $s/clusters/$output_folder/ABAconsensus_cropped/crop_ABAconsensus_"${s##*/}"_native_cluster_"$i".nii.gz $s/clusters/$output_folder/stats_cropped/crop_stats_thr_"${s##*/}"_native_cluster_"$i".nii.gz_IntDen-Max_most-sig-slice.csv
    elif [ "$make_montage" == "y" ]; then
      extract_most_sig_slice.sh $s/clusters/$output_folder/consensus_cropped/crop_consensus_"${s##*/}"_native_cluster_"$i".nii.gz $s/clusters/$output_folder/stats_cropped/crop_stats_thr_"${s##*/}"_native_cluster_"$i".nii.gz_IntDen-Max_most-sig-slice.csv
    fi

    # Crop raw data
    if [ "$raw_folders" != "n" ]; then
      for r in $raw_folders; do
        for i in $(eval echo "$clusters_to_process"); do
          cd $r
          first_tif=$(ls *.tif | head -1)
          cd ..
          crop_cluster.sh $s/clusters/$output_folder/bounding_boxes/"${s##*/}"_native_cluster_"$i"_fslstats_w.txt $r $s/$r/$first_tif
          if [ "$make_montage" == "y" ]; then 
           extract_most_sig_slice.sh $s/clusters/$output_folder/"$r"_cropped/crop_"$r"_"${s##*/}"_native_cluster_"$i".nii.gz $s/clusters/$output_folder/stats_cropped/crop_stats_thr_"${s##*/}"_native_cluster_"$i".nii.gz_IntDen-Max_most-sig-slice.csv
          fi
        done
      done
    fi

    rsync -au $s/clusters/$output_folder/ $exp_summary_dir/cluster_validation_summary/$output_folder
  done 
fi

for s in ${samples[@]}; do
  cd $s
  rsync -au $s/clusters/$output_folder/ $exp_summary_dir/cluster_validation_summary/$output_folder
done 

cd $exp_summary_dir

echo " " ; echo "Rerun validate_clusters.sh with: " ; echo " " 
echo "###############################################"
echo "$inputs"
echo "###############################################"
echo " " 

#Daniel Ryskamp Rijsketic 05/16/2022-06/21/2022 07/27/22-07/29/22 10/19-21/22/22 11/23/22 12/9/22
#Austen Casey (helped w/ summary scripts 8/2/22) (Heifets lab)
