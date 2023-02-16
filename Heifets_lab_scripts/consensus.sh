#!/bin/bash
# (c) Daniel Ryskamp Rijsketic, Boris Heifets @ Stanford University, 2021-2023

if [ "$1" == "help" ]; then  
  echo '
Run this from experiment folder:
consensus.sh [leave blank to process all samples or enter sample?? separated by spaces]

If a pixel was classified as a cell by at least 3/5 raters using Ilastik, then preserve it as a cell
Input (requires 5 raters): EXP/sampleX/seg_ilastik_?/IlastikSegmentation/tifs (from ilastik.sh)
main output: <EXP>/sample??_consensus.nii.gz
'
  exit 1
fi

echo " " ; echo "Running consensus.sh $@ from $PWD" ; echo " " 

if [ $# -gt 0 ]; then 
  sample_array=($(echo "${@:1}" | sed "s/['\"]//g"))
  sample_array=($(for i in ${sample_array[@]}; do echo $(basename $i) ; done)) 
else 
  sample_array=(sample??) 
fi

for sample in ${sample_array[@]}; do
  cd $sample

  tifs_in_seg4=$(ls seg_ilastik_4/IlastikSegmentation | wc -l)
  tifs_in_seg5=$(ls seg_ilastik_4/IlastikSegmentation | wc -l)

  if (( $tifs_in_seg5 > 0 )) && (( $tifs_in_seg4 == $tifs_in_seg5 )); then 

    if [ -f consensus/"$sample"_consensus.tif ] && [ ! -f consensus/"$sample"_consensus.nii.gz ]; then 
      cd ..
      consensus_tif_to_nii.sh $sample
    fi

    if [ -f consensus/"$sample"_consensus.nii.gz ]; then 
      echo "  Consensus exists for "$sample", skipping" ; echo " "
    else 
      echo "  Making consensus tif for "$sample", w/ cells detected by >= 3/5 raters" ; echo " "
      mkdir -p consensus
      for i in {1..5} ; do 
        cd seg_ilastik_$i/IlastikSegmentation 
          declare IlaSeg$i="$PWD"
          declare FirstFile$i=$(ls | head -n 1) 
        cd ../..
      done 

      #macros split to reduce RAM load. If a seg tif series = 10GB (hemi), each part use 30GB of RAM.
      /usr/local/miracl/depends/Fiji.app/ImageJ-linux64 --ij2 -macro consensus_part1 $IlaSeg1/$FirstFile1#$IlaSeg2/$FirstFile2 
      /usr/local/miracl/depends/Fiji.app/ImageJ-linux64 --ij2 -macro consensus_part2 $IlaSeg3/$FirstFile3
      rm -f consensus/Result_of_seg_ilastik_1.tif
      /usr/local/miracl/depends/Fiji.app/ImageJ-linux64 --ij2 -macro consensus_part3 $IlaSeg4/$FirstFile4
      rm -f consensus/Result_of_seg_ilastik_3.tif
      /usr/local/miracl/depends/Fiji.app/ImageJ-linux64 --ij2 -macro consensus_part4 $IlaSeg5/$FirstFile5
      rm -f consensus/Result_of_seg_ilastik_4.tif
      mv consensus/consensus.nii consensus/"$sample"_consensus.nii
      gzip -9 -f consensus/"$sample"_consensus.nii
    
    fi 
  else 
    echo " " ; echo "  MISSING INPUTS. Rerun: ilastik.sh <path/<EXP>_rater1.ilp> '{1..5}' for "$sample"" ; echo " "
  fi 

  cd ..
done  


#Daniel Ryskamp Rijsketic 09/16/21 & 07/11/22 (Heifets Lab)





