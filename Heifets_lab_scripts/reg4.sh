#!/bin/bash

if [[ $# == 0 || "$1" == "-h" || "$1" == "--help" || "$1" == "help" ]] ; then
  echo '
From experiment folder run: 
reg4.sh <orient code> <0, 1, or ./template.nii.gz> <w/l/r> <label res: 25> [sample?? list]

Input: ./<EXP>/<sample??>/reg_input/sample??_??x_down_*_chan.nii.gz
Optional: brain mask (faster): ./nifti/clar_res0.05_mask.nii.gz
    reg_input/autofl_50um_brain_mask.nii.gz
    reg_input/autofl_50um_masked.nii.gz

Detailed command:
reg4.sh <orient code> <1=OB, 0=OB, or ./custom_template.nii.gz> <w, l or r> <warped label res in tissue space: 10/25/50> [leave blank to process all samples or enter sample?? separated by spaces]

Determining 3 letter orientation codes (A/P=Anterior/Posterior, L/R=Left/Right, S/I=Superior/Interior):
  Open z-stack virtually in FIJI -> 1st letter is side facing up, 2nd is side facing left, 3rd is side at stack start
OB = Olfactory bulb
side: w, l or r = whole/left/right
Check registration accuracy with ITK-SNAP and log quality: 
  From ./reg_final run: itksnap.sh or for ABA coloring run: itksnap.sh a
  Main image = ./reg_final/clar_downsample_res10um.nii.gz
  Segmentation = ./reg_final/gubra_ano_split_10um_clar_downsample.nii.gz 
  s: toggle atlas, a/d: change opacity, ctrl+j auto B&C or Tools->Image Contrast'
  exit 1
fi

echo " " ; echo "Running reg4.sh $@ from $PWD" ; echo " " 

if [ $# -gt 4 ]; then 
  sample_array=($(echo "${@:5}" | sed "s/['\"]//g"))
  sample_array=($(for i in ${sample_array[@]}; do echo $(basename $i) ; done))
else 
  sample_array=(sample??)
fi

for sample in ${sample_array[@]}; do

  cd $sample

  if [ ! -f reg_final/gubra_ano_split_${4}um_clar_downsample.nii.gz ]; then 
    echo "  Running registration for $sample" ; echo " " 

    # Log registration command
    mkdir -p parameters
    echo reg4.sh $@ >> parameters/reg_parameters.txt

    # Use mask for faster registration if it exists (brain_mask.sh)
    mask=reg_input/autofl_50um_brain_mask.nii.gz
    autofl_masked=reg_input/autofl_50um_masked.nii.gz
    if [ -f $mask ] && [ -f $autofl_masked ] ; then
      reg_cmd=$(echo "registration4.sh -i $autofl_masked -o $1 -m split -v $4 -t $2 -x $mask")
    else
      reg_cmd=$(echo "registration4.sh -o $1 -m split -v $4 -t $2")
    fi

    # Run registration
    if [ "$3" == "w" ]; then
      echo "  $reg_cmd" ; echo " " ; $reg_cmd 
    elif [ "$3" == "l" ]; then
      echo "  $reg_cmd -s lh" ; echo " " ; $reg_cmd -s lh
    elif [ "$3" == "r" ]; then
      echo "  $reg_cmd -s rh" ; echo " " ; $reg_cmd -s rh
    else 
      echo "  Positional arg 3 is not w, l, or r (run: reg4.sh help) "
    fi

  else
    echo "  Registration already complete for $PWD, skipping"
  fi

  cd ../  

done 

#Austen Casey 10/12/2021 & Daniel Ryskamp Rijsketic ~07/19/2021 & 06/09/22 & 08/24-25/23 (Heifets lab)
