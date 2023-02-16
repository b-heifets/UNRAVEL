#!/bin/bash
# (c) Daniel Ryskamp Rijsketic, Boris Heifets @ Stanford University, 2022-2023

if [ $# == 0 ] || [ "$1" == "help" ]; then
  echo '
Run from sample folder
ABA_histo_2xDS_tif.sh <xy voxel size (um) or m (metadata)> <z voxel size or m>

Inputs:
reg_final/gubra_ano_split_10um_clar_vox.nii.gz

Outputs: 
sample??/reg_final/"$sample"_2xDS_native_gubra_ano_split.tif

Outputs: 
sample??/sample??_ABA_histogram_total.csv

'
  exit 1
fi

#Inputs for ABAseg
SampleDir="$PWD"
sample="$(basename $SampleDir)"
SampleFolder="$(basename $SampleDir)" ### remove variable redundancy later
SegDir="$PWD"/consensus
Seg="$SegDir"/"$sample"_consensus.nii.gz
ABA="$PWD"/reg_final/gubra_ano_split_10um_clar_downsample_16-bit.nii.gz
image=gubra_ano_split_10um_clar_downsample_16-bit.nii.gz
output_dir=$PWD/reg_final


########################################
####### Atlas to 2xDS res native #######
########################################
if [ ! -f "$sample"_ABA_histogram_total.csv ] ; then 

  echo " " ; echo "Getting region volumes for "$sample""  ; echo Start: $(date) ; echo " " 

  cd reg_final
  #Extracting intensity count column
  mkdir ABA_histogram_of_pixel_intensity_counts

  #Scale native atlas to 2xDS res
  if (( $(ls 488 | wc -l) < 1 )); then echo " " ; echo "./488/tifs MISSING" ; echo " " ; exit 1 ; fi  

  folder_w_warped_image=reg_final #warped atlas (10um res w/ padding)
  fslmaths $folder_w_warped_image/gubra_ano_split_10um_clar_downsample.nii.gz $folder_w_warped_image/$image -odt short

  #################   Calulate cropping  #################

  # Native image size:
  cd 488 ; shopt -s nullglob ; for f in *\ *; do mv "$f" "${f// /_}"; done ; shopt -u nullglob ; cd .. #replace spaces with _ in tif series if needed
  tif=$(ls -1q $PWD/488/*.tif | head -1) #change to other 2xDS res input if needed
  tif_x_dim=$(identify -quiet $tif | cut -f 3 -d " " | cut -dx -f1)
  tif_y_dim=$(identify -quiet $tif | cut -f 3 -d " " | cut -dx -f2)
  tif_z_dim=$(ls -1q $PWD/488/*.tif | wc -l) 

  # 2x downsample dim:
  tif_x_dim_2xDS=$(echo "scale=1;$tif_x_dim/2" | bc -l) #scale=1 means 1 # after the decimal and | bc -l enables floats
  tif_y_dim_2xDS=$(echo "scale=1;$tif_y_dim/2" | bc -l)
  tif_z_dim_2xDS=$(echo "scale=1;$tif_z_dim/2" | bc -l)

  # $folder_w_warped_image/$image has a different orientation than the native tissue
  #y for warped atlas is x for 2xDS 
  #x for warped atlas is y for 2xDS 
  #z for warped atlas is z for 2xDS

  # Calculate dim of output (2xDS native res):
  DS_atlas_x=$(echo "($tif_y_dim_2xDS+0.5)/1" | bc) #rounds
  DS_atlas_y=$(echo "($tif_x_dim_2xDS+0.5)/1" | bc) #rounds
  DS_atlas_z=$(echo "($tif_z_dim_2xDS+0.5)/1" | bc) #rounds

  # Get dim of warped image (10um res w/ padding)
  if [ $(fslinfo $folder_w_warped_image/$image | sed -n '1 p' | awk '{print $1;}') == "filename" ] ; then  #If filename in header, then
    xdim=$(fslinfo $folder_w_warped_image/$image | sed -n '3 p' | awk '{print $2;}') #fslinfo | 3rd line | 2nd word 
    ydim=$(fslinfo $folder_w_warped_image/$image | sed -n '4 p' | awk '{print $2;}')
    zdim=$(fslinfo $folder_w_warped_image/$image | sed -n '5 p' | awk '{print $2;}')
  else
    xdim=$(fslinfo $folder_w_warped_image/$image | sed -n '2 p' | awk '{print $2;}') 
    ydim=$(fslinfo $folder_w_warped_image/$image | sed -n '3 p' | awk '{print $2;}')
    zdim=$(fslinfo $folder_w_warped_image/$image | sed -n '4 p' | awk '{print $2;}')
  fi
  
  # Determine xyz voxel size in microns
  if [ "$2" == "m" ]; then 
    metadata.sh
    xy_res=$(grep "Voxel size: " parameters/metadata | cut -d" " -f3 | cut -dx -f1)
    z_res=$(grep "Voxel size: " parameters/metadata | cut -d" " -f3 | cut -dx -f3)
  else
    xy_res=$1
    z_res=$2
  fi 

  # Parameters for resampling $image from 10 um res to 2x downsampled (2xDS) native res: 
  # (10um/2xDS_native_xyres_in_um)*xy_dim and (10um/2xDS_native_zres_in_um)*z_dim
  xy_voxel_size=$(echo "scale=5; ($xy_res)/1000" | bc | sed 's/^\./0./') #3.53 for Zeiss
  z_voxel_size=$(echo "scale=5; ($z_res)/1000" | bc | sed 's/^\./0./') #3.5 for Zeiss
  xy_voxel_size_2xDS=$(echo "scale=5; ($xy_res*2)/1000" | bc | sed 's/^\./0./') #sed adds a 0 before the . if the result<1
  z_voxel_size_2xDS=$(echo "scale=5; ($z_res*2)/1000" | bc | sed 's/^\./0./')

  x_dim_10um_float=$(echo "(0.01/$xy_voxel_size_2xDS)*$xdim" | bc -l) #0.01 mm = 10 um
  y_dim_10um_float=$(echo "(0.01/$xy_voxel_size_2xDS)*$ydim" | bc -l)
  z_dim_10um_float=$(echo "(0.01/$z_voxel_size_2xDS)*$zdim" | bc -l)

  x_dim_10um=$(echo "($x_dim_10um_float+0.5)/1" | bc) #rounds
  y_dim_10um=$(echo "($y_dim_10um_float+0.5)/1" | bc)
  z_dim_10um=$(echo "($z_dim_10um_float+0.5)/1" | bc)
 
  # Determine xyzmin for cropping with fslroi 
  xmin=$((($x_dim_10um-$DS_atlas_x)/2))
  ymin=$((($y_dim_10um-$DS_atlas_y)/2))
  zmin=$((($z_dim_10um-$DS_atlas_z)/2))
  zmax=$(echo "($DS_atlas_z+$zmin-1)" | bc )

  echo " " ; echo "  Scale to 2xDS native, crop padding, reorient $image.nii.gz for $sample" ; echo " " 
  /usr/local/miracl/depends/Fiji.app/ImageJ-linux64 --ij2 -macro to_native_2xDS_tif $PWD/$folder_w_warped_image/$image#$x_dim_10um#$y_dim_10um#$z_dim_10um#$xmin#$DS_atlas_x#$ymin#$DS_atlas_y#$zmin#$zmax#$tif_x_dim#$tif_y_dim#$tif_z_dim

  rm -f $folder_w_warped_image/$image 


#Sum histograms of all slices
cd ABA_histogram_of_pixel_intensity_counts

#Sum ABA histograms of all slices
#Extract 4th column containing counts for each pixel intensity (rows 0 - 65534 = corresponding intensity for 16-bit images)
find -name "ABA_histogram.csv" -type f -print0 | xargs  cut -d, -f4 > temp.csv 

#remove CSV header
sed -i '1d' temp.csv

#split CSV into multiple CSVs (1 per slice)
split -l 65535 -d -a 4 --additional-suffix=.csv temp.csv ABA_histogram_slice_ 

#concatenate csv columns into one CSV
rm ABA_histogram.csv ; paste *.csv  | awk '{ print $0; }' > ABA_histogram_stack.csv

#sum columns into one CSV
perl -anle '$x+=$_ for(@F);print $x;$x=0;' ABA_histogram_stack.csv >  ABA_histogram_total.csv

rm ABA_histogram_slice_*.csv
rm ABA_histogram_stack.csv # comment out to have csv with pixel intensity counts for each slice

#To run in terminal after running FIJI macro, cd to folder with CSV and run:
#find -name "ABA_histogram.csv" -type f -print0 | xargs  cut -d, -f4 > temp.csv ; sed -i '1d' temp.csv ; split -l 65535 -d -a 4 --additional-suffix=.csv temp.csv ABA_histogram_slice_ ; rm temp.csv ; rm ABA_histogram.csv ; paste *.csv  | awk '{ print $0; }' > ABA_histogram_stack.csv ; perl -anle '$x+=$_ for(@F);print $x;$x=0;' ABA_histogram_stack.csv >  ABA_histogram_total.csv ; rm ABA_histogram_slice_*.csv


###Rename ABA_histogram_total.csv in /ABA_histogram_of_pixel_intensity_counts and copy to sample folder
StacksDir="$PWD"
mv ABA_histogram_total.csv ../
cd ../
ParentFolder=${PWD##*/}
for f in ABA_histogram_total.csv ;  do mv "$f" "$(basename "$(pwd)")"_"$f" ;  done #Append parent folder name (e.g., reg_final)
mv "$ParentFolder"_ABA_histogram_total.csv ../
cd ../
GrantParentDir=$(pwd)
GrandParentFolder=${PWD##*/}
for f in "$ParentFolder"_ABA_histogram_total.csv ;  do mv "$f" "$(basename "$(pwd)")"_"$f" ;  done #Append grandparent folder name (e.g., KNK_sample2_)
Filename="$GrandParentFolder"_"$ParentFolder"_ABA_histogram_total.csv
Filename2=$(printf '%s\n' "${Filename/reg_final_}") #trim "reg_final_" from filename
#Filename3=$(printf '%s\n' "${Filename2/ample}") #trim "ample" from filename)
mv "$Filename" "$Filename2"
Source=""$GrantParentDir"/"$Filename2""
cp "$Source" "$StacksDir"
  
  echo End: $(date) ; echo " " 
else 
  echo " " ; echo "Region volumes exist for "$sample", skipping" ; echo " " 
fi


#Daniel Ryskamp Rijsketic 09/30/2022 (Heifets lab)

