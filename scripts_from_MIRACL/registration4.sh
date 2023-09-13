#!/usr/bin/env bash
#(c) Maged Goubran 2017, Daniel Rijsketic 2023, Boris Heifets 2023
#Adapted from miracl_reg_clar-allen_whole_brain.sh by Daniel Ryskamp Rijsketic 03/17/23 & 08/25/23

if [[ $# == 0 || "$1" == "-h" || "$1" == "--help" || "$1" == "help" ]] ; then
  echo '
From ./sample??/ run: 
registration.sh -i <niftis/sample??_##x_down_autofl_chan.nii.gz> -o <orientation code> 

Registers average template brain/atlas to downsampled autofl brain.

Required arguments:
  -i:  input
  -o:  orientation code (e.g. <ARS>) to reorient nifti to atlas space (A/P, R/L, S/I)

Optional arguments (-l overrides -m & -v) ###################################################
  -m:  <split> (left hemisphere intensities increased by 20000) or 
       <combined> (symmetric) atlas (default: split)
  -v:  labels voxel size in um <10>, <25>, or <50> (default: 25) ##########################################################	
  -l:  <path/atlas> to warp (default: gubra_ano_split_10um.nii.gz) ##########################################################
  -s:  side, if registering a hemisphere instead of whole brain: 
       <rh> (right hemisphere) or <lh> (left)
  -t:  olfactory bulb exists <1>, doesn'\''t exist <0>, or <path/custom_template.nii.gz> (default: 1)
  -x:  ./mask.nii.gz (e.g., ./reg_input/autofl_50um_brain_mask.nii.gz (default: no mask, which is slower)

Outputs:
  reg_final/clar_downsample_res(vox)um.nii.gz : Autofluo data downsampled and oriented to "standard"
  reg_final/annotation_hemi_(hemi)_(vox)um_clar_downsample.nii.gz : atlas labels registered to downsampled autofluo

To check registration, from reg_final run itksnap.sh or for ABA coloring itksnap.sh a 

Dependencies: ANTs (https://github.com/stnava/ANTs) & c3d (https://sourceforge.net/projects/c3d)
'
  exit 1
fi

while getopts ":i:o:l:m:v:s:t:x:" opt; do 
  case "${opt}" in
    i) inclar="${OPTARG}" ;;
    o) ort="${OPTARG}" ;;
    l) lbls="${OPTARG}" ;;
    m) hemi="${OPTARG}" ;;
    v) vox="${OPTARG}" ;;
    s) side="${OPTARG}" ;;
    t) template="${OPTARG}" ;;
    x) mask="${OPTARG}" ;;
    *) usage ;;
  esac	
done    

atlasdir=${MIRACL_HOME}/atlases
regdirfinal=$PWD/reg_final # main outputs
regdir=$PWD/clar_allen_reg

if [[ ! -d ${regdir} ]]; then mkdir -p ${regdirfinal} ${regdir} ; fi

# Log stderr
exec > >(tee -i ${regdir}/clar_allen_script.log) ; exec 2>&1

# Check inputs
if [[ ! $ort =~ ^[APRLIS][APRLIS][APRLIS]$ ]]; then 
  printf "\n ERROR: Orientation code not valid. Valid example: ARS \n\n" ; exit 1
fi

# Specify atlas to use 
if [[ -z $lbls ]]; then 
  if [[ "$hemi" != "split" || "$hemi" != "combined" ]] ; then hemi="split" ; fi #default
  if [[ -z $vox ]]; then vox=25 ; fi #default 
  lbls=$atlasdir/ara/gubra/gubra_ano_${hemi}_${vox}um.nii.gz
fi 

# Set side for hemisphere registration
if [[ -z ${side} ]] ; then side="" #default for whole brain
elif [[ "${side}" == "rh" ]]; then side="_right"
elif [[ "${side}" == "lh" ]]; then side="_left"
fi


############################
####### Registration #######
############################

START=$(date +%s)

function ifdsntexistrun() {  
  local output="$1"; local cmd_description="$2"; local command="${@:3}"
  if [[ ! -f $output ]]; then
    printf "\n  $cmd_description: \n" ; echo "$command" ; eval $command
  else  
    printf "\n  $output exists, skipping \n" 
  fi
}

