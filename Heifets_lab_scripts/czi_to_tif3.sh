#!/bin/bash 

#For help message run: czi_to_tif3.sh help
if [[ $# == 0 || "$1" == "-h" || "$1" == "--help" || "$1" == "help" ]] ; then
  echo '
From the experiment folder run: 
czi_to_tif3.sh <488> <ochann> [sample?? list]

Detailed command notes: 
From experiment folder containing ./sample??/*.czi (one .czi in ./sample??/ w/ 2 channels [autofluorescence and other channel {ochann}]), run:
czi_to_tif3.sh <folder name for 1st channel (e.g., 488)> <folder name for 2nd channel (e.g., ochann)> [leave blank to process all samples or enter sample?? separated by spaces]

Outputs a tif series for each channel in specified folders
'
  exit 1
fi 

echo " " ; echo "Running czi_to_tif3.sh $@ from $PWD" ; echo " " 

#if more than 2 positional arguments provided, then: 
if [ $# -gt 2 ]; then 
  sample_array=($(echo "${@:3}" | sed "s/['\"]//g")) # echo positional args 2-n | ' marks removed if folders dragged/dropped into terminal
  sample_array=($(for i in ${sample_array[@]}; do echo $(basename $i) ; done)) #path(s) removed, so sample folder names remain in array
else 
  sample_array=(sample??) #assumes 2 digits for sample number
fi

for sample in ${sample_array[@]}; do
  cd $sample
  
  czi=$(ls *.czi) #Zeiss file type
  
  if [ -f $czi ]; then 

    mkdir -p $1 $2
    num_of_ch0_tifs=$(ls $1 | wc -l)
    num_of_ch1_tifs=$(ls $2 | wc -l)
  
    if (( $num_of_ch1_tifs > 1 )) && (( $num_of_ch0_tifs == $num_of_ch1_tifs )); then
      echo "  $1 and $2 tifs for $sample exist, skipping" ; echo " "
    else
      echo "  Converting $czi to $1 and $2 tifs for $sample " ; echo Start: $(date) ; echo " "

      /usr/local/miracl/depends/Fiji.app/ImageJ-linux64 --ij2 -macro czi_to_tif3 $PWD/$czi#$1#$2 > /dev/null 2>&1

      if (( $num_of_ch1_tifs > 1 )) && (( $num_of_ch0_tifs == $num_of_ch1_tifs )); then 
        echo " " ; echo "  Converted .czi to $1 and $2 tifs for $sample " ; echo End: $(date) ; echo " "
      fi

    fi

  else
    echo "No .czi in $PWD" ; echo " " 
  fi
  cd ..
done  

#Daniel Ryskamp Rijsketic 06/08/22 & 07/07/22 & 08/25/23 (Heifets lab)
