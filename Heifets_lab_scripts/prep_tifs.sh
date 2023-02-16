#!/bin/bash
# (c) Daniel Ryskamp Rijsketic, Austen Casey, Boris Heifets @ Stanford University, 2021-2023

#For help message run: 488_prep_tifs.sh help
if [ $# == 0 ] || [ "$1" == "help" ]; then
  echo '
From experiment folder containing ./sample??/488/tifs, run:
488_prep_tifs.sh <enter 0 or min of new display range for 488> [leave blank to process all samples or enter sample?? separated by spaces]

Use 488_prep_tifs.sh to 1) make xy pixel dimensions even if needed (for 488_to_nii.sh) and 2) adjusts the display range min for 488 to improve registration to the averaged template by zeroing out most voxels outside of brain (otherwise, external voxels may pull atlas labels outward).
To determine display range min, open FIJI, open 488 (drag/drop folder into FIJI menu & check Use Virtual Stack), control+shift+t, set upper value to 0, adjust lower slider such that most, but not all, of background outside tissue is red. Use this # for the min.
For batch processing samples, do this for each sample and enter the min for the 488 display range as appropriate during the overview.sh part of find_clusters.sh

If the min display range for 488 was not adjusted when converting .czi to ./488/tifs and ./ochann/tifs, this script can be used for that.

If the min display range needs to be adjusted again, keep ./488_original/tifs and delete ./488/tifs and ./parameters/488_min

If min display range for 488 not adjusted, original tifs are in ./488/tifs
'
  exit 1
fi

echo " " ; echo "Running 488_prep_tifs.sh $@ from $PWD" ; echo " " 

#if more than 1 positional arguments provided, then: 
if [ $# -gt 1 ]; then 
  sample_array=($(echo "${@:2}" | sed "s/['\"]//g")) # echo positional args 2-n | ' marks removed if folders dragged/dropped into terminal
  sample_array=($(for i in ${sample_array[@]}; do echo $(basename $i) ; done)) #path(s) removed, so sample folder names remain in array
else 
  sample_array=(sample??) #assumes 2 digits for sample number
fi

for sample in ${sample_array[@]}; do
  cd $sample

  first_488_tif=$(ls 488_original | head -1)

  metadata.sh
  SizeX=$(sed -n 10p parameters/metadata | awk '{print $3}') #10th line, 3rd word
  SizeY=$(sed -n 11p parameters/metadata | awk '{print $3}')

  if [ "$1" == "0" ] && [ $((SizeX%2)) -eq 0 ] && [ $((SizeY%2)) -eq 0 ]; then #if 488 display range min is 0 and SizeX is even and SizeY is even, then 
    echo "  No display range adjustment & x/y dim are even, so leave ./488/tifs and ./ochann/tifs as is for $sample" ; echo " "
  else
    if [ ! -d 488_original ]; then mv 488 488_original ; mkdir -p 488; fi
    if [ ! -f parameters/488_min ] ; then
      echo " " ; echo "  Running prep_tifs.ijm for $sample" ; echo Start: $(date) ; echo " "
      #prep_tifs.ijm adjusts 488 min display range and makes 488 x and y pixel dim even for tif to nii.gz conversion if needed  

      if [ $((SizeX%2)) -eq 0 ] && [ $((SizeY%2)) -eq 0 ]; then #positional args follow macro w/ # delimiter
        /usr/local/miracl/depends/Fiji.app/ImageJ-linux64 --ij2 -macro prep_tifs $PWD/488_original/$first_488_tif#$1#SizeX_even#SizeY_even#488#_Ch1_ 
      elif [ $((SizeX%2)) -ne 0 ] && [ $((SizeY%2)) -eq 0 ]; then 
        /usr/local/miracl/depends/Fiji.app/ImageJ-linux64 --ij2 -macro prep_tifs $PWD/488_original/$first_488_tif#$1#SizeX_odd#SizeY_even#488#_Ch1_ 
      elif [ $((SizeX%2)) -eq 0 ] && [ $((SizeY%2)) -ne 0 ]; then
        /usr/local/miracl/depends/Fiji.app/ImageJ-linux64 --ij2 -macro prep_tifs $PWD/488_original/$first_488_tif#$1#SizeX_even#SizeY_odd#488#_Ch1_
      elif  [ $((SizeX%2)) -ne 0 ] && [ $((SizeY%2)) -ne 0 ]; then
        /usr/local/miracl/depends/Fiji.app/ImageJ-linux64 --ij2 -macro prep_tifs $PWD/488_original/$first_488_tif#$1#SizeX_odd#SizeY_odd#488#_Ch1_
      fi
      echo $1 > parameters/488_min
      if [ -f parameters/488_min ]; then echo "  Finished preprocessing 488 tifs for $sample" ; echo End: $(date) ; echo " " ; fi

    else
      echo "  488 tifs already preprocessed for $sample, skipping" ; echo " " 
    fi
  fi

  #Make ochann x and y pixel dim even for tif to nii.gz conversion if needed
  cd ochann ; shopt -s nullglob ; for f in *\ *; do mv "$f" "${f// /_}"; done ; shopt -u nullglob ; cd .. 

  if [ $((SizeX%2)) -ne 0 ] || [ $((SizeY%2)) -ne 0 ]; then
    echo "  Making ochann x and y pixel dim even for tif to nii.gz conversion for $sample " 
    first_ochann_tif=$(ls ochann | head -1)
    cp ochann ochann_original #ochann_original can be deleted to save space if same # of tifs in ochann and ochann_original, but keep first tif if it has metadata
  fi

  first_ochann_tif=$(ls ochann | head -1)

  if [ $((SizeX%2)) -ne 0 ] && [ $((SizeY%2)) -eq 0 ]; then
    /usr/local/miracl/depends/Fiji.app/ImageJ-linux64 --ij2 -macro prep_tifs $PWD/ochann/$first_ochann_tif#0#SizeX_odd#SizeY_even#ochann#_Ch2_ 
  elif [ $((SizeX%2)) -eq 0 ] && [ $((SizeY%2)) -ne 0 ]; then
    /usr/local/miracl/depends/Fiji.app/ImageJ-linux64 --ij2 -macro prep_tifs $PWD/ochann/$first_ochann_tif#0#SizeX_even#SizeY_odd#ochann#_Ch2_
  elif  [ $((SizeX%2)) -ne 0 ] && [ $((SizeY%2)) -ne 0 ]; then
    /usr/local/miracl/depends/Fiji.app/ImageJ-linux64 --ij2 -macro prep_tifs $PWD/ochann/$first_ochann_tif#0#SizeX_odd#SizeY_odd#ochann#_Ch2_
  fi

  if [ $((SizeX%2)) -ne 0 ] || [ $((SizeY%2)) -ne 0 ]; then
    old_filename_pattern=$(echo $first_ochann_tif | sed 's/0000/*/g')
    cd ochann
    rm -f $old_filename_pattern #delete old files so that only cropped files remain
    cd .. 
  fi

  cd ..
done 


# Austen Casey 10/09/21 & Daniel Ryskamp Rijsketic 12/07/21 & 07/07/22 & 07/18/22 (Heifets lab)
