#!/bin/bash
# (c) Daniel Ryskamp Rijsketic, Austen Casey, Boris Heifets @ Stanford University, 2022-2023

if [ $# == 0 ] || [ "$1" == "help" ]; then
  echo "
Run ez_thr.sh <path/vox_p.nii.gz> <side of the brain (l, r, or both) or path/custom_mask> <cluster_z_thresh> <cluster_prob_thresh>
 
This script runs the /usr/local/fsl/bin/easythresh
cluster_z_thresh is 1.644854 for one-tailed p-thr of 0.05 
cluster_z_thresh is 1.959964 for one-tailed p-thr of 0.025 
cluster_z_thresh is 2.326348 for one-tailed p-thr of 0.01 
cluster_z_thresh is 2.575829 for one-tailed p-thr of 0.005 
cluster_z_thresh is 3.090232 for one-tailed p-thr of 0.001 
cluster_z_thresh is 1.959964 for two-tailed p-thr of 0.05 
cluster_z_thresh is 2.241403 for two-tailed p-thr of 0.025 
cluster_z_thresh is 2.575829 for two-tailed p-thr of 0.01 
cluster_z_thresh is 2.807034 for two-tailed p-thr of 0.005 
cluster_z_thresh is 3.290527 for two-tailed p-thr of 0.001 
https://www.gigacalculator.com/calculators/p-value-to-z-score-calculator.php
0.05 for cluster_prob_thresh means <5% chance that resulting clusters are due to chance.
This accounts for spatial resolution, smoothness, etc..., to
determine a min size cluster meeting these criteria

FSL's easythresh function estimates smoothness of z-scored image and uses this for GRF-based cluster correction: 
https://www.freesurfer.net/pub/dist/freesurfer/tutorial_packages/OSX/fsl_501/bin/easythresh
https://fsl.fmrib.ox.ac.uk/fsl/fslwiki/Cluster
"
  exit 1
fi

echo " " ; echo "Running ez_thr.sh $@ " ; echo " " 

orig_dir=$PWD
cd ${1%/*} #./glm/stats/
image=${1##*/}
results=${image::-7}_ezThr$3

if [ ! -f $results/"$results"_rev_cluster_index.nii.gz ]; then 

  echo " " ; echo "  Converting p-values to z-value and running easythresh for $1 " ; echo Start: $(date) ; echo " "
 
  mkdir -p $results
  cd $results

  fslmaths $1 -sub $1 empty.nii.gz

  #Convert 1-p file into p:
  fslmaths $1 -sub 1 ${image::-7}_minus1.nii.gz
  fslmaths ${image::-7}_minus1.nii.gz -mul -1 ${image::-7}_minus1_times-1.nii.gz

  #Convert p to z
  fslmaths ${image::-7}_minus1_times-1.nii.gz -ptoz ${image::-7}_zstats.nii.gz

  #Define brain mask
  if [ $2 == "l" ]; then mask=/usr/local/miracl/atlases/ara/gubra/gubra_template_wo_OB_25um_full_bin_left.nii.gz
  elif [ $2 == "r" ]; then mask=/usr/local/miracl/atlases/ara/gubra/gubra_template_wo_OB_25um_full_bin_right.nii.gz
  elif [ $2 == "both" ]; then mask=/usr/local/miracl/atlases/ara/gubra/gubra_template_25um_thr30_bin.nii.gz 
  else mask=$(echo $2 | sed "s/['\"]//g")
  fi 

  #Script from FSL: easythresh <raw_zstats> <brain_mask> <cluster_z_thresh> <cluster_prob_thresh> <background_image> <output_root>
  echo "Running: easythresh ${image::-7}_zstats.nii.gz $mask $3 $4 empty.nii.gz ${image::-7}"  
  easythresh ${image::-7}_zstats.nii.gz $mask $3 $4 empty.nii.gz ${image::-7}
  mv cluster_${image::-7}.txt "$results"_cluster_info.txt
  mv rendered_thresh_$image "$results"_thresh.nii.gz
  mv cluster_mask_$image "$results"_cluster_index.nii.gz
  rm -f empty.nii.gz ${image::-7}_minus1.nii.gz ${image::-7}_minus1_times-1.nii.gz rendered_thresh_${image::-7}.png

  #Reverse cluster ID order in cluster_index 
  echo " " ; echo "  Reversing cluster order for $results" ; echo " " 
  index="$results"_cluster_index.nii.gz
  float=$(fslstats $index -R | awk '{print $2;}') # get 2nd word of output (max value in volume)
  num_of_clusters=${float%.*} # convert to integer
  clusters_to_process="{1..$num_of_clusters}"

  #Make reverse cluster ID masks
  for i in $(eval echo $clusters_to_process); do
    revID=$(($num_of_clusters-$i+1))
    fslmaths $index -thr $i -uthr $i -bin -mul $revID ${index::-7}_revID_"$revID".nii.gz
  done

  #Make blank vol and add revIDs to it
  fslmaths $index -sub $index "$results"_rev_cluster_index.nii.gz
  revID_array=(*_revID_*.nii.gz)
  for i in ${revID_array[@]}; do 
     fslmaths "$results"_rev_cluster_index.nii.gz -add $i "$results"_rev_cluster_index.nii.gz 
  done
  rm -f *_revID_*.nii.gz

  cd $orig_dir

  echo " " ; echo "  Finished running easythresh at "$(date) ; echo " "
else 
  echo " " ; echo "  cluster_mask_${image::-7} exists, skipping" ; echo " "
fi


#Austen Casey & Daniel Ryskamp Rijsketic 06/14/22, 07/28/22, 10/19/22 (Heifets lab)

