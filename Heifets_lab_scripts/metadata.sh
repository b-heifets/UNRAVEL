#!/bin/bash 

if [ "$1" == "help" ]; then 
  echo '
Run metadata.sh from the sample?? folder to generate a text file with metadata for getting image dim and voxel size

Outputs:6 ./sample??/parameters/metadata

Alternatively, open stack or first image in FIJI and control+i to view metadata
'
  exit 1
fi

if [ ! -f parameters/metadata ]; then 
  echo " " ; echo "Running metadata for ${PWD##*/}" ; echo " " 
  mkdir -p parameters

  if ls *.czi 1> /dev/null 2>&1; then 
    /usr/local/miracl/depends/Fiji.app/ImageJ-linux64 --ij2 -macro metadata $PWD/$(ls *.czi) > /dev/null 2>&1 #Zeiss file type
    mv metadata parameters/metadata
  elif [ -d 488_original ]; then
    cd 488_original
    first_tif=$(ls *.tif | head -1)
    shopt -s nullglob ; for f in *\ *; do mv "$f" "${f// /_}"; done ; shopt -u nullglob #remove spaces from tif series
    /usr/local/miracl/depends/Fiji.app/ImageJ-linux64 --ij2 -macro metadata $PWD/$first_tif > /dev/null 2>&1
    cd ..
    mv 488_original/metadata parameters/metadata
  else 
    cd 488
    first_tif=$(ls *.tif | head -1)
    shopt -s nullglob ; for f in *\ *; do mv "$f" "${f// /_}"; done ; shopt -u nullglob
    /usr/local/miracl/depends/Fiji.app/ImageJ-linux64 --ij2 -macro metadata $PWD/$first_tif > /dev/null 2>&1
    cd ..
    mv 488/metadata parameters/metadata
  fi
fi


#Daniel Ryskamp Rijsketic 07/07/22 & 07/18/22 & 07/28/22 (Heifets Lab)
