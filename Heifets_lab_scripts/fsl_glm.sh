#!/bin/bash 

if [ $# == 0 ] || [ "$1" == "help" ] || [ "$1" == "--help" ] || [ "$1" == "-h" ]; then
  echo "
For a two-sample unpaired t-test (takes a few min): 
1) run from glm folder named succiently (e.g., glm_<EXP>)
2) add <condition1/2>_sample*_gubra_space.nii.gz files and follow prompts 
3) open inputs in fsleyes & the atlas to check alignment and that sides are correct:
fsleyes $(for i in *gz ; do echo <dollar>i -dr <min> <max> -d ; done) /usr/local/miracl/atlases/ara/gubra/gubra_ano_combined_25um.nii.gz -ot label -o
4) run fsl_glm.sh from glm folder and follow prompts (outputs to ./fsl_glm_stats/) 
tstat1 =  group 1 activity > group 2 (group order is alphabetical [use ls to check order])
tstat2 =  group 2 activity > group 1
"
  exit 1
fi 

#User inputs
echo " " 
read -p "Enter side of the brain to process (l, r, both) or (m) for mask specified by 1st positional argument: " mask ; echo " "
read -p "Enter additional fsl_glm options or just press enter (for help run: fsl_glm -h): " options ; echo " "
read -p "Enter kernel radius for smoothing w/ fslmaths in mm (e.g., 0.05): " kernel ; echo " " 
read -p "Enter p value threshold (e.g., for 0.05, use 0.975 in fsleyes for 2-tail threshold or 0.1 for 1-tail): " p_thr ; echo " " 

kernel_in_um=$(echo "($kernel*1000+0.5)/1" | bc) #(x+0.5)/1 is used for rounding in bash and bc handles floats

