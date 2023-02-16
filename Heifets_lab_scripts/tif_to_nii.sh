#!/bin/bash
# (c) Daniel Ryskamp Rijsketic, Boris Heifets @ Stanford University, 2022-2023

if [ "$1" == "help" ]; then  
  echo '
Run from path with input files 
tif_to_nii.sh [leave blank to convert all tifs in working directory or enter path/image(s).tif separated by spaces>
'
  exit 1
fi

echo " " ; echo "Running tif_to_nii.sh $@ from $PWD" ; echo " " 

if (( $# == 0 )); then 
  image_array=(find $PWD -name "*.tif")
else 
  images=$(echo $@ | sed "s/['\"]//g")
  image_array=($images)
fi

for i in ${image_array[@]}; do
  echo " " ; echo "  Converting $i starting at " $(date)  ; echo " " 
  /usr/local/miracl/depends/Fiji.app/ImageJ-linux64 --ij2 -macro tif_to_nii $i
  mv $i.nii ${i%????}.nii
  gzip -9 -f ${i%????}.nii
  echo " " ; echo "  Finished converting $i at " $(date)  ; echo " "
done


#Daniel Ryskamp Rijsketic 07/11/22 (Heifets Lab)





