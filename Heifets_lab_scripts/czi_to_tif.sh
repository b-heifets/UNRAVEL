#!/bin/bash 

#For help message run: czi_to_tif.sh help
if [ $# == 0 ] || [ "$1" == "help" ]; then
  echo '
From experiment folder containing ./sample??/*.czi (one .czi in ./sample??/ w/ 2 channels [autofluorescence and other channel {ochann}]), run:
czi_to_tif.sh <0 or number for min of new 488 display range> [leave blank to process all samples or enter sample?? separated by spaces]
 
Adjusting the display range min for 488 can improve registration by zeroing out most voxels outside of brain (otherwise, external voxels may pull atlas labels outward)
To determine min, drag and drop the .czi file into FIJI'\''s menu and open it as a virtual stack to save time/RAM
Press control+shift+t, set upper value to 0, adjust lower slider such that most, but not all, of background outside tissue is red. Use this # for the min.
For batch processing samples, do this for each sample and enter the min for the 488 display range as appropriate during the overview.sh part of find_clusters.sh

If the min display range needs to be adjusted again, keep ./488_original/tifs, delete ./488/tifs and ./parameters/488_min, and run prep_tifs.sh <min of new display range for 488>

If min display range for 488 not adjusted, original tifs are in ./488/tifs
'
  exit 1
fi 

echo " " ; echo "Running czi_to_tif.sh $@ from $PWD" ; echo " " 

#if more than 1 positional arguments provided, then: 
if [ $# -gt 1 ]; then 
  sample_array=($(echo "${@:2}" | sed "s/['\"]//g")) # echo positional args 2-n | ' marks removed if folders dragged/dropped into terminal
  sample_array=($(for i in ${sample_array[@]}; do echo $(basename $i) ; done)) #path(s) removed, so sample folder names remain in array
else 
  sample_array=(sample??) #assumes 2 digits for sample number
fi

for sample in ${sample_array[@]}; do
  cd $sample
  
  czi=$(ls *.czi) #Zeiss file type
  
  if [ -f $czi ]; then 

    mkdir -p 488 ochann
    num_of_488_tifs=$(ls 488 | wc -l)
    num_of_ochann_tifs=$(ls ochann | wc -l)
  
    if (( $num_of_ochann_tifs > 1 )) && (( $num_of_488_tifs == $num_of_ochann_tifs )); then
      echo "  488 and ochann tifs for $sample exist, skipping" ; echo " "
    else
      echo "  Converting $PWD/$czi to 488 and ochann tifs for $sample " ; echo Start: $(date) ; echo " "

      if [ $1 != "0" ]; then mkdir -p 488_original ; fi 

      #x and y dimensions need an even number of pixels for tif to nii.gz conversion w/ MIRACL 
      metadata.sh 
      SizeX=$(sed -n 10p parameters/metadata | awk '{print $3}') #10th line, 3rd word
      SizeY=$(sed -n 11p parameters/metadata | awk '{print $3}')

      if [ $((SizeX%2)) -eq 0 ] && [ $((SizeY%2)) -eq 0 ]; then
        /usr/local/miracl/depends/Fiji.app/ImageJ-linux64 --ij2 -macro czi_to_tif $PWD/$czi#$1#SizeX_even#SizeY_even > /dev/null 2>&1
      elif [ $((SizeX%2)) -ne 0 ] && [ $((SizeY%2)) -eq 0 ]; then
        /usr/local/miracl/depends/Fiji.app/ImageJ-linux64 --ij2 -macro czi_to_tif $PWD/$czi#$1#SizeX_odd#SizeY_even > /dev/null 2>&1
      elif [ $((SizeX%2)) -eq 0 ] && [ $((SizeY%2)) -ne 0 ]; then
        /usr/local/miracl/depends/Fiji.app/ImageJ-linux64 --ij2 -macro czi_to_tif $PWD/$czi#$1#SizeX_even#SizeY_odd > /dev/null 2>&1
      else 
        /usr/local/miracl/depends/Fiji.app/ImageJ-linux64 --ij2 -macro czi_to_tif $PWD/$czi#$1#SizeX_odd#SizeY_odd > /dev/null 2>&1
      fi

      if (( $num_of_ochann_tifs > 1 )) && (( $num_of_488_tifs == $num_of_ochann_tifs )); then echo " " ; echo "  Converted .czi to 488 and ochann tifs for $sample " ; echo End: $(date) ; echo " " ; fi
    fi
  else
    echo "No .czi in $PWD" ; echo " " 
  fi
  cd ..
done  

#Daniel Ryskamp Rijsketic 06/08/22 & 07/07/22 (Heifets lab)
