#!/bin/bash 
# (c) Daniel Ryskamp Rijsketic, Austen Casey, Boris Heifets @ Stanford University, 2021-2023

if [ $# == 0 ] || [ "$1" == "help" ]; then  
  echo '
Run this from folder containing NiFTi files in atlas space:
z_brain_template_mask.sh <Enter side of the brain (l, r, or both)> [leave blank to process *_gubra_space.nii.gz or enter images separated by spaces]

Outputs z-scored volume (<image>_z_gubra_space.nii.gz)

z-score = (<image>_gubra_space.nii.gz - mean pixel intensity in brain)/standard dev of intensity in brain

Update path/template_mask in script if needed
'
  exit 1
fi

echo " " ; echo "Running z_brain_template_mask.sh $@ from $PWD" ; echo " "

if [ $1 == "l" ]; then template=/usr/local/miracl/atlases/ara/gubra/gubra_template_wo_OB_25um_full_bin_left.nii.gz ; fi
if [ $1 == "r" ]; then template=/usr/local/miracl/atlases/ara/gubra/gubra_template_wo_OB_25um_full_bin_right.nii.gz ; fi
if [ $1 == "both" ]; then template=/usr/local/miracl/atlases/ara/gubra/gubra_template_25um_thr30_bin.nii.gz ; fi

if [ $# -gt 1 ]; then 
  image_array=($(echo "${@:2}" | sed "s/['\"]//g"))
  image_array=($(for i in ${image_array[@]}; do echo $(basename $i) ; done))
else 
  image_array=(*_gubra_space.nii.gz)
fi

for i in ${!image_array[@]}; do
  if [ ! -f ${image_array[$i]::-19}_z_gubra_space.nii.gz ]; then 

  echo "  Z-scoring ${image_array[$i]}, starting at" $(date)

  # Zero out voxels outside atlas template
  fslmaths ${image_array[$i]} -mas $template ${image_array[$i]::-7}_masked.nii.gz 

  # Get mean intensity for all nonzero voxels
  masked_mean=$(fslstats ${image_array[$i]::-7}_masked.nii.gz -M)

  # Generate Z-score numerator by subtracting masked_mean from each voxel in the brain mask 
  fslmaths ${image_array[$i]::-7}_masked.nii.gz -sub $masked_mean -mas $template ${image_array[$i]::-7}_numerator.nii.gz 

  # Calculate the standard deviation of the image for nonzero voxels
  SD=$(fslstats ${image_array[$i]::-7}_masked.nii.gz -S) 

  # Z-score the image
  fslmaths ${image_array[$i]::-7}_numerator.nii.gz -div $SD ${image_array[$i]::-19}_z_gubra_space.nii.gz

  rm ${image_array[$i]::-7}_masked.nii.gz ${image_array[$i]::-7}_numerator.nii.gz

  echo "  Boom, you z-scored ${image_array[$i]}!" $(date) ; echo " "

else 
  echo "${image_array[$i]::-19}_z_gubra_space.nii.gz exists, skipping"
fi
done 


#Austen Casey 11/23/21-2/22/22 & Daniel Ryskamp Rijsketic 11/23/21 & 07/21/22 (Heifets Lab)
