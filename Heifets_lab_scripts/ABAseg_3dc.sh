#!/bin/bash

if [ "$1" == "help" ]; then
  echo '
Run from experiment folder:
ABAseg_3dc.sh <xy voxel size (um) or m (metadata)> <z voxel size or m> [leave blank to process all samples or enter sample?? separated by spaces]

First run reg.sh and ilastik.sh

Inputs:
reg_final/gubra_ano_split_10um_clar_vox.nii.gz
seg_ilastik_1/IlastikSegmentation/<1st_tif>

Outputs: 
sample??/sample??_ABAseg_stacks_25slices.csv

Use this script for region based 3D cell counts from a single rater
Adjust line 115 to select which columns you want from 3D counting output
'
  exit 1
fi

echo " " ; echo "Running ABAseg_3dc.sh $@ from $PWD" ; echo " "

if [ $# -gt 2 ]; then 
  sample_array=($(echo "${@:3}" | sed "s/['\"]//g"))
  sample_array=($(for i in ${sample_array[@]}; do echo $(basename $i) ; done)) 
else 
  sample_array=(sample??) 
fi

for sample in ${sample_array[@]}; do
  cd $sample
  SampleDir="$PWD"

  #Generate full resolution atlas in tissue space
  native_ABA=$PWD/reg_final/"$sample"_native_gubra_ano_split.nii.gz
  if [ ! -f $native_ABA ]; then
    ABA_to_native.sh $1 $2
  fi

  #Convert ./seg_ilastik_1/IlastikSegmentation/*tif to ./seg_ilastik_1/seg_ilastik_1.nii.gz
  seg=$PWD/seg_ilastik_1/seg_ilastik_1.nii.gz
  if [ ! -f $seg ]; then 
    original_dir=$PWD
    cd seg_ilastik_1/IlastikSegmentation
    seg_series_to_nii.sh #"rm" 
    cd $original_dir
  fi 

  #Multiply atlas by segmentation
  ABAseg=$PWD/seg_ilastik_1/ABAseg_ilastik_1.nii.gz
  if [ ! -f $ABAseg ]; then 
    echo " " ; echo "  Making $ABAseg " ; echo Start: $(date) ; echo " " 
    /usr/local/miracl/depends/Fiji.app/ImageJ-linux64 --ij2 -macro convert_to_ABA_intensities $native_ABA#$seg > /dev/null 2>&1
    mv $seg.nii ${ABAseg::-3}
    gzip -f -9 ${ABAseg::-3}
    echo " " ; echo "  Made $ABAseg " ; echo End: $(date) ; echo " " 
  else 
    echo " " ; echo "  $ABAseg exists, skipping" ; echo " " 
  fi

  #Convert seg objects to ABA intensities and generate 25 slice substacks using full verion of FIJI
  if [ ! -d seg_ilastik_1/ABAseg_stacks_25slices ]; then 
    echo "  Making $PWD/seg_ilastik_1/ABAseg_stacks_25slices" ; echo Start: $(date) ; echo " " 
    /usr/local/miracl/depends/Fiji.app/ImageJ-linux64 --ij2 -macro ABAseg_25sliceSubstacks $ABAseg > /dev/null 2>&1
    echo "  Made $PWD/seg_ilastik_1/ABAseg_stacks_25slices" ; echo End: $(date) ; echo " " 
  fi 

  #3D object counting on the GPU (avoid parallel processing of 3D counting)
  if [ ! -f "$sample"_ABAseg_stacks_25slices.csv ]; then 

    echo " " ; echo "  Generating region specific 3D count: "$sample"_ABAseg_stacks_25slices.csv" ; echo Start: $(date) ; echo " " 

    cd $PWD/seg_ilastik_1/ABAseg_stacks_25slices

    find . -path "*ExcludeEdges.tif" -exec java -jar /usr/local/miracl/depends/Fiji.app/jars/ij-1.53c.jar -ijpath /usr/local/miracl/depends/Fiji.app -macro ABAseg_3D_count_ExcludeEdges  "{}" \; #lite version of FIJI

    find . -path "*IncludeEdges.tif" -exec java -jar /usr/local/miracl/depends/Fiji.app/jars/ij-1.53c.jar -ijpath /usr/local/miracl/depends/Fiji.app -macro ABAseg_3D_count_IncludeEdges  "{}" \; 

    #Find e27 and i25 slice substack counting errors, split substacks with errors, rerun 3D count 
    for f in *.tif_*.csv; do
      case $f in 
        *_IncludeEdges.tif_I.csv)
          error=$(awk 'FNR == 3 {print}' $f)
          if [[ $error == *"error"* ]]; then
            echo "ERROR" in $f
            t=$f
            TifWithError=${t::-6}
            java -jar /usr/local/miracl/depends/Fiji.app/jars/ij-1.53c.jar -ijpath /usr/local/miracl/depends/Fiji.app -macro ABAseg_25include_split "$TifWithError"
            rm $f
            rm "$TifWithError"
            find . -path "*ExcludeSmall.tif" -exec java -jar /usr/local/miracl/depends/Fiji.app/jars/ij-1.53c.jar -ijpath /usr/local/miracl/depends/Fiji.app -macro ABAseg_3D_count_ExcludeEdges  "{}" \;
            find . -path "*IncludeSmall.tif" -exec java -jar /usr/local/miracl/depends/Fiji.app/jars/ij-1.53c.jar -ijpath /usr/local/miracl/depends/Fiji.app -macro ABAseg_3D_count_IncludeEdges  "{}" \;
          fi
      ;;
        *_ExcludeEdges.tif_E.csv)
          error=$(awk 'FNR == 3 {print}' $f)
          if [[ $error == *"error"* ]]; then
            echo "ERROR" in $f
            t=$f
            TifWithError=${t::-6}
            java -jar /usr/local/miracl/depends/Fiji.app/jars/ij-1.53c.jar -ijpath /usr/local/miracl/depends/Fiji.app -macro ABAseg_27exclude_split "$TifWithError"
            rm $f
            rm "$TifWithError"
            find . -path "*ExcludeSmall.tif" -exec java -jar /usr/local/miracl/depends/Fiji.app/jars/ij-1.53c.jar -ijpath /usr/local/miracl/depends/Fiji.app -macro ABAseg_3D_count_ExcludeEdges  "{}" \;
            find . -path "*IncludeSmall.tif" -exec java -jar /usr/local/miracl/depends/Fiji.app/jars/ij-1.53c.jar -ijpath /usr/local/miracl/depends/Fiji.app -macro ABAseg_3D_count_IncludeEdges  "{}" \;
          fi
        ;;
      esac
    done

    #concatenate csvs
    cat *csv > all.csv
    find "all.csv" | xargs cut -d, -f16,37,39,40,42,43,45 > ABAseg_stacks_25slices.csv #extracts columns from all.csv 
    rm all.csv
    #rm *E.csv
    #rm *I.csv

    ###Copy CSV output to sample folder and rename
    cp ABAseg_stacks_25slices.csv "$SampleDir"/"$sample"_ABAseg_stacks_25slices.csv

    cd ../..

    echo "  Made region specific 3D count: "$sample"_ABAseg_stacks_25slices.csv" ; echo End: $(date) ; echo " " 

  fi 

  cd ..
done 

#Daniel Ryskamp Rijsketic 09/23/22 & 04/26/23 (Heifets lab)
