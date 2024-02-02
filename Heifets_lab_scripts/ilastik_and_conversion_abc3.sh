#!/bin/bash

if [ $# == 0 ] || [ "$1" == "help" ] || [ "$1" == "--help" ] || [ "$1" == "-h" ] ; then
  echo "
From experiment folder containing ./sample??/<cfos>/tifs, run:
ilastik_and_conversion_abc3.sh <path/cfos_rater1.ilp (trained ilastik project named like this)> [leave blank to process all samples or enter sample?? separated by spaces]
 
This script creates the active cell segmentation using Ilastik's pixel classification workflow

To train an Ilastik project, organize training slices into folder (e.g., 3 slices from 3 samples per condition)
launch ilastik (e.g., by running: ilastik)
Pixel Classification -> save as <EXP>_rater1.ilp 
https://www.ilastik.org/documentation/pixelclassification/pixelclassification

1. Input Data 
   Raw data -> Add New...-> Add Separate Image(s)... -> select training slices -> Open
   ctrl+A -> right click -> Edit shared properties -> Storage: Copy into project file -> Ok 

2. Feature Selection
   Select Features... -> select same predefined features for each rater 
   (To choose a subset of features, initially select all [control+a], then refine later)

3. Training
   Double click yellow square -> click yellow rectangle (Color for drawing) -> click in triangle and drag to the right to change color to red -> ok
   Adjust brightness and contrast as needed (select gradient button and click and drag slowly in the image as needed
   Use control + mouse wheel scroll to zoom, press mouse wheel and drag image to pan (faster if zoomed in)
   With label 1 selected, paint on cells
   With label 2 selected, paint on background
   Turn on Live Update to preview pixel classification (faster if zoomed in) and refine training. 
   If label 1 fuses neighboring cells, draw a thin line in between them with label 2. 
   Toggle eyes show/hide layers 
   The segmentation will be exported, so turn off the Prediction for Label1/2. 
   Turn alpha (opacity) for Segmentation (Label 2) to 0% and then you can presss on the keyboard to toggle on and off  Segmentation (Label 1). 
   If you accidentally pressa and add an extra label, turn off Live Updates and press X to delete the extra label
   If you want to go back too steps 1 & 2, turn off Live Updates off
   ChangeCurrent view to see other training slices. Check segmentation for these and refine as needed.
   Optional: With fewer features segmentation is faster and less RAM intensive but less accurate
   To speed up processing find a subset of suggested features to use by: 
   Train ilastik initially with all features, turn off Live Updates, click Suggest Features, choose number of features used for pixel classification (7 features is default, but to select number of features automatically, enter 0), Run Feature Selection, from menus at bottom of window note the error and computation time, also record features from Show Feature Names, and click Select Feature Set. Selected features can also be noted by going by to step 2 (Feature Selection). Use the same set of features for all raters (people that indepdently train ilastik) for all samples for a specific experiment. If it is difficult to train ilastik to distinguish cells from non-cells, adding features might improve performance. 
   Refine training with subset of features. /SSD2/olson
   Save the project in experiment summary folder and close if using this script to run ilastik in headless mode for segmenting all images. 
   If using the GUI, proceed to steps 4 and 5. 

4. Prediction Export
   Source: Simple Segmentation
   Choose Export Image Settings... -> Format: -> tif -> if desired, replace {dataset_dir} with path where you want to export segmented images and leave /{nickname}_{result_type}.tif or /{nickname}.tif

5. Batch Processing
   Select Raw Data Files... -> Select all immunofluor images to process
   Process all files (if you cancel processing, Clear Raw Data Files and again Select Raw Data Files..., otherwise the project will become corrupted).
"
  exit 1
fi 

echo " " ; echo "Running ilastik_and_conversion_abc3.sh $@ from $PWD" ; echo " "

if [ $# -gt 1 ]; then 
  samples=$(echo "${@:2}" | sed "s/['\"]//g")
  sample_array=($samples)
  sample_array=($(for i in ${sample_array[@]}; do echo $(basename $i) ; done)) 
else 
  sample_array=(sample??) 
fi

ilp_path=$(echo $1 | sed "s/['\"]//g")
label=$(echo ${ilp_path##*/} | cut -d'_' -f1) # Immunolabel
rater=$(echo $ilp_path | cut -d'_' -f2 | cut -d '.' -f1)
rater=${rater: 5} # Trim "rater" 

for sample in ${sample_array[@]}; do
  cd $sample
  sample_path=$PWD
  num_of_tifs=$(ls $label | wc -l)

  if [ -f "$label"_seg_ilastik_$rater/"$sample"_"$label"_seg_ilastik_$rater.nii.gz ] ; then
    echo "  IlastikSegmentation complete for $sample/"$label"_seg_ilastik_$rater, skipping "
  else
    mkdir -p "$label"_seg_ilastik_$rater "$label"_seg_ilastik_$rater/IlastikSegmentation
    echo " " ; echo "  Running ilastik_and_conversion_abc3.sh for $label $sample rater $rater" starting at $(date) ; echo " "
    echo "  run_ilastik.sh --headless --project=$ilp_path --export_source="Simple Segmentation" --output_format=tif --output_filename_format="$label"_seg_ilastik_"$rater"/IlastikSegmentation/{nickname}.tif "$label"/*.tif" 
    run_ilastik.sh --headless --project="$ilp_path" --export_source="Simple Segmentation" --output_format=tif --output_filename_format="$label"_seg_ilastik_"$rater"/IlastikSegmentation/{nickname}.tif "$label"/*.tif
    echo " " ; echo "  ilastik.sh for $label $sample rater $rater finished at " $(date) ; echo " "

    echo "Converting "$label"_seg_ilastik_$rater/IlastikSegmentation/tifs to "$label"_seg_ilastik_$rater.nii.gz"
    first_tif=$(ls "$label"_seg_ilastik_$rater/IlastikSegmentation | head -1)
    /usr/local/miracl/depends/Fiji.app/ImageJ-linux64 --ij2 -macro seg_series_to_nii "$label"_seg_ilastik_$rater/IlastikSegmentation/$first_tif > /dev/null 2>&1
    gzip -9 -f "$label"_seg_ilastik_$rater/"$label"_seg_ilastik_$rater.nii 
    mv "$label"_seg_ilastik_$rater/"$label"_seg_ilastik_$rater.nii.gz "$label"_seg_ilastik_$rater/"$sample"_"$label"_seg_ilastik_$rater.nii.gz ;
  fi

  if [ -d "$label"_seg_ilastik_$rater/IlastikSegmentation ]; then
    num_of_seg_tifs=$(ls "$label"_seg_ilastik_$rater/IlastikSegmentation | wc -l)
    num_of_slices_in_nii=$(fslinfo "$label"_seg_ilastik_$rater/"$sample"_"$label"_seg_ilastik_$rater.nii.gz | awk 'NR == 4 {print $2}' | head -n 1)
    if [[ "$num_of_seg_tifs" == "$num_of_slices_in_nii" ]] ; then 
      echo "The number of Ilastiksegmentation tifs equals the number of slices in "$label"_seg_ilastik_$rater.nii.gz, so deleting tifs"
      rm -r "$label"_seg_ilastik_$rater/IlastikSegmentation
    fi
  fi
  cd ..
done  


#Daniel Ryskamp Rijsketic 08/15/2021, 07/11/22, 11/03/23, 01/04/24 (Heifets Lab), w/ the run_ilastik.sh command adapted from Dan Barbosa
#Austen Brooks Casey 07/13/2023 (Heifets Lab), edited such that custom immunofluor labels can be defined in seg_ilastik and tifs are converted to .nii.gz filetype