# Add autofl_50um.nii.gz to ./clar_allen_reg 
if [[ -z $inclar ]]; then 
  inclar=$PWD/reg_input/autofl_50um.nii.gz #default
fi 

resclar=${regdir}/autofl_50um.nii.gz
if [[ ! -f $res_clar ]]; then 
  if [[ -f $inclar ]]; then 
    cp $inclar $resclar
  else 
    ifdsntexistrun $resclar "Resample autofl to 50 micron resolution" \
    zoom.sh $inclar m m m 50 uint16 ; if [ -f ${inclar::-7}_50um.nii.gz ]; then mv ${inclar::-7}_50um.nii.gz $resclar ; fi
  fi
fi

# N4 bias correct
biasclar=$regdir/autofl_50um_bias.nii.gz
if [[ -z $mask ]]; then
  ifdsntexistrun $biasclar "Bias-correcting 50 micron autofluo image" \
N4BiasFieldCorrection -d 3 -i ${regdir}/autofl_50um.nii.gz -s 2 -t [0.15,0.01,200] -o $biasclar
else 
  ifdsntexistrun $biasclar "Bias-correcting 50 micron autofluo image using mask" \
N4BiasFieldCorrection -d 3 -i ${regdir}/autofl_50um.nii.gz -s 2 -t [0.15,0.01,200] -o $biasclar -x $mask
fi

# Pad image
padclar=$regdir/autofl_50um_pad.nii.gz
ifdsntexistrun $padclar "Padding image with 15 percent of voxels" \
c3d $biasclar -pad 15% 15% 0 -o ${padclar}

# Orient
ortclar=$regdir/autofl_50um_ort.nii.gz
ifdsntexistrun $ortclar "Orienting autofluo to standard orientation" \
c3d $padclar -orient $ort -interpolation Cubic -type float -o $ortclar #-type < char | uchar | short | ushort | int | uint | float | double > ; -interpolation <NearestNeighbor|Linear|Cubic|Sinc|Gaussian> [param]

# Smooth
smclar=$regdir/autofl_50um_sm.nii.gz
ifdsntexistrun $smclar "Smoothing autofluo image" \
c3d $ortclar -smooth 0.25vox -o $smclar

# Initial registration of average template to autofluo image (50um & smoothed) 
if [[ -z $template ]]; then
  template=$atlasdir/ara/gubra/gubra_template_25um${side}.nii.gz #default
elif [[ "$template" == 0 ]]; then
  template=$atlasdir/ara/gubra/gubra_template_wo_OB_25um${side}.nii.gz
elif [[ "$template" == 1 ]]; then
  template=$atlasdir/ara/gubra/gubra_template_25um${side}.nii.gz
else 
  printf "\n  Using custom template \n"
fi
printf "\n  Average template brain: $template \n"

smclar_cp=$regdir/clar.nii.gz
if [[ ! -f "$smclar_cp" ]]; then cp $smclar $smclar_cp ; fi 
initform=$regdir/init_tform.mat #antsAffineInitializer transform output filename (intial transform matrix)
deg=1 # search increment in degrees
radian_fraction=1 # between 0 and 1 --- will search this arc +/- around principal axis
useprincax=0 # rotation searched around an initial principal axis (boolean)
localiter=500 # num of iterations of local optimization at each search point (default 20)
initallen=$regdir/init_allen.nii.gz #Template initially aligned with 50 um clar

ifdsntexistrun $initform "Generating initial tranform for warping template to downsampled and smoothed autofluo image" \
antsAffineInitializer 3 $smclar_cp $template $initform $deg $radian_fraction $useprincax $localiter 2> /dev/null &

if [[ ! -f $initallen ]]; then sleep 180 ; kill -9 $(ps -e | grep antsAffineInit | awk '{print $1}') ; fi # kill after 3 min (gcc issue) 

ifdsntexistrun $initallen "Warping template to 50 micron autofluo image" \
antsApplyTransforms -i $template -r $smclar_cp -t $initform -o $initallen

