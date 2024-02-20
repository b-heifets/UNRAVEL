#!/bin/bash 
# (c) Daniel Ryskamp Rijsketic, Austen Casey, Boris Heifets @ Stanford University, 2022-2023

if [ $# == 0 ] || [ "$1" == "help" ]; then
  echo '
fdr2.sh <path/stat_image.nii.gz> <side of the brain (l, r, or both) or enter path/custom_mask> <min cluster size in voxels> <q_value (e.g., 0.05)>

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
results=${image::-7}_FDR"$4"_MinCluster"$3"

if [ ! -f $results/"$results"_rev_cluster_index.nii.gz ]; then 

  mkdir -p $results
  cp $1 $results/
  cd $results

  if [ $2 == "l" ]; then mask=/usr/local/miracl/atlases/ara/gubra/gubra_template_wo_OB_25um_full_bin_left.nii.gz
  elif [ $2 == "r" ]; then mask=/usr/local/miracl/atlases/ara/gubra/gubra_template_wo_OB_25um_full_bin_right.nii.gz
  elif [ $2 == "both" ]; then mask=/usr/local/miracl/atlases/ara/gubra/gubra_template_25um_thr30_bin.nii.gz
  else mask=$2 
  fi

  cp /usr/local/miracl/atlases/ara/gubra/gubra_ano_combined_25um.nii.gz ./
  cp $mask ./

  #Voxel-wise FDR correction 
  echo "fdr -i $image --oneminusp -m $mask -q $4 --othresh=FDR$4-thresh_${image::-7} -a FDR$4-adjusted_${image::-7} " ; echo " " 
  fdr -i $image --oneminusp -m $mask -q $4 --othresh=FDR$4-thresh_${image::-7} -a FDR$4-adjusted_${image::-7} | tail -1 > Probability_Threshold 
  echo " " ; echo "Probability Threshold:" ; cat Probability_Threshold ; echo " "   
  OneMinusPthresh=$(echo "1-"$(cat Probability_Threshold) | bc -l | sed 's/^\./0./') #sed adds a 0 before the . if the result<1
  echo $OneMinusPthresh > 1-P_thresh 

  #Make clusters
  echo "cluster --in=FDR$4-adjusted_${image::-7} --oindex="$results"_cluster_index -t $(echo "scale=6;1-$4" | bc) --othresh="$results"_thresh --minextent=$3 " ; echo " " 
  cluster -i FDR$4-adjusted_${image::-7} --oindex="$results"_cluster_index -t $(echo "scale=6;1-$4" | bc) --othresh="$results"_thresh --minextent=$3 > "$results"_cluster_info.txt 
  cat "$results"_cluster_info.txt

  #Reverse cluster ID order in cluster_index 
  echo " " ; echo "  Reversing cluster order for $results" ; echo " " 
  index="$results"_cluster_index.nii.gz
  num_of_clusters=$(fslstats $index -R | cut -d ' ' -f2 | cut -d '.' -f1)
  clusters_to_process="{1..$num_of_clusters}"

  #Convert to 8-bit if possible
  if (( "$num_of_clusters" < "255" )); then 
    odt="-odt char"
  elif (( "$num_of_clusters" < "65535" )); then 
    odt="-odt short"
  fi

  fslmaths $index $index $odt

  #Make reverse cluster ID masks
  for i in $(eval echo $clusters_to_process); do
    revID=$(($num_of_clusters-$i+1))
    fslmaths $index -thr $i -uthr $i -bin -mul $revID ${index::-7}_revID_"$revID".nii.gz $odt
  done

  #Make blank vol and add revIDs to it
  fslmaths $index -sub $index "$results"_rev_cluster_index.nii.gz $odt
  revID_array=(*_revID_*.nii.gz)
  for i in ${revID_array[@]}; do 
     fslmaths "$results"_rev_cluster_index.nii.gz -add $i "$results"_rev_cluster_index.nii.gz $odt
  done
  mkdir -p revID
  mv *_revID_*.nii.gz ./revID/
  echo $mask > mask_used_for_cluster_correction.txt
  echo $PWD > path_to_inputs_for_cluster_correction.txt

  echo " " ; echo "  Made FDR$4-adjusted_${image::-7} and "$results"_rev_cluster_index.nii.gz" ; echo " "
else 
  echo " " ; echo "  FDR$4-adjusted_${image::-7} and "$results"_rev_cluster_index.nii.gz exist, skipping" ; echo " " 
fi

cd $orig_dir


#Daniel Ryskamp Rijsketic 05/10-28/2022 & 07/25-28/22 & Austen Casey 07/25-29/22 (Heifets Lab)
