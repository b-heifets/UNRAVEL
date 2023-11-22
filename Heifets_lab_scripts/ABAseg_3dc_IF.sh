#!/bin/bash

if [ $# == 0 ] || [ "$1" == "-h" ] || [ "$1" == "--help" ] || [ "$1" == "help" ]; then
  echo '
Run from experiment folder:
ABAseg_3dc_IF.sh <full_path_to_native_atlas/[rev_shift_log]gubra_ano_split_25um.nii.gz> <immunofluor label> <rater #> [leave blank to process all samples or enter sample?? separated by spaces]

First run reg.sh and ilastik.sh

If shift2.sh is used for IF images in atlas space, then use rev_shift.sh on the atlas before 3D counting. 

Other input:
${2}_seg_ilastik_${3}/IlastikSegmentation/<1st_tif>

Outputs: 
sample??/sample??_${2}_ABAseg_${3}_stacks_25slices.csv

Use this script for region based 3D cell counts from a single rater
'
  exit 1
fi

echo " " ; echo "Running ABAseg_3dc_IF.sh $@ from $PWD" ; echo " "

if [ $# -gt 3 ]; then 
  sample_array=($(echo "${@:4}" | sed "s/['\"]//g"))
  sample_array=($(for i in ${sample_array[@]}; do echo $(basename $i) ; done)) 
else 
  sample_array=(sample??) 
fi

for sample in ${sample_array[@]}; do
  cd $sample
  SampleDir="$PWD"

  native_atlas=$(echo $1 | sed "s/['\"]//g")
  if [ -f $native_atlas ]; then
    echo "  Native atlas: $native_atlas" ; echo " " 
  else 
    echo "  Native atlas ($native_atlas) does not exist" ; exit 1 
  fi

  echo $1 >> $PWD/parameters/atlas_used_for__${2}_seg_ilastik_${3}__ABAseg_3dc_IF.txt

  seg=$PWD/${2}_seg_ilastik_${3}/${sample}_${2}_seg_ilastik_${3}.nii.gz
  if [ -f $seg ]; then
    echo "  Segmentation: $seg" ; echo " " 
  else 
    echo "  Native atlas ($native_atlas) does not exist" ; exit 1 
  fi

  # Multiply atlas by segmentation
  ABAseg=$PWD/${2}_seg_ilastik_${3}/${sample}_ABA_${2}_seg_ilastik_${3}.nii.gz
  if [ ! -f $ABAseg ]; then 
    echo " " ; echo "  Making $ABAseg " ; echo Start: $(date) ; echo " " 
    echo "  /usr/local/miracl/depends/Fiji.app/ImageJ-linux64 --ij2 -macro convert_to_ABA_intensities $native_atlas#$seg" 
    /usr/local/miracl/depends/Fiji.app/ImageJ-linux64 --ij2 -macro convert_to_ABA_intensities $native_atlas#$seg > /dev/null 2>&1
    mv $seg.nii ${ABAseg::-3}
    gzip -f -9 ${ABAseg::-3}
    echo " " ; echo "  Made $ABAseg " ; echo End: $(date) ; echo " " 
  else 
    echo " " ; echo "  $ABAseg exists, skipping" ; echo " " 
  fi

  # Convert seg objects to ABA intensities and generate 25 slice substacks using full verion of FIJI
  if [ ! -d ${2}_seg_ilastik_${3}/ABAseg_stacks_25slices ]; then 
    echo "  Making $PWD/${2}_seg_ilastik_${3}/ABAseg_stacks_25slices" ; echo Start: $(date) ; echo " " 
    echo "  /usr/local/miracl/depends/Fiji.app/ImageJ-linux64 --ij2 -macro 25sliceSubstacks $ABAseg#ABAseg"
    /usr/local/miracl/depends/Fiji.app/ImageJ-linux64 --ij2 -macro 25sliceSubstacks $ABAseg#ABAseg > /dev/null 2>&1
    gzip -f -9 $PWD/${2}_seg_ilastik_${3}/ABAseg_stacks_25slices/*.nii
    echo "  Made $PWD/${2}_seg_ilastik_${3}/ABAseg_stacks_25slices" ; echo End: $(date) ; echo " " 
  fi 

  # 3D object counting on the GPU (avoid parallel processing of 3D counting)
  output="$sample"_ABA_${2}_seg_ilastik_${3}_stacks_25slices.csv
  if [ ! -f $output ]; then 

    echo " " ; echo "  Generating region specific 3D count: $output" ; echo Start: $(date) ; echo " " 

    cd $PWD/${2}_seg_ilastik_${3}/ABAseg_stacks_25slices

    # find $PWD -path "*ExcludeEdges.nii.gz" -exec /usr/local/miracl/depends/Fiji.app/ImageJ-linux64 --ij2 -macro 3D_count_ExcludeEdges  "{}" \;
    find $PWD -path "*ExcludeEdges.nii.gz" -exec sh -c '{
      echo "  /usr/local/miracl/depends/Fiji.app/ImageJ-linux64 --ij2 -macro 3D_count_ExcludeEdges $1"
      /usr/local/miracl/depends/Fiji.app/ImageJ-linux64 --ij2 -macro 3D_count_ExcludeEdges "$1" > /dev/null 2>&1
      gpu_memory_error=$(grep error ${1}_E.csv)
      if [ ! -z "$gpu_memory_error" ]; then
        echo ERROR: $gpu_memory_error
      else
        cell_count=$((( $(cat ${1}_E.csv | wc -l) - 1 )))
        echo "  Cell Count: $cell_count"
      fi 
      echo " " 
    }' sh {} \;

    # find $PWD -path "*IncludeEdges.nii.gz" -exec /usr/local/miracl/depends/Fiji.app/ImageJ-linux64 --ij2 -macro 3D_count_IncludeEdges  "{}" \; 
    find $PWD -path "*IncludeEdges.nii.gz" -exec sh -c '{
      echo "  /usr/local/miracl/depends/Fiji.app/ImageJ-linux64 --ij2 -macro 3D_count_IncludeEdges $1"
      /usr/local/miracl/depends/Fiji.app/ImageJ-linux64 --ij2 -macro 3D_count_IncludeEdges "$1" > /dev/null 2>&1
      gpu_memory_error=$(grep error ${1}_I.csv)
      if [ ! -z "$gpu_memory_error" ]; then
        echo ERROR: $gpu_memory_error
      else
        cell_count=$((( $(cat ${1}_I.csv | wc -l) - 1 )))
        echo "  Cell Count: $cell_count"
      fi 
    }' sh {} \;

    # Find e27 and i25 slice substack counting errors, split substacks with errors, rerun 3D count 
    for f in *.nii.gz_*.csv; do
      case $f in 
        *_IncludeEdges.nii.gz_I.csv)
          error=$(awk 'FNR == 3 {print}' $f)
          if [[ $error == *"error"* ]]; then
            echo "ERROR" in $f
            NiiWithError=${f::-6}
            /usr/local/miracl/depends/Fiji.app/ImageJ-linux64 --ij2 -macro 25include_split $PWD/"$NiiWithError" > /dev/null 2>&1
            gzip -f -9 *.nii
            num_files_matching_nii_prefix=$(ls ${NiiWithError}* | wc -l)
            if (( $num_files_matching_nii_prefix == "5")) ; then
              rm $f
              rm "$NiiWithError"
            else
              echo "Unexpected number of files ($num_files_matching_nii_prefix) after splitting $NiiWithError.nii.gz into substacks. " 
              exit 1
            fi
            # find $PWD -path "*ExcludeSmall.nii.gz" -exec /usr/local/miracl/depends/Fiji.app/ImageJ-linux64 --ij2 -macro 3D_count_ExcludeEdges  "{}" \;
            find $PWD -path "*ExcludeSmall.nii.gz" -exec sh -c '{
              echo "  /usr/local/miracl/depends/Fiji.app/ImageJ-linux64 --ij2 -macro 3D_count_ExcludeEdges $1"
              /usr/local/miracl/depends/Fiji.app/ImageJ-linux64 --ij2 -macro 3D_count_ExcludeEdges "$1" > /dev/null 2>&1
              gpu_memory_error=$(grep error ${1}_E.csv)
              if [ ! -z "$gpu_memory_error" ]; then
                echo ERROR: $gpu_memory_error
              else
              cell_count=$((( $(cat ${1}_E.csv | wc -l) - 1 )))
              echo "  Cell Count: $cell_count"
              fi 
              echo " " 
            }' sh {} \;
            # find $PWD -path "*IncludeSmall.nii.gz" -exec /usr/local/miracl/depends/Fiji.app/ImageJ-linux64 --ij2 -macro 3D_count_IncludeEdges  "{}" \;
            find $PWD -path "*IncludeSmall.nii.gz" -exec sh -c '{
              echo "  /usr/local/miracl/depends/Fiji.app/ImageJ-linux64 --ij2 -macro 3D_count_IncludeEdges $1"
              /usr/local/miracl/depends/Fiji.app/ImageJ-linux64 --ij2 -macro 3D_count_IncludeEdges "$1" > /dev/null 2>&1
              gpu_memory_error=$(grep error ${1}_I.csv)
              if [ ! -z "$gpu_memory_error" ]; then
                echo ERROR: $gpu_memory_error
              else
              cell_count=$((( $(cat ${1}_I.csv | wc -l) - 1 )))
              echo "  Cell Count: $cell_count"
              fi 
              echo " " 
            }' sh {} \;
          fi
      ;;
        *_ExcludeEdges.nii.gz_E.csv)
          error=$(awk 'FNR == 3 {print}' $f)
          if [[ $error == *"error"* ]]; then
            echo "ERROR" in $f
            NiiWithError=${f::-6}
            /usr/local/miracl/depends/Fiji.app/ImageJ-linux64 --ij2 -macro 27exclude_split $PWD/"$NiiWithError" > /dev/null 2>&1
            gzip -f -9 *.nii
            num_files_matching_nii_prefix=$(ls ${NiiWithError}* | wc -l)
            if (( $num_files_matching_nii_prefix == "5")) ; then
              rm $f
              rm "$NiiWithError"
            else
              echo "Unexpected number of files ($num_files_matching_nii_prefix) after splitting $NiiWithError.nii.gz into substacks. " 
              exit 1
            fi
            # find $PWD -path "*ExcludeSmall.nii.gz" -exec /usr/local/miracl/depends/Fiji.app/ImageJ-linux64 --ij2 -macro 3D_count_ExcludeEdges  "{}" \;
            find $PWD -path "*ExcludeSmall.nii.gz" -exec sh -c '{
              echo "  /usr/local/miracl/depends/Fiji.app/ImageJ-linux64 --ij2 -macro 3D_count_ExcludeEdges $1"
              /usr/local/miracl/depends/Fiji.app/ImageJ-linux64 --ij2 -macro 3D_count_ExcludeEdges "$1" > /dev/null 2>&1
              gpu_memory_error=$(grep error ${1}_E.csv)
              if [ ! -z "$gpu_memory_error" ]; then
                echo ERROR: $gpu_memory_error
              else
              cell_count=$((( $(cat ${1}_E.csv | wc -l) - 1 )))
              echo "  Cell Count: $cell_count"
              fi 
              echo " " 
            }' sh {} \;
            # find $PWD -path "*IncludeSmall.nii.gz" -exec /usr/local/miracl/depends/Fiji.app/ImageJ-linux64 --ij2 -macro 3D_count_IncludeEdges  "{}" \;
            find $PWD -path "*IncludeSmall.nii.gz" -exec sh -c '{
              echo "  /usr/local/miracl/depends/Fiji.app/ImageJ-linux64 --ij2 -macro 3D_count_ExcludeEdges $1"
              /usr/local/miracl/depends/Fiji.app/ImageJ-linux64 --ij2 -macro 3D_count_IncludeEdges "$1" > /dev/null 2>&1
              gpu_memory_error=$(grep error ${1}_I.csv)
              if [ ! -z "$gpu_memory_error" ]; then
                echo ERROR: $gpu_memory_error
              else
              cell_count=$((( $(cat ${1}_I.csv | wc -l) - 1 )))
              echo "  Cell Count: $cell_count"
              fi 
              echo " " 
            }' sh {} \;
          fi
        ;;
      esac
    done

    # Concatenate csvs
    cat *csv > all.csv
    find "all.csv" | xargs cut -d, -f16,37,39,40,42,43,45 > ABAseg_stacks_25slices.csv #extracts columns from all.csv 
    rm all.csv

    # Copy CSV output to sample folder and rename
    cp ABAseg_stacks_25slices.csv "$SampleDir"/$output

    cd ../..

    echo "  Made region specific 3D count: $output" ; echo End: $(date) ; echo " " 

  fi 

  cd ..
done 

#Daniel Ryskamp Rijsketic 09/23/22, 04/26/23, & 09/20-27/23 (Heifets lab)
