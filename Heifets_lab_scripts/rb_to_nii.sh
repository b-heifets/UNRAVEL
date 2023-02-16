#!/bin/bash
# (c) Daniel Ryskamp Rijsketic, Boris Heifets @ Stanford University, 2021-2023

if [ $# == 0 ] || [ "$1" == "help" ]; then
  echo '
From experiment folder containing ./sample??/ochann/tifs run:
rb.sh <three letter orientation code> <# of pixels for rolling ball radius> <x/y voxel size in microns or m for metadata> <z voxel size or m> [leave blank to process all samples or enter sample?? separated by spaces]

Subtracts background to improve signal to noise ratio
Then converts tif to nifti
Then warps the background subtracted downsampled raw data to atlas space

3 letter orientation codes (A/P=Anterior/Posterior, L/R=Left/Right, S/I=Superior/Interior): 
   Zeiss LS7: ALS in agarose (imaged w/ dorsal toward door & front up; in z-stacks A is up, L is left, S is at stack start) 
   Zeiss LS7: PLS if glued (imaged w/ dorsal toward door & front down; in z-stacks P is up, L is left, S is at stack start)
   UltraII: AIL=LH (imaged w/ medial side down & front facing back; in z-stacks A is up, I is left, L is at stack start) 
   UltraII: ASR=RH (imaged w/ medial side down & front facing back; in z-stacks A is up, S is left, R is at stack start)

The rolling ball radius should be at least equal to the radius of the largest object of interest. Larger values ok too.

If using for voxel-wise stats (glm.sh), afterwards move outputs to folder and run fsleyes.sh to check alignment of samples
If alignment not correct, use mirror.sh to flip (or flip.sh and shift.sh for custom adjustment)
'
  exit 1
fi

echo " " ; echo "Running rb.sh $@ from $PWD" ; echo " " 

if [ $# -gt 4 ]; then 
  sample_array=($(echo "${@:5}" | sed "s/['\"]//g"))
  sample_array=($(for i in ${sample_array[@]}; do echo $(basename $i) ; done)) 
else 
  sample_array=(sample??) 
fi

for sample in ${sample_array[@]}; do
  cd $sample

  cd ochann ; shopt -s nullglob ; for f in *\ *; do mv "$f" "${f// /_}"; done ; shopt -u nullglob ; cd .. #replace spaces w/ _ in tif series file names

  #Rolling ball subtraction 
  num_of_ochann_tifs="0" ; if [ -d ochann ]; then num_of_ochann_tifs=$(ls ochann | wc -l) ; fi
  num_of_ochann_rb_tifs="0" ; if [ -d ochann_rb$2 ]; then num_of_ochann_rb_tifs=$(ls ochann_rb$2 | wc -l) ; fi

  if (( $num_of_ochann_rb_tifs > 1 )) && (( $num_of_ochann_tifs == $num_of_ochann_rb_tifs )); then
    echo "  Rolling ball subtraction already run for "$sample", skipping" ; echo " " 
  else
    echo " " ; echo "  Rolling ball subtracting w/ pixel radius of $2 for $sample" ; echo " " 
    mkdir -p ochann_rb$2
    cd ochann
    first_tif=$(ls *.tif | head -1)
    /usr/local/miracl/depends/Fiji.app/ImageJ-linux64 --ij2 -macro rolling_ball_bkg_subtraction $PWD/$first_tif#$2
    cd ..
  fi

  #x and y dimensions need an even number of pixels for tif to nii.gz conversion
  if [ "$3" == "m" ]; then 
    metadata.sh
    xy_res=$(grep "Voxel size: " parameters/metadata | cut -d" " -f3 | cut -dx -f1)
    z_res=$(grep "Voxel size: " parameters/metadata | cut -d" " -f3 | cut -dx -f3)
  else
    xy_res=$3
    z_res=$4
  fi 

  ##Tif to nii.gz conversion
  if [ ! -f niftis/"$sample"_02x_down_ochann_rb$2_chan.nii.gz ] ; then
    echo "  Converting ochann_rb$2 tifs to nii.gz for $sample"
    miracl_conv_convertTIFFtoNII.py -f ochann_rb$2 -o "$sample" -d 2 -ch ochann_rb$2 -vx $xy_res -vz $z_res
  else 
    echo "  "$sample"_02x_down_ochann_rb$2_chan.nii.gz exists, skipping "
  fi

  cd ..
done 

# Daniel Ryskamp Rijsketic 12/7/21 & 07/07/22 (Heifets lab)
