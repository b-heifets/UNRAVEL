#!/bin/bash 
# (c) Daniel Ryskamp Rijsketic, Austen Casey, Boris Heifets @ Stanford University, 2021-2023

if [ "$1" == "help" ]; then echo " " 
    echo " sub.sh" ; echo " "
    echo " Run from folder with two *.nii.gz files"
    echo " Subtracts file1 from file2 and vice versa"
    echo " " ; exit 0
fi


file1=$(find *.nii.gz -maxdepth 0 -type f | head -n 1)
echo "File 1: $file1"
file1_basename=${file1%.nii.gz}

file2=$(find *.nii.gz -maxdepth 0 -type f | tail -n 1)
echo "File 2: $file2"
file2_basename=${file2%.nii.gz}

fslmaths "$file2" -sub "$file1" "$file2_basename"_minus_"$file1_basename".nii.gz
fslmaths "$file1" -sub "$file2" "$file1_basename"_minus_"$file2_basename".nii.gz
 

#Daniel Ryskamp Rijsketic & Austen Casey 11/23/21







 

