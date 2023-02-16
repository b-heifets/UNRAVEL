#!/bin/bash
# (c) Daniel Ryskamp Rijsketic, Boris Heifets @ Stanford University, 2022-2023

if [ "$1" == "help" ]; then
  echo '
Run from sample folder
ABA_histo_in_tissue_2xDS.sh <Threshold for tissue mask> [leave blank to process all samples or enter sample?? separated by spaces]

Inputs: 
sample??/reg_final/clar_downsample_res10um.nii.gz 
sample??/reg_final/"$sample"_2xDS_native_gubra_ano_split.nii.gz (from ABA_to_native_2xDS.sh)


Outputs: 
sample??/sample??_ABA_histogram_in_tissue.csv
'
  exit 1
fi

echo " " ; echo "Running ABA_histo_in_tissue_2xDS.sh at $PWD $@" ; echo " " 

if [ $# -gt 1 ]; then 
  sample_array=($(echo "${@:2}" | sed "s/['\"]//g"))
  sample_array=($(for i in ${sample_array[@]}; do echo $(basename $i) ; done)) 
else 
  sample_array=(sample??) 
fi

for sample in ${sample_array[@]}; do
  cd $sample

  first_488_tif=$(ls 488 | head -1)
  SampleDir="$PWD"
  SampleFolder="$(basename $SampleDir)"

  if [ ! -f "$sample"_ABA_histogram_in_tissue.csv ] ; then 
    echo "Getting region volumes in tissue for "$sample"" ; echo Start: $(date)

    /usr/local/miracl/depends/Fiji.app/ImageJ-linux64 --ij2 -macro 2xDS_488_tif $PWD/488/$first_488_tif
    mv $PWD/488/2xDS_488.tif $PWD/reg_final/2xDS_488.tif


#Inputs
cd reg_final
mkdir ABA_histogram_of_pixel_intensity_counts_in_tissue
ABA488="$PWD"/*ABA_488_downsample.tif #rename without EXP_sampleX if needed 
ABAtissue="$PWD"/ABA_in_tissue.tif
echo $ABA488
echo "$ABAtissue"

#Extracting intensity count column
/usr/local/miracl/depends/Fiji.app/ImageJ-linux64 --ij2 -macro ABA_within_tissue_2xDS_tif $PWD/reg_final/"$sample"_2xDS_native_gubra_ano_split.tif#$PWD/reg_final/2xDS_488.tif#$1

#Sum ABA histograms of all slices
#Extract 4th column containing counts for each pixel intensity (rows 0 - 65534 = corresponding intensity for 16-bit images)
cd ABA_histogram_of_pixel_intensity_counts_in_tissue
find -name "ABA_histogram_in_tissue.csv" -type f -print0 | xargs  cut -d, -f4 > temp.csv 

#remove CSV header
sed -i '1d' temp.csv

#split CSV into multiple CSVs (1 per slice)
split -l 65535 -d -a 4 --additional-suffix=.csv temp.csv ABA_histogram_in_tissue_slice_ 
rm temp.csv 

#concatenate csv columns into one CSV
rm ABA_histogram_in_tissue.csv ; paste *.csv  | awk '{ print $0; }' > ABA_histogram_in_tissue_stack.csv

#sum columns into one CSV
perl -anle '$x+=$_ for(@F);print $x;$x=0;' ABA_histogram_in_tissue_stack.csv >  ABA_histogram_in_tissue_total.csv

rm ABA_histogram_in_tissue_slice_*.csv
rm ABA_histogram_in_tissue_stack.csv # comment out to have csv with pixel intensity counts for each slice

#To run in terminal after running FIJI macro, cd to folder with CSV and run:
#find -name "ABA_histogram_in_tissue.csv" -type f -print0 | xargs  cut -d, -f4 > temp.csv ; sed -i '1d' temp.csv ; split -l 65535 -d -a 4 --additional-suffix=.csv temp.csv ABA_histogram_in_tissue_slice_ ; rm temp.csv ; rm ABA_histogram_in_tissue.csv ; paste *.csv  | awk '{ print $0; }' > ABA_histogram_in_tissue_stack.csv ; perl -anle '$x+=$_ for(@F);print $x;$x=0;' ABA_histogram_in_tissue_stack.csv >  ABA_histogram_in_tissue_total.csv ; rm ABA_histogram_in_tissue_slice_*.csv


###Rename ABA_histogram_in_tissue_total.csv in /ABA_histogram_of_pixel_intensity_counts_in_tissue and copy to sample folder
StacksDir="$PWD"
mv ABA_histogram_in_tissue_total.csv ../
cd ../
ParentFolder=${PWD##*/}
for f in ABA_histogram_in_tissue_total.csv ;  do mv "$f" "$(basename "$(pwd)")"_"$f" ;  done #Append parent folder name (e.g., reg_final)
mv "$ParentFolder"_ABA_histogram_in_tissue_total.csv ../
cd ../
GrantParentDir=$(pwd)
GrandParentFolder=${PWD##*/}
for f in "$ParentFolder"_ABA_histogram_in_tissue_total.csv ;  do mv "$f" "$(basename "$(pwd)")"_"$f" ;  done #Append grandparent folder name (e.g., KNK_sample2_)
Filename="$GrandParentFolder"_"$ParentFolder"_ABA_histogram_in_tissue_total.csv
Filename2=$(printf '%s\n' "${Filename/reg_final_}") #trim "reg_final_" from filename
#Filename3=$(printf '%s\n' "${Filename2/ample}") #trim "ample" from filename)
mv "$Filename" "$Filename2"
Source=""$GrantParentDir"/"$Filename2""
cp "$Source" "$StacksDir"

    echo End: $(date) ; echo " "
  else 
    echo "Region volumes in tissue exist for "$sample", skipping"
  fi

  cd ..
done 

#Daniel Ryskamp Rijsketic 09/30/2022 (Heifets lab)

