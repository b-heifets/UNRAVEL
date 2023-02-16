#!/bin/bash
# (c) Daniel Ryskamp Rijsketic, Boris Heifets @ Stanford University, 2021-2023

if [ $# == 0 ] || [ "$1" == "help" ]; then
  echo '
ochann_to_gubra.sh <three letter orientation code> <x/y voxel size in microns or m for metadata> <z voxel size or m> [leave blank to process all samples or enter sample?? separated by spaces]

Warps ./sample??/niftis/sample??_02x_down_ochann_chan.nii.gz to Gubra atlas space

3 letter orientation codes (A/P=Anterior/Posterior, L/R=Left/Right, S/I=Superior/Interior) 
   Zeiss LS7: ALS in agarose (imaged w/ dorsal toward door & front up; in z-stacks A is up, L is left, S is at stack start) 
   Zeiss LS7: PLS if glued (imaged w/ dorsal toward door & front down; in z-stacks P is up, L is left, S is at stack start)
   UltraII: AIL=LH (imaged w/ medial side down & front facing back; in z-stacks A is up, I is left, L is at stack start) 
   UltraII: ASR=RH (imaged w/ medial side down & front facing back; in z-stacks A is up, S is left, R is at stack start) 

If using for voxel-wise stats (glm.sh), afterwards move outputs to folder and run fsleyes.sh to check alignment of samples
If alignment not correct, use mirror.sh to flip (or flip.sh and shift.sh for custom adjustment)
'
  exit 1
fi

echo " " ; echo "Running ochann_to_gubra.sh $@" ; echo " " 

if [ $# -gt 3 ]; then 
  sample_array=($(echo "${@:4}" | sed "s/['\"]//g"))
  sample_array=($(for i in ${sample_array[@]}; do echo $(basename $i) ; done)) 
else 
  sample_array=(sample??) 
fi

for sample in ${sample_array[@]}; do
  cd $sample

  #Warp ochann to atlas space
  if [ ! -f "$sample"_ochann_gubra_space.nii.gz ] ; then
    echo " " ; echo "  Warping "$sample"_02x_down_ochann_chan.nii.gz to Gubra space" ; echo " "

    #orientation can also be determined with /usr/local/miracl/miracl/conv/miracl_conv_set_orient_gui.py
    mkdir -p parameters
    echo "  Creating ort2std.txt with $1"
    echo "tifdir=$PWD/488" > parameters/ort2std.txt 
    echo "ortcode=$1" >> parameters/ort2std.txt

    #delete intermediate files in clar_allen_reg in case something was not correct w/ previous run 
    cd clar_allen_reg
    rm -f vox_seg_ochann_res.nii.gz vox_seg_ochann_swp.nii.gz reo_"$sample"_02x_down_ochann_chan_ort.nii.gz reo_"$sample"_02x_down_ochann_chan_ort_cp_org.nii.gz clar_allen_comb_def.nii.gz clar_res_org_seg.nii.gz
    cd ../ 

    #x and y dimensions need an even number of pixels for tif to nii.gz conversion
    if [ "$2" == "m" ]; then 
      metadata.sh
      xy_res=$(grep "Voxel size: " parameters/metadata | cut -d" " -f3 | cut -dx -f1)
      z_res=$(grep "Voxel size: " parameters/metadata | cut -d" " -f3 | cut -dx -f3)
    else
      xy_res=$2
      z_res=$3
    fi 

    #Make empty volume for copying header
    cd ochann
    downsample_ratio=2
    if (( $(echo "$xy_res <= $z_res" | bc -l) )); then 
      dz=$downsample_ratio
    else #make downsampled z res ~ similar to that for xy as in the savenii function in miracl_conv_convertTIFFtoNII.py
      dz=$(echo "$(echo "scale=5 ; $downsample_ratio*($xy_res/$z_res)" | bc )/1" | bc) #dividing by 1 -> rounds down
    fi
    z_res_out_float=$(echo "scale=7 ; ($z_res * $dz)/1000" | bc -l | sed 's/^\./0./') #convert um to mm
    #https://stackoverflow.com/questions/26861118/rounding-numbers-with-bc-in-bash
    round() {
      # $1 is expression to round (should be a valid bc expression)
      # $2 is number of decimal figures (optional). Defaults to three if none given
      local df=${2:-3}
      printf '%.*f\n' "$df" "$(bc -l <<< "a=$1; if(a>0) a+=5/10^($df+1) else if (a<0) a-=5/10^($df+1); scale=$df; a/1")"
    }
    z_res_out=$(round $z_res_out_float 6)
    z_size=$(ls *.tif | wc -l)
    z_size_out=$(echo "scale=6 ; (($z_size/$dz)+0.5)/1" | bc -l) #https://stackoverflow.com/questions/2395284/round-a-divided-number-in-bash
    FirstFile=$(ls | head -1)
    y_size=$(identify -format "%h\n" "$FirstFile" 2> /dev/null) #to use identify, first: sudo apt-get install imagemagick
    y_size_out=$(( $y_size / $downsample_ratio ))
    x_size=$(identify -format "%w\n" "$FirstFile" 2> /dev/null) 
    x_size_out=$(( $x_size / $downsample_ratio ))
    xy_res_out=$(echo "scale=6 ; ($xy_res * $downsample_ratio)/1000" | bc -l | sed 's/^\./0./') 
    cd ..
    fslcreatehd $z_size_out $y_size_out $x_size_out 1 $z_res_out $xy_res_out $xy_res_out 1 0 0 0 4 empty

    #Reorient "$sample"_ochann_gubra_space.nii.gz
    if [ ! -f "$sample"_ochann_gubra_space.nii.gz ] ; then
      echo "  Reorienting "$sample"_ochann_gubra_space.nii.gz"
      fslswapdim niftis/"$sample"_02x_down_ochann_chan.nii.gz z x y niftis/reo_"$sample"_02x_down_ochann_chan.nii.gz
      fslcpgeom empty.nii.gz niftis/reo_"$sample"_02x_down_ochann_chan.nii.gz 
    fi

    echo "  Warping niftis/reo_"$sample"_02x_down_ochann_chan.nii.gz to atlas space"
    miracl_reg_warp_clar_data_to_gubra.sh -r clar_allen_reg -i niftis/reo_"$sample"_02x_down_ochann_chan.nii.gz -o parameters/ort2std.txt -s ochann

    mv reg_final/reo_"$sample"_02x_down_ochann_chan_ochann_channel_allen_space.nii.gz "$sample"_ochann_gubra_space.nii.gz

    rm -f niftis/reo_"$sample"_02x_down_ochann_chan.nii.gz empty.nii.gz
  else 
    echo " " ; echo "  "$sample"_ochann_gubra_space.nii.gz exists, skipping" ; echo " "
  fi

  cd ..
done 

# Daniel Ryskamp Rijsketic 12/7/21 & 07/07/22 (Heifets lab)
