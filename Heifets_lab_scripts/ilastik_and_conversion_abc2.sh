#!/bin/bash

if [ $# == 0 ] || [ "$1" == "help" ]; then
  echo "
From experiment folder containing ./sample??/<immunofluor_folder>/tifs, run:
ilastik.sh <path/<EXP>_rater1.ilp (trained ilastik project)> <'{1..5}' (range for raters 1-5) or '1 2 4' (for specific rater(s))> <immunofluor label to be segmented> < [leave blank to process all samples or enter sample?? separated by spaces]
 
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

echo " " ; echo "Running ilastik.sh $@ from $PWD" ; echo " "

if [ $# -gt 3 ]; then 
  samples=$(echo "${@:4}" | sed "s/['\"]//g")
  sample_array=($samples)
  sample_array=($(for i in ${sample_array[@]}; do echo $(basename $i) ; done)) 
else 
  sample_array=(sample??) 
fi

exp_dir_path=$PWD
exp_summary_path=${1%/*}
cd $exp_summary_path
EXP=$(echo *.ilp | awk -F'_' '{print $1}') #abbreviation of experiment name
number_of_raters=$(ls "$EXP"_rater*.ilp | wc -l)

cd $exp_dir_path

for sample in ${sample_array[@]}; do
  cd $sample
  sample_path=$PWD
  num_of_tifs=$(ls $3 | wc -l)

  for i in $(eval echo $2); do 
    if [ -f "$3"_seg_ilastik_$i/"$sample"_"$3"_seg_ilastik_$i.nii.gz ] ; then
      echo "  IlastikSegmentation complete for $sample/"$3"_seg_ilastik_$i, skipping "
    else
      mkdir -p "$3"_seg_ilastik_$i "$3"_seg_ilastik_$i/IlastikSegmentation
      echo " " ; echo "  Running ilastik.sh for $EXP $sample rater $i" starting at $(date) ; echo " "
      echo "  run_ilastik.sh --headless --project=$exp_summary_path/"$EXP"_rater"$i".ilp --export_source="Simple Segmentation" --output_format=tif --output_filename_format="$3"_seg_ilastik_"$i"/IlastikSegmentation/{nickname}.tif "$3"/*.tif" 
      run_ilastik.sh --headless --project="$exp_summary_path"/"$EXP"_rater"$i".ilp --export_source="Simple Segmentation" --output_format=tif --output_filename_format="$3"_seg_ilastik_"$i"/IlastikSegmentation/{nickname}.tif "$3"/*.tif
      echo " " ; echo "  ilastik.sh for $EXP $sample rater $i finished at " $(date) ; echo " "

      echo "Converting "$3"_seg_ilastik_$i/IlastikSegmentation/tifs to "$3"_seg_ilastik_$i.nii.gz"
      first_tif=$(ls "$3"_seg_ilastik_$i/IlastikSegmentation | head -1)
      /usr/local/miracl/depends/Fiji.app/ImageJ-linux64 --ij2 -macro seg_series_to_nii "$3"_seg_ilastik_$i/IlastikSegmentation/$first_tif > /dev/null 2>&1
      gzip -9 -f "$3"_seg_ilastik_$i/"$3"_seg_ilastik_$i.nii 
      mv "$3"_seg_ilastik_$i/"$3"_seg_ilastik_$i.nii.gz "$3"_seg_ilastik_$i/"$sample"_"$3"_seg_ilastik_$i.nii.gz ;
    fi

    if [ -d "$3"_seg_ilastik_$i/IlastikSegmentation ]; then
      num_of_seg_tifs=$(ls "$3"_seg_ilastik_$i/IlastikSegmentation | wc -l)
      num_of_slices_in_nii=$(fslinfo "$3"_seg_ilastik_$i/"$sample"_"$3"_seg_ilastik_$i.nii.gz | awk 'NR == 4 {print $2}' | head -n 1)
      if [[ "$num_of_seg_tifs" == "$num_of_slices_in_nii" ]] ; then 
        echo "The number of Ilastiksegmentation tifs equals the number of slices in "$3"_seg_ilastik_$i.nii.gz, so deleting tifs"
        rm -r "$3"_seg_ilastik_$i/IlastikSegmentation
      fi
    fi
  done
  cd ..
done  


#Daniel Ryskamp Rijsketic 08/15/2021, 07/11/22, 11/03/23 (Heifets Lab), w/ the run_ilastik.sh command adapted from Dan Barbosa
#Austen Brooks Casey 07/13/2023 (Heifets Lab), edited such that custom immunofluor labels can be defined in seg_ilastik and tifs are converted to .nii.gz filetype

