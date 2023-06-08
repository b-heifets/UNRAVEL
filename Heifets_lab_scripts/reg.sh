#!/bin/bash
# (c) Daniel Ryskamp Rijsketic, Austen Casey, Boris Heifets @ Stanford University, 2021-2023

if [ $# == 0 ] || [ "$1" == "help" ]; then
  echo '
From experiment folder run: 
reg.sh <orientation code> <1 if olfactory bulb exists or 0> <w = wholebrain; l or r = left/right hemisphere> [leave blank to process all samples or enter sample?? separated by spaces]

Input: ./<EXP>/<sample??>/niftis/sample??_02x_down_autofl_chan.nii.gz
 
Determining 3 letter orientation codes (A/P=Anterior/Posterior, L/R=Left/Right, S/I=Superior/Interior):

  Open z-stack virtually in FIJI -> 1st letter is side facing up, 2nd is side facing left, 3rd is side at stack start
  (Think about this from the perspective of the detection objective) 
 
Check registration accuracy with ITK-SNAP: 
  From ./sample??/reg_final/ run: itksnap.sh or for ABA coloring run: itksnap.sh a
  Main image = ./reg_final/clar_downsample_res10um.nii.gz
  Segmentation = ./reg_final/gubra_ano_split_10um_clar_downsample.nii.gz 
  s toggles atlas, a decreases opacity, d increases opacity, control+j auto-adjusts brightness/contrast or Tools -> Image Contrast
  Log quality in Google sheet
  If using hemispheres, midline cuts are often not perfect. Extra tissue can be trimmed or missing tissue added with 3D Slicer
  For tutorials see: https://drive.google.com/drive/folders/1AQK6K560qjXgWJW9BKAR2SDnZik3tNWu?usp=sharing (parts could be outdated). 
  If a dim needs expansion, modify the tif series, remake the niftis, fix it in 3D slicer, & then rerun reg.sh 
'
  exit 1
fi

echo " " ; echo "Running reg.sh $@ from $PWD" ; echo " " 

if [ $# -gt 3 ]; then 
  sample_array=($(echo "${@:4}" | sed "s/['\"]//g"))
  sample_array=($(for i in ${sample_array[@]}; do echo $(basename $i) ; done))
else 
  sample_array=(sample??)
fi

for sample in ${sample_array[@]}; do
  cd $sample
  if [ ! -f reg_final/gubra_ano_split_10um_clar_downsample.nii.gz ]; then 
    echo "  Running reg.sh for $PWD"
    if [ "$3" == "w" ]; then
      miracl_reg_clar-allen_whole_brain_iDISCO.sh -i niftis/"$sample"_02x_down_autofl_chan.nii.gz -o $1 -m split -v 10 -b $2 
    elif [ "$3" == "l" ]; then
      miracl_reg_clar-allen_whole_brain_iDISCO.sh -i niftis/"$sample"_02x_down_autofl_chan.nii.gz -o $1 -m split -v 10 -b $2 -s lh
    elif [ "$3" == "r" ]; then
      miracl_reg_clar-allen_whole_brain_iDISCO.sh -i niftis/"$sample"_02x_down_autofl_chan.nii.gz -o $1 -m split -v 10 -b $2 -s rh
    else 
      echo "  Positional arg 3 is not w, l, or r (run: reg.sh help) "
    fi
  else
    echo "  Registration already complete for $PWD, skipping"
  fi
  cd ../  
done 

#Austen Casey 10/12/2021 & Daniel Ryskamp Rijsketic ~07/19/2021 & 06/09/22 (Heifets lab)
