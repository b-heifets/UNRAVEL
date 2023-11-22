#!/bin/bash

if [[ $# == 0 || "$1" == "-h" || "$1" == "--help" || "$1" == "help" ]] ; then
  echo "
For rolling ball background subtraction run from experiment folder:
rb.sh <orient code> <rb radius> <x/y res or m> <z res or m> <'IF folder name(s)'> [sample?? list]

Detailed command info: 
rb.sh <orientation code> <int: rolling ball radius in pixels> <x/y voxel size in microns or m for metadata> <z voxel size or m> <input folder name(s) in list w/ quotes> [leave blank to process all samples or enter sample?? separated by spaces]

Input: ./sample??/"$5"/tifs 
Output: ./sample??/sample??_"$5"_rb$2_gubra_space.nii.gz

For help on ortientation code, run: reg3.sh -h
The rolling ball radius should be at least equal to the radius of the largest object of interest. Larger values ok too.
If using for voxel-wise stats (glm.sh), consider z-scoring outputs, move them to folder and run fsleyes.sh to confirm alignment
Use mirror.sh to flip samples
"
  exit 1
fi

echo " " ; echo "Running rb.sh $@ from $PWD" ; echo " " 

if [ $# -gt 5 ]; then 
  sample_array=($(echo "${@:6}" | sed "s/['\"]//g"))
  sample_array=($(for i in ${sample_array[@]}; do echo $(basename $i) ; done)) 
else 
  sample_array=(sample??) 
fi

immunofluor=($(echo "$5" | sed "s/['\"]//g"))

for sample in ${sample_array[@]}; do
  cd $sample

  for ochann in ${immunofluor[@]}; do
  cd "$ochann" ; shopt -s nullglob ; for f in *\ *; do mv "$f" "${f// /_}"; done ; shopt -u nullglob ; cd .. #replace spaces w/ _ in tif series file names

  # Rolling ball subtraction 
  num_of_tifs="0" ; if [ -d "$ochann" ]; then num_of_tifs=$(ls "$ochann" | wc -l) ; fi
  num_of_rb_tifs="0" ; if [ -d "$ochann"_rb$2 ]; then num_of_rb_tifs=$(ls "$ochann"_rb$2 | wc -l) ; fi

  if (( $num_of_rb_tifs > 1 )) && (( $num_of_tifs == $num_of_rb_tifs )); then
    echo "  Rolling ball subtraction already run for "$sample", skipping" ; echo " " 
  else
    echo " " ; echo "  Rolling ball subtracting w/ pixel radius of $2 for $sample" ; echo " " 
    mkdir -p "$ochann"_rb$2
    cd "$ochann"
    first_tif=$(ls *.tif | head -1)
    /usr/local/miracl/depends/Fiji.app/ImageJ-linux64 --ij2 -macro rolling_ball_bkg_subtraction_abc $PWD/$first_tif#$2#$ochann
    cd ..
  fi

  # x and y dimensions need an even number of pixels for tif to nii.gz conversion
  if [ "$3" == "m" ]; then 
    metadata.sh
    xy_res=$(grep "Voxel size: " parameters/metadata | cut -d" " -f3 | cut -dx -f1)
    z_res=$(grep "Voxel size: " parameters/metadata | cut -d" " -f3 | cut -dx -f3)
  else
    xy_res=$3
    z_res=$4
  fi 

  # Tif to nii.gz conversion
  ds_nifti=$PWD/niftis/"$sample"_02x_down_"$ochann"_rb$2_chan.nii.gz
  if [ ! -f $ds_nifti ] ; then
    echo "  Converting "$ochann"_rb$2 tifs to nii.gz for $sample"
    miracl_conv_convertTIFFtoNII.py -f "$ochann"_rb$2 -o "$sample" -d 2 -ch "$ochann"_rb$2 -vx $xy_res -vz $z_res
  else 
    echo "  $ds_nifti exists, skipping "
  fi

  # Warp "$ochann"_rbX to atlas space
  if [ ! -f "$sample"_"$ochann"_rb$2_gubra_space.nii.gz ] ; then
    echo " " ; echo "  Warping $ds_nifti to Gubra space" ; echo " "

    # Orientation can also be determined with /usr/local/miracl/miracl/conv/miracl_conv_set_orient_gui.py
    mkdir -p parameters
    echo "  Creating ort2std.txt with $1"
    echo "tifdir=$PWD/488" > parameters/ort2std.txt 
    echo "ortcode=$1" >> parameters/ort2std.txt

    # Delete intermediate files in clar_allen_reg in case something was not correct w/ previous run 
    cd clar_allen_reg
    rm -f vox_seg_"$ochann"_res.nii.gz vox_seg_"$ochann"_swp.nii.gz reo_"$sample"_02x_down_"$ochann"_rb$2_chan_ort.nii.gz reo_"$sample"_02x_down_"$ochann"_rb$2_chan_ort_cp_org.nii.gz clar_allen_comb_def.nii.gz clar_res_org_seg.nii.gz
    cd ../ 

    # Make empty volume for copying header
    x_size=$(fslinfo $ds_nifti | head  -2 | tail -1 | cut -f3)
    y_size=$(fslinfo $ds_nifti | head  -3 | tail -1 | cut -f3)
    z_size=$(fslinfo $ds_nifti | head  -4 | tail -1 | cut -f3)
    xy_res=$(fslinfo $ds_nifti | head  -7 | tail -1 | cut -f3)
    z_res=$(fslinfo $ds_nifti | head  -9 | tail -1 | cut -f3)
    fslcreatehd $z_size $x_size $y_size 1 $z_res $xy_res $xy_res 1 0 0 0 4 empty

    # Reorient "$sample"_"$ochann"_rb$2_gubra_space.nii.gz
    reo_ds_nifti=$PWD/niftis/reo_"$sample"_02x_down_"$ochann"_rb$2_chan.nii.gz
    if [ ! -f $reo_ds_nifti ]; then
      echo " " ; echo "  Reorienting "$sample"_"$ochann"_rb$2_gubra_space.nii.gz"
        fslswapdim $ds_nifti z x y $reo_ds_nifti
        fslcpgeom empty.nii.gz $reo_ds_nifti 
    fi

    echo "  Warping $reo_ds_nifti to atlas space"
    miracl_reg_warp_clar_data_to_gubra.sh -r clar_allen_reg -i $reo_ds_nifti -o parameters/ort2std.txt -s "$ochann"

    mv reg_final/reo_"$sample"_02x_down_"$ochann"_rb$2_chan_"$ochann"_channel_allen_space.nii.gz "$sample"_"$ochann"_rb$2_gubra_space.nii.gz

   # rm -f $reo_ds_nifti empty.nii.gz
  else 
    echo " " ; echo "  "$sample"_"$ochann"_rb$2_gubra_space.nii.gz exists, skipping" ; echo " "
  fi
  done
  cd ..
done 

# Daniel Ryskamp Rijsketic 12/7/21, 07/07/22, & 09/01/23 (Heifets lab)
