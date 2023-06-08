#!/bin/bash 

if [ "$1" == "help" ]; then
   echo '
From ./reg_final/ run:
itksnap.sh [for ABA colors enter: a or path/LUT.txt] 
'
  exit 1
fi 

if [ "$1" == a ]; then
  echo " " ; echo "Running: itksnap -g clar_downsample_res*um.nii.gz -s *um_clar_downsample.nii.gz -l /home/bear/itksnap_Gubra_LUT.txt" ; echo " " 
  itksnap -g clar_downsample_res*um.nii.gz -s *um_clar_downsample.nii.gz -l /home/bear/itksnap_Gubra_LUT.txt
elif [ ! -z $1 ]; then
  lut=$(echo "$1" | sed "s/['\"]//g")
  echo " " ; echo "Running: itksnap -g clar_downsample_res*um.nii.gz -s *um_clar_downsample.nii.gz -l $1" ; echo " " 
  itksnap -g clar_downsample_res*um.nii.gz -s *um_clar_downsample.nii.gz -l $1
else 
  echo " " ; echo "Running: itksnap -g clar_downsample_res*um.nii.gz -s *um_clar_downsample.nii.gz" ; echo " " 
  itksnap -g clar_downsample_res*um.nii.gz -s *um_clar_downsample.nii.gz
fi 

#Daniel Ryskamp Rijsketic 03/16/23 (Heifets Lab)
