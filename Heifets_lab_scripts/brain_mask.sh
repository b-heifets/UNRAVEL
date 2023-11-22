#!/bin/bash

if [[ $# == 0 || "$1" == "-h" || "$1" == "--help" || "$1" == "help" ]] ; then
  echo '
From experiment folder with ./sample??/nifti/clar_res0.05.nii.gz, run:
brain_mask.sh <path/trained_ilastik_project.ilp> [leave blank to process all samples or enter sample?? separated by spaces]

When training ilastik, tissue should = label 1 and outside of the brain should = label 2.

Before running brain_mask.sh, train ilastik using tifs from ./sample??/niftis/autofl_50um/*.tif (from prep_reg.sh)
For help on ilastik, run: ilastik.sh -h 
 
Outputs: ./niftis/autofl_50um_seg_ilastik, ./autofl_50um_seg_ilastik.nii.gz, & ./clar_res0.05_masked.nii.gz

'
  exit 1
fi 

echo " " ; echo "Running brain_mask.sh $@ from $PWD" ; echo " "

if [ $# -gt 1 ]; then 
  samples=$(echo "${@:2}" | sed "s/['\"]//g")
  sample_array=($samples)
  sample_array=($(for i in ${sample_array[@]}; do echo $(basename $i) ; done)) 
else 
  sample_array=(sample??) 
fi

ilastik_project=$(echo $1 | sed "s/['\"]//g")

for sample in ${sample_array[@]}; do
  cd $sample
  sample_path=$PWD
  num_of_tifs=$(ls $3 | wc -l)

  mkdir -p niftis/autofl_50um_seg_ilastik
  num_of_input_tifs=$(ls niftis/autofl_50um | wc -l)
  num_of_output_tifs=$(ls niftis/autofl_50um_seg_ilastik | wc -l)
  if (( $num_of_output_tifs > 1 )) && (( $num_of_input_tifs == $num_of_output_tifs )); then
    echo "  ./niftis/autofl_50um_seg_ilastik exists, skipping "
  else
    echo " " ; echo "  Segmenting ./niftis/autofl_50um/*.tif starting at " $(date) ; echo " "
    mkdir -p log

    full_path_tifs="$PWD/niftis/autofl_50um/*.tif"

    echo "  run_ilastik.sh --headless --project=$ilastik_project --export_source="Simple Segmentation" --output_format=tif --output_filename_format=niftis/autofl_50um_seg_ilastik/{nickname}.tif $full_path_tifs" 

    run_ilastik.sh --headless --project=$ilastik_project --export_source="Simple Segmentation" --output_format=tif --output_filename_format=niftis/autofl_50um_seg_ilastik/{nickname}.tif $full_path_tifs

    echo " " ; echo "  brain_mask.sh finished at " $(date) ; echo " "
  fi

  # Convert Ilastik segmentation from tif series to .nii.gz 
  if [ ! -f niftis/autofl_50um_seg_ilastik.nii.gz ]; then 
    cd niftis/autofl_50um_seg_ilastik
    seg_series_to_nii.sh
    cd ..
    mv niftis.nii.gz autofl_50um_seg_ilastik.nii.gz
    fslmaths autofl_50um_seg_ilastik.nii.gz -bin autofl_50um_seg_ilastik.nii.gz -odt char # Use this if tissue = 1 and background = 2  

    # Invert the binary segmentation if needed (if tissue = 2 and outside = 1 in ilastik) as follows
    # fslmaths autofl_50um_seg_ilastik.nii.gz -bin -mul -1 -add 1 autofl_50um_seg_ilastik.nii.gz -odt char
    cd .. 
  fi

  #Apply mask to tissue
  if [ ! -f clar_res0.05_masked.nii.gz ]; then 
  cd niftis
  # Follow these steps as well if you needed to invert the brain mask.
  fslcpgeom clar_res0.05.nii.gz autofl_50um_seg_ilastik.nii.gz
  fslmaths clar_res0.05.nii.gz -mas autofl_50um_seg_ilastik.nii.gz clar_res0.05_masked.nii.gz -odt short
  cd ..
  fi 

  cd ..
done  

#Daniel Rijsketic adapted from ilastik.sh 08/25/23 (Heifets lab)