cp_mask_atlas () {
  if [ "$mask" == "l" ]; then 
    cp /usr/local/miracl/atlases/ara/gubra/gubra_template_wo_OB_25um_full_bin_left.nii.gz ./fsl_glm_stats/
    mask=gubra_template_wo_OB_25um_full_bin_left.nii.gz # voxels within mask included in GLM
  fi

  if [ "$mask" == "r" ]; then 
    cp /usr/local/miracl/atlases/ara/gubra/gubra_template_wo_OB_25um_full_bin_right.nii.gz ./fsl_glm_stats/
    mask=gubra_template_wo_OB_25um_full_bin_right.nii.gz
  fi

  if [ "$mask" == "both" ]; then 
    cp /usr/local/miracl/atlases/ara/gubra/gubra_template_25um_thr30_bin.nii.gz ./fsl_glm_stats/
    mask=gubra_template_25um_thr30_bin.nii.gz
  fi

  if [ "$mask" == "m" ]; then 
    cp $1 ./fsl_glm_stats/
    mask=${1##*/}
  fi

  cp /usr/local/miracl/atlases/ara/gubra/gubra_ano_combined_25um.nii.gz ./fsl_glm_stats/ 
}

output_name=${PWD##*/} # glm folder name

group1=$(find *.nii.gz -maxdepth 0 -type f | head -n 1 | cut -d _ -f 1) # get prefix for group1
group2=$(find *.nii.gz -maxdepth 0 -type f | tail -n 1 | cut -d _ -f 1)
group1_N=$(find "$group1"_* -maxdepth 0 -type f | wc -l)
echo " " 
echo "  Group 1 and N: $group1 $group1_N"
group2_N=$(find "$group2"_* -maxdepth 0 -type f | wc -l)
echo "  Group 2 and N: $group2 $group2_N"
echo " "

mkdir -p fsl_glm_stats

cp_mask_atlas $1

# Make single volume with all subject volumes
if [ ! -f ./fsl_glm_stats/all.nii.gz ] && [ -f ./stats/all.nii.gz ]; then cp ./stats/all.nii.gz ./fsl_glm_stats/ ; fi 
if [ ! -f ./fsl_glm_stats/all.nii.gz ]; then 
  echo "  Merging volumes" 
  fslmerge -t fsl_glm_stats/all.nii.gz *.nii.gz ; echo " " 
fi

# Make t-test design
cd fsl_glm_stats
design_ttest2 design "$group1_N" "$group2_N" 

# Log parameters
echo "Running fsl_glm.sh with mask: $mask, options: '$options', kernel: $kernel, from $PWD" > fsl_glm_params
echo "Group 1 and N: $group1 $group1_N" > groups.txt
echo "Group 2 and N: $group2 $group2_N" >> groups.txt
echo "*stat1: $group1 > $group2"  >> groups.txt
echo "*stat2: $group2 > $group1"  >> groups.txt

# Run fsl_glm 
if [ ! -f "$output_name"_z.nii.gz ]; then  
  if (( $kernel_in_um > 0 )); then 
    if [ ! -f all_s$kernel_in_um.nii.gz ] ; then cd .. ; cp ./stats/all_s$kernel_in_um.nii.gz ./fsl_glm_stats ; cd fsl_glm_stats ; fi
    if [ ! -f all_s$kernel_in_um.nii.gz ] ; then fslmaths all.nii.gz -s $kernel all_s$kernel_in_um.nii.gz ; fi
    fsl_glm_cmd="fsl_glm -i all_s$kernel_in_um.nii.gz -m $mask -d design.mat -c design.con --out_z="$output_name"_z.nii.gz $options"
  else
    fsl_glm_cmd="fsl_glm -i all.nii.gz -m $mask -d design.mat -c design.con --out_z="$output_name"_z.nii.gz $options"
  fi
fi 
if [ ! -f "$output_name"_z.nii.gz ]; then
  echo " " ; echo "  Running $fsl_glm_cmd" ; echo Start: $(date) ; echo " "
  echo "$fsl_glm_cmd" > fsl_glm_params
  $fsl_glm_cmd
  echo " " ; echo "  fsl_glm finished at " $(date) ; echo " "
fi 

if [ ! -f ${group1}_gt_${group2}_p-thr${p_thr}.nii.gz ] || [ ! -f ${group2}_gt_${group1}_p-thr${p_thr}.nii.gz ] ; then 

  echo "  Making directional p value maps from z map" 

  2-tailed conversion from p value to z-score threshold
  z_thr=$(ptoz $p_thr -2) 
  z_thr_neg="-$z_thr"
  echo "p value threshold used for making: $p_thr" > vox_p_map_params
  echo "z-score threshold used for making: $z_thr" >> vox_p_map_params
   
  # Create a positive threshold mask
  fslmaths "$output_name"_z.nii.gz -thr $z_thr -bin zstat_map_thresh_pos

  # Create a negative threshold mask
  fslmaths "$output_name"_z.nii.gz -uthr $z_thr_neg -mul -1 -bin zstat_map_thresh_neg

  # Generate p-value map from positive z-scores
  fslmaths "$output_name"_z.nii.gz -ztop -mas zstat_map_thresh_pos "$output_name"_p_pos.nii.gz
  fslmaths zstat_map_thresh_pos -sub "$output_name"_p_pos.nii.gz ${group1}_gt_${group2}_p-thr${p_thr}.nii.gz # 1-p map (group 1 > group 2)

  # Generate p-value map from negative z-scores
  fslmaths "$output_name"_z.nii.gz -mul -1 -ztop -mas zstat_map_thresh_neg "$output_name"_p_neg.nii.gz
  fslmaths zstat_map_thresh_neg -sub "$output_name"_p_neg.nii.gz ${group2}_gt_${group1}_p-thr${p_thr}.nii.gz

  rm zstat_map_thresh_pos.nii.gz zstat_map_thresh_neg.nii.gz "$output_name"_p_pos.nii.gz "$output_name"_p_neg.nii.gz

fi

cd ..

#Daniel Ryskamp Rijsketic & Austen Casey 9/21/21, 06/08/22, 11/08/23 