# Refined registration of warped template to smoothed 50um autofluo img
transform=b         # rigid + affine + deformable b-spline syn
spldist=26          # spline distance for deformable B-spline SyN transform (default = 26)
rad=2 	            # radius for cross correlation metric used during SyN stage (default = 4)
precision=d         # double precision (otherwise ITK error in some cases!)
threads=`nproc`     # get num of cores 
antsallen=$regdir/allen_clar_antsWarped.nii.gz # output
c3d $initallen -type int -o $initallen

ifdsntexistrun $antsallen "Bspline registration of template to 50 micron autofluo image" \
antsRegistrationMIRACL.sh -d 3 -f $smclar_cp -m $initallen -o $regdir/allen_clar_ants -t $transform -p $precision \
-n $threads -s $spldist -r $rad | tee -a $regdir/ants_reg.log #-f=fixed_img, -m=moving_img, -o=out_prefix, -t=transform_type 

# Warp atlas to original autofluo 
antswarp=$regdir/allen_clar_ants1Warp.nii.gz             	 # transforms
antsaff=$regdir/allen_clar_ants0GenericAffine.mat                # transforms
base=`basename $lbls` ; lblsname=${base%%.*}                     # e.g., gubra_ano_split_10um prefix
wrplbls=$regdirfinal/${lblsname}_clar_downsample.nii.gz          # out lbls
ortlbls=$regdir/${lblsname}_ants_ort.nii.gz                      # ort pars
swplbls=$regdir/${lblsname}_ants_swp.nii.gz                      # swap lbls
reslbls=$regdirfinal/${lblsname}_clar.nii.gz                     # Up lbls (input nifti res?)              
smclarres=$regdirfinal/clar_downsample_res${vox}um.nii.gz        # res clar
wrplblsorg=$regdir/${lblsname}_ants_org.nii.gz                   # lbls to org nii
orgortlbls=$regdir/${lblsname}_ants_org_ort.nii.gz        	 # lbls to org nii
lblsorgnii=$regdirfinal/${lblsname}_clar_space_downsample.nii.gz # lbls to org nii

# Res clar in
ifdsntexistrun $smclarres "Upsampling smoothed 50um autofl image to ${vox}um resolution" \
zoom.sh $smclar m m m $vox uint16 ; if [ -f ${smclar::-7}_${vox}um.nii.gz ]; then mv ${smclar::-7}_${vox}um.nii.gz $smclarres ; fi 

# Warp to registered clarity
ifdsntexistrun $wrplbls "Applying ants deformation to atlas" \
antsApplyTransforms -d 3 -r $smclarres -i $lbls -n MultiLabel -t $antswarp $antsaff $initform \
-o $wrplbls --float # -r <reference-img> -t <transform(s)>

# Get org tag (slow with larger niftis. Perhaps nibabel would be faster)
ortmatrix=`PrintHeader $inclar 4 | tr 'x' ' '` ### Get ortientation matrix (Direction) w/ space delimiter rather than x delimiter 

ifdsntexistrun $ortlbls "Orienting atlas labels" \ 
SetDirectionByMatrix $wrplbls $ortlbls $ortmatrix

# Swap dim (x=>y / y=>x)
ifdsntexistrun $swplbls "Swapping atlas dimensions" \
PermuteFlipImageOrientationAxes 3 $ortlbls $swplbls  1 0 2  0 0 0

# Warp nifti to org space
orgspacing=`PrintHeader $inclar 1`

ifdsntexistrun $wrplblsorg "Resampling labels to original space" \
ResampleImage 3 $wrplbls $wrplblsorg $orgspacing 0 1
###zoom.sh $wrplbls m m m $orgspacing ; mv ${wrplbls::-7}_50um.nii.gz $wrplblsorg ### need to  enable resizing (not just isotropic resampling) add in option for NN interpolation

ifdsntexistrun ${orgortlbls} "Orienting atlas labels to original space" \
SetDirectionByMatrix ${wrplblsorg} ${orgortlbls} ${ortmatrix}

END=$(date +%s) ; DIFF=$((END-START)) ; DIFF=$((DIFF/60))
printf "\n Registration for ${PWD##*/} completed in $DIFF minutes. \n"
