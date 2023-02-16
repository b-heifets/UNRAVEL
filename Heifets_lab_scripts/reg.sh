#!/bin/bash
# (c) Daniel Ryskamp Rijsketic, Austen Casey, Boris Heifets @ Stanford University, 2021-2023

if [ $# == 0 ] || [ "$1" == "help" ]; then
  echo '
From experiment folder run: 
reg.sh <1) three letter orientation code> <2) enter 0 for no olfactory bulb or 1 if OB exists> <3) enter w for wholebrains or l or r for left/right hemisphere> [leave blank to process all samples or enter sample?? separated by spaces]
Input: ./<EXP>/<sample??>/niftis/sample??_02x_down_autofl_chan.nii.gz
 
Determining 3 letter orientation codes (A/P=Anterior/Posterior, L/R=Left/Right, S/I=Superior/Interior) :

  Open z-stack in FIJI -> 1st letter is side facing up, 2nd is side facing left, 3rd is side at stack start

  Examples:
  Zeiss LS7: ALS in agarose (axial images w/ dorsal z-stack start, dorsal toward LSFM front, & anterior up; in z-stacks A is up, L is left, S is at stack start) 
  Zeiss LS7: PLS if glued (axial images w/ dorsal z-stack  start, dorsal toward LSFM front & anterior down; in z-stacks P is up, L is left, S is at stack start)
  UltraII: AIL=LH (sagittal images w/ lateral z-stack start, medial side down, & anterior toward LSFM back; in z-stacks A is up, I is left, L is at stack start) 
  UltraII: ASR=RH (sagittal images w/ lateral z-stack start, medial side down, & anterior toward LSFM back; in z-stacks A is up, S is left, R is at stack start) 
 
Check registration accuracy with ITK-SNAP: 
  Run: itksnap
  Drag and drop in ./reg_final/clar_downsample_res10um.nii.gz and load as main image
  Drag and drop in ./reg_final/gubra_ano_split_10um_clar_downsample.nii.gz and load as segmentation 
  s toggles atlas, a decreases opacity, d increases opacity, control+j auto-adjusts brightness/contrast 
  Log quality in Google sheet
  If using hemispheres, midline cuts are often not perfect. Extra tissue can be trimmed or missing tissue added with 3D Slicer
  For tutorials see: https://drive.google.com/drive/folders/1AQK6K560qjXgWJW9BKAR2SDnZik3tNWu?usp=sharing (parts could be outdated compared to scripts). Try to keep original niftis dimensions. If a dim really needs to expand for missing tissue to be added, expand it in the tif series for 488 and ochann, remake the niftis, fix it in 3D slicer, then rerun reg.sh 
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
