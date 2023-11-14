#!/bin/bash

if [[ $# == 0 || "$1" == "-h" || "$1" == "--help" || "$1" == "help" ]] ; then
  echo '
For rolling ball background subtraction run from experiment folder:
rb3.sh <orient code> <rb radius> <x/y res or m> <z res or m> <IF folder name> <ds factor> [sample?? list]

Detailed command info: 
rb3.sh <orientation code> <int: rolling ball radius in pixels> <x/y voxel size in microns or m for metadata> <z voxel size or m> <input folder name> <downsample factor used w/ prep_reg.sh> [leave blank to process all samples or enter sample?? separated by spaces]

Input: ./sample??/"$5"/tifs 
Output: ./sample??/sample??_"$5"_rb$2_gubra_space.nii.gz

For help on ortientation code, run: reg3.sh -h
The rolling ball radius should be at least equal to the radius of the largest object of interest. Larger values ok too.
If using for voxel-wise stats (glm.sh), consider z-scoring outputs, move them to folder and run fsleyes.sh to confirm alignment
Use mirror.sh to flip samples
'
  exit 1
fi

echo " " ; echo "Running rb3.sh $@ from $PWD" ; echo " " 

if [ $# -gt 6 ]; then 
  sample_array=($(echo "${@:7}" | sed "s/['\"]//g"))
  sample_array=($(for i in ${sample_array[@]}; do echo $(basename $i) ; done)) 
else 
  sample_array=(sample??) 
fi

for sample in ${sample_array[@]}; do
  cd $sample

  cd "$5" ; shopt -s nullglob ; for f in *\ *; do mv "$f" "${f// /_}"; done ; shopt -u nullglob ; cd .. #replace spaces w/ _ in tif series file names

  # Rolling ball subtraction 
  num_of_tifs="0" ; if [ -d "$5" ]; then num_of_tifs=$(ls "$5" | wc -l) ; fi
  num_of_rb_tifs="0" ; if [ -d "$5"_rb$2 ]; then num_of_rb_tifs=$(ls "$5"_rb$2 | wc -l) ; fi
  if (( $num_of_rb_tifs > 1 )) && (( $num_of_tifs == $num_of_rb_tifs )); then
    echo "  Rolling ball subtraction already run for "$sample", skipping" ; echo " " 
  else
    echo " " ; echo "  Rolling ball subtracting w/ pixel radius of $2 for $sample" ; echo " " 
    mkdir -p "$5"_rb$2
    cd "$5"
    first_tif=$(ls *.tif | head -1)
    /usr/local/miracl/depends/Fiji.app/ImageJ-linux64 --ij2 -macro rolling_ball_bkg_subtraction_abc $PWD/$first_tif#$2#$5 > /dev/null 2>&1
    cd ..
  fi

  # Load tifs, downsample, reorient image, and save as .nii.gz
  if [ "$3" == "m" ]; then 
    metadata.sh
    xy_res=$(grep "Voxel size: " parameters/metadata | cut -d" " -f3 | cut -dx -f1)
    z_res=$(grep "Voxel size: " parameters/metadata | cut -d" " -f3 | cut -dx -f3)
  else
    xy_res=$3
    z_res=$4
  fi 
  if (( $6 > 9 )); then x_down=${6}x_down ; else x_down=0${6}x_down ; fi
  ds_nifti=$PWD/niftis/"$sample"_${x_down}_"$5"_rb$2_chan.nii.gz
  if [ ! -f $ds_nifti ] ; then
    echo "  Converting "$5"_rb$2 tifs to .nii.gz, downsampling, and reorienting for $sample"
    miracl_conv_convertTIFFtoNII_simplified.py -f "$5"_rb$2 -d $6 -o "$sample"_${x_down}_"$5"_rb$2_chan -vx $xy_res -vz $z_res
  else
    echo "  $ds_nifti exists, skipping "
  fi

  # Warp "$5"_rbX to atlas space
  if [ ! -f "$sample"_"$5"_rb$2_gubra_space.nii.gz ] ; then
    echo " " ; echo "  Warping $ds_nifti to Gubra space" ; echo " "

    # Orientation can also be determined with /usr/local/miracl/miracl/conv/miracl_conv_set_orient_gui.py
    mkdir -p parameters
    echo "  Creating ort2std.txt with $1"
    echo "tifdir=$PWD/488" > parameters/ort2std.txt 
    echo "ortcode=$1" >> parameters/ort2std.txt

    # Delete intermediate files in clar_allen_reg in case something was not correct w/ previous run 
    cd clar_allen_reg
    rm -f vox_seg_"$5"_res.nii.gz vox_seg_"$5"_swp.nii.gz reo_"$sample"_0${6}x_down_"$5"_rb$2_chan_ort.nii.gz reo_"$sample"_0${6}x_down_"$5"_rb$2_chan_ort_cp_org.nii.gz clar_allen_comb_def.nii.gz clar_res_org_seg.nii.gz
    cd ../ 

    # Make empty volume for copying header
    x_size=$(fslinfo $ds_nifti | head  -2 | tail -1 | cut -f3)
    y_size=$(fslinfo $ds_nifti | head  -3 | tail -1 | cut -f3)
    z_size=$(fslinfo $ds_nifti | head  -4 | tail -1 | cut -f3)
    xy_res=$(fslinfo $ds_nifti | head  -7 | tail -1 | cut -f3)
    z_res=$(fslinfo $ds_nifti | head  -9 | tail -1 | cut -f3)
    fslcreatehd $z_size $x_size $y_size 1 $z_res $xy_res $xy_res 1 0 0 0 4 empty

    # Reorient "$sample"_"$5"_rb$2_gubra_space.nii.gz
    reo_ds_nii=$PWD/niftis/reo_"$sample"_${x_down}_"$5"_rb$2_chan.nii.gz
    if [ ! -f $reo_ds_nii ]; then
      echo " " ; echo "  Reorienting $reo_ds_nii"
        fslswapdim $ds_nifti z x y $reo_ds_nii
        fslcpgeom empty.nii.gz $reo_ds_nii
    fi

    echo "  Warping $reo_ds_nii to atlas space"
    miracl_reg_warp_clar_data_to_gubra.sh -r clar_allen_reg -i $reo_ds_nii -o parameters/ort2std.txt -s "$5"

    mv reg_final/reo_"$sample"_${x_down}_"$5"_rb$2_chan_"$5"_channel_allen_space.nii.gz "$sample"_"$5"_rb$2_gubra_space.nii.gz

    rm -f $reo_ds_nii empty.nii.gz
  else 
    echo " " ; echo "  "$sample"_"$5"_rb$2_gubra_space.nii.gz exists, skipping" ; echo " "
  fi

  cd ..
done 

# Daniel Ryskamp Rijsketic 12/7/21, 07/07/22, & 08/25/23 (Heifets lab)
# Austen Casey adapted to run with any directory name 7/1/23
