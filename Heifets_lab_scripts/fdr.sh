#!/bin/bash 
# (c) Daniel Ryskamp Rijsketic, Austen Casey, Boris Heifets @ Stanford University, 2022-2023

if [ $# == 0 ] || [ "$1" == "help" ]; then
  echo '
fdr.sh <path/stat_image.nii.gz> <q_value (e.g., 0.05)> <min cluster size in voxels> <side of the brain (l, r, or both) or enter path/custom_mask>

Uses FSL'\''s fdr function to control the FDR across voxels, outputing an adjusted pvalimage (also an adjusted 1-p thresh)
Then, FSL'\''s cluster function is used to threshold the adjusted pvalimage and generate a cluster index image (image with sig clusters above the min cluster size)

If outside of Heifets lab, update path to template masks in script or use custom masks.
'
  exit 1
fi

echo " " ; echo "Running fdr.sh $@" ; echo " " 

orig_dir=$PWD
cd ${1%/*} #./glm/stats/
image=${1##*/}
results=${image::-7}_FDR"$2"_MinCluster"$3"

if [ ! -f $results/"$results"_rev_cluster_index.nii.gz ]; then 

  mkdir -p $results
  cp $1 $results/
  cd $results

  if [ $4 == "l" ]; then mask=/usr/local/miracl/atlases/ara/gubra/gubra_template_wo_OB_25um_full_bin_left.nii.gz
  elif [ $4 == "r" ]; then mask=/usr/local/miracl/atlases/ara/gubra/gubra_template_wo_OB_25um_full_bin_right.nii.gz
  elif [ $4 == "both" ]; then mask=/usr/local/miracl/atlases/ara/gubra/gubra_template_25um_thr30_bin.nii.gz
  else mask=$4 
  fi

  cp /usr/local/miracl/atlases/ara/gubra/gubra_ano_combined_25um.nii.gz ./

  #Voxel-wise FDR correction 
  echo "fdr -i $image --oneminusp -m $mask -q $2 --othresh=FDR$2-thresh_${image::-7} -a FDR$2-adjusted_${image::-7} " ; echo " " 
  fdr -i $image --oneminusp -m $mask -q $2 --othresh=FDR$2-thresh_${image::-7} -a FDR$2-adjusted_${image::-7} | tail -1 > Probability_Threshold 
  echo " " ; echo "Probability Threshold:" ; cat Probability_Threshold ; echo " "   
  OneMinusPthresh=$(echo "1-"$(cat Probability_Threshold) | bc -l | sed 's/^\./0./') #sed adds a 0 before the . if the result<1
  echo $OneMinusPthresh > 1-P_thresh 

  #Make clusters
  echo "cluster --in=FDR$2-adjusted_${image::-7} --oindex="$results"_cluster_index --olmax="$results"_lmax.txt --osize="$results"_cluster_size -t $(echo "scale=6;1-$2" | bc) --othresh="$results"_thresh --minextent=$3 " ; echo " " 
  cluster -i FDR$2-adjusted_${image::-7} --oindex="$results"_cluster_index --olmax="$results"_lmax.txt --osize="$results"_cluster_size -t $(echo "scale=6;1-$2" | bc) --othresh="$results"_thresh --minextent=$3 > "$results"_cluster_info.txt 
  cat "$results"_cluster_info.txt

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
  mkdir -p revID
  mv *_revID_*.nii.gz ./revID/
  echo $mask > mask_used_for_cluster_correction.txt
  echo $PWD > path_to_inputs_for_cluster_correction.txt

  echo " " ; echo "  Made FDR$2-adjusted_${image::-7} and "$results"_rev_cluster_index.nii.gz" ; echo " "
else 
  echo " " ; echo "  FDR$2-adjusted_${image::-7} and "$results"_rev_cluster_index.nii.gz exist, skipping" ; echo " " 
fi

cd $orig_dir


#Daniel Ryskamp Rijsketic 05/10-28/2022 & 07/25-28/22 & Austen Casey 07/25-29/22 (Heifets Lab)
