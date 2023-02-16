#!/bin/bash
# (c) Daniel Ryskamp Rijsketic, Boris Heifets @ Stanford University, 2022-2023

if [ "$1" == "help" ]; then
  echo '
Run from sample folder:
ABAconsensus_3dc.sh <xy voxel size (um) or m (metadata)> <z voxel size or m> [leave blank to process all samples or enter sample?? separated by spaces]

First run reg.sh, ilastik.sh and consensus.sh

Inputs:
reg_final/gubra_ano_split_10um_clar_vox.nii.gz
consensus/sampleX_consensus.nii.gz

Outputs: 
sample??/sample??_ABAconsensus_stacks_25slices.csv

Use this script for region based 3D cell counts
'
  exit 1
fi

echo " " ; echo "Running ABAconsensus_3dc.sh $@ from $PWD" ; echo " "

if [ $# -gt 2 ]; then 
  sample_array=($(echo "${@:3}" | sed "s/['\"]//g"))
  sample_array=($(for i in ${sample_array[@]}; do echo $(basename $i) ; done)) 
else 
  sample_array=(sample??) 
fi

for sample in ${sample_array[@]}; do
  cd $sample

  #Convert consensus.tif to consensus.nii.gz if needed
  consensus_tif_to_nii.sh

  #ABA to native space
  ABA_to_native.sh $1 $2 #<xy voxel size (um) or m (metadata)> <z voxel size or m>

  #Convert consensus segmentation to ABA regional intensities
  ABAconsensus.sh

  SampleDir="$PWD"
  sample="$(basename $PWD)"

  #Convert seg objects to ABA intensities and generate 25 slice substacks using full verion of FIJI
  if [ ! -d consensus/ABAconsensus_stacks_25slices ]; then 
    echo "  Making $PWD/consensus/ABAconsensus_stacks_25slices" ; echo Start: $(date) ; echo " " 
    /usr/local/miracl/depends/Fiji.app/ImageJ-linux64 --ij2 -macro ABAconsensus_25sliceSubstacks "$PWD"/consensus/"$sample"_ABAconsensus.nii.gz
    echo "  Made $PWD/consensus/ABAconsensus_stacks_25slices" ; echo End: $(date) ; echo " " 
  fi 

  #3D object counting on the GPU (avoid parallel processing of 3D counting)
  if [ ! -f "$sample"_ABAconsensus_stacks_25slices.csv ]; then 

    echo " " ; echo "  Generating region specific 3D count: "$sample"_ABAconsensus_stacks_25slices.csv" ; echo Start: $(date) ; echo " " 

    cd $PWD/consensus/ABAconsensus_stacks_25slices

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
    find "all.csv" | xargs cut -d, -f16,37,39,40,42,43,45 > ABAconsensus_stacks_25slices.csv #extracts columns from all.csv 
    rm all.csv
    #rm *E.csv
    #rm *I.csv

    ###Copy CSV output to sample folder and rename
    cp ABAconsensus_stacks_25slices.csv "$SampleDir"/"$sample"_ABAconsensus_stacks_25slices.csv

    cd ../..

    echo "  Made region specific 3D count: "$sample"_ABAconsensus_stacks_25slices.csv" ; echo End: $(date) ; echo " " 

  fi 

  cd ..
done 

#Daniel Ryskamp Rijsketic 09/23/22 (Heifets lab)
