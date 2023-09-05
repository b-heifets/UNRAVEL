#!/bin/bash

if [ $# == 0 ] || [ "$1" == "help" ]; then
  echo '
For rolling ball background subtraction run from experiment folder:
rb.sh <orient code> <rolling ball radius in pixels> <x/y voxel size in microns or m for metadata> <z voxel size or m> <folder name for "$5"> [leave blank to process all samples or enter sample?? separated by spaces]

Input: ./sample??/"$5"/tifs 
Output: ./sample??/sample??_"$5"_rb$2_gubra_space.nii.gz

Determining 3 letter orientation codes (A/P=Anterior/Posterior, L/R=Left/Right, S/I=Superior/Interior):
  Open z-stack virtually in FIJI -> 1st letter is side facing up, 2nd is side facing left, 3rd is side at stack start

The rolling ball radius should be at least equal to the radius of the largest object of interest. Larger values ok too.

If using for voxel-wise stats (glm.sh), afterwards z-score outputs, move them to folder and run fsleyes.sh to check alignment
If alignment not correct, use mirror.sh to flip (or flip.sh and shift.sh for custom adjustment)
'
  exit 1
fi

echo " " ; echo "Running rb.sh $@ from $PWD" ; echo " " 

if [ $# -gt 5 ]; then 
  sample_array=($(echo "${@:6}" | sed "s/['\"]//g"))
  sample_array=($(for i in ${sample_array[@]}; do echo $(basename $i) ; done)) 
else 
  sample_array=(sample??) 
fi

for sample in ${sample_array[@]}; do
  cd $sample

  cd "$5" ; shopt -s nullglob ; for f in *\ *; do mv "$f" "${f// /_}"; done ; shopt -u nullglob ; cd .. #replace spaces w/ _ in tif series file names

  #Rolling ball subtraction 
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

  #x and y dimensions need an even number of pixels for tif to nii.gz conversion
  if [ "$3" == "m" ]; then 
    metadata.sh
    xy_res=$(grep "Voxel size: " parameters/metadata | cut -d" " -f3 | cut -dx -f1)
    z_res=$(grep "Voxel size: " parameters/metadata | cut -d" " -f3 | cut -dx -f3)
  else
    xy_res=$3
    z_res=$4
  fi 

  ##Tif to nii.gz conversion
  if [ ! -f niftis/"$sample"_02x_down_"$5"_rb$2_chan.nii.gz ] ; then
    echo "  Converting "$5"_rb$2 tifs to nii.gz for $sample"
    miracl_conv_convertTIFFtoNII.py -f "$5"_rb$2 -o "$sample" -d 2 -ch "$5"_rb$2 -vx $xy_res -vz $z_res
  else 
    echo "  "$sample"_02x_down_"$5"_rb$2_chan.nii.gz exists, skipping "
  fi

  #Warp "$5"_rbX to atlas space
  if [ ! -f "$sample"_"$5"_rb$2_gubra_space.nii.gz ] ; then
    echo " " ; echo "  Warping "$sample"_02x_down_"$5"_rb$2_chan.nii.gz to Gubra space" ; echo " "

    #orientation can also be determined with /usr/local/miracl/miracl/conv/miracl_conv_set_orient_gui.py
    mkdir -p parameters
    echo "  Creating ort2std.txt with $1"
    echo "tifdir=$PWD/488" > parameters/ort2std.txt 
    echo "ortcode=$1" >> parameters/ort2std.txt

    #delete intermediate files in clar_allen_reg in case something was not correct w/ previous run 
    cd clar_allen_reg
    rm -f vox_seg_"$5"_res.nii.gz vox_seg_"$5"_swp.nii.gz reo_"$sample"_02x_down_"$5"_rb$2_chan_ort.nii.gz reo_"$sample"_02x_down_"$5"_rb$2_chan_ort_cp_org.nii.gz clar_allen_comb_def.nii.gz clar_res_org_seg.nii.gz
    cd ../ 

    #Make empty volume for copying header
    cd "$5"
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
    if [ $(($z_size%2)) -ne 0 ] ; then
	z_size_out=$(echo "scale=6 ; (($z_size/$dz)+0.5)/1" | bc -l) #https://stackoverflow.com/questions/2395284/round-a-divided-number-in-bash #rounds up
    else 
    	z_size_out=$(echo "scale=0; $z_size/$dz" | bc) #rounds down, trying for sample01
    fi
    FirstFile=$(ls | head -1)
    y_size=$(identify -format "%h\n" "$FirstFile" 2> /dev/null) #to use identify, first: sudo apt-get install imagemagick
    y_size_out=$(( $y_size / $downsample_ratio ))
    x_size=$(identify -format "%w\n" "$FirstFile" 2> /dev/null) 
    x_size_out=$(( $x_size / $downsample_ratio ))
    xy_res_out=$(echo "scale=6 ; ($xy_res * $downsample_ratio)/1000" | bc -l | sed 's/^\./0./') 
    cd ..


    ### DRR bug fix
    z_size_out=$(fslinfo niftis/"$sample"_02x_down_autofl_chan.nii.gz | head  -4 | tail -1 | cut -f3)


    fslcreatehd $z_size_out $y_size_out $x_size_out 1 $z_res_out $xy_res_out $xy_res_out 1 0 0 0 4 empty


    ### DRR bug fix
    if [ -f niftis/reo_"$sample"_02x_down_"$ochann"_rb$2_chan.nii.gz ]; then
      fslcpgeom empty.nii.gz niftis/reo_"$sample"_02x_down_"$ochann"_rb$2_chan.nii.gz
    fi


    #Reorient "$sample"_"$5"_rb$2_gubra_space.nii.gz
    if [ ! -f niftis/reo_"$sample"_02x_down_"$5"_rb$2_chan.nii.gz ]; then
      echo " " ; echo "  Reorienting "$sample"_"$5"_rb$2_gubra_space.nii.gz"
        fslswapdim niftis/"$sample"_02x_down_"$5"_rb$2_chan.nii.gz z x y niftis/reo_"$sample"_02x_down_"$5"_rb$2_chan.nii.gz
        fslcpgeom empty.nii.gz niftis/reo_"$sample"_02x_down_"$5"_rb$2_chan.nii.gz 
    fi

    echo "  Warping niftis/reo_"$sample"_02x_down_"$5"_rb$2_chan.nii.gz to atlas space"
      miracl_reg_warp_clar_data_to_gubra.sh -r clar_allen_reg -i niftis/reo_"$sample"_02x_down_"$5"_rb$2_chan.nii.gz -o parameters/ort2std.txt -s "$5"

      mv reg_final/reo_"$sample"_02x_down_"$5"_rb$2_chan_"$5"_channel_allen_space.nii.gz "$sample"_"$5"_rb$2_gubra_space.nii.gz

   # rm -f niftis/reo_"$sample"_02x_down_"$5"_rb$2_chan.nii.gz empty.nii.gz
  else 
    echo " " ; echo "  "$sample"_"$5"_rb$2_gubra_space.nii.gz exists, skipping" ; echo " "
  fi

  cd ..
done 

# Daniel Ryskamp Rijsketic 12/7/21 & 07/07/22 (Heifets lab)
#Austen Casey adapted to run with any directory name and round z dim to reduce glitch prevalence upon reverse warping 7/1/23
