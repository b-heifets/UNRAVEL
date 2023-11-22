// to_native2 (Daniel Rijsketic 05/12/22 & 09/19/23; Heifets lab)
//===================================================

// "Reorient rev warped $image and scale to native res"
// /usr/local/miracl/depends/Fiji.app/ImageJ-linux64 --ij2 -macro to_native $PWD/clar_allen_reg/$image#$tif_x_dim#$tif_y_dim#$tif_z_dim
// Outputs: native_$image

setBatchMode(true);

inputlist=getArgument();
input=split(inputlist,'#');

open(input[0]);
dir=getDirectory("image");
input_image=getTitle();

//Reorient to native
run("Rotate 90 Degrees Right");
wait(1000); //Necessary to avoid a bug from when the prior and following steps are executed back to back
run("Flip Horizontally", "stack");

//Scale to full res
run("Scale...", "x=- y=- z=- width="+input[1]+" height="+input[2]+" depth="+input[3]+" interpolation=None process");

//Save native full res 
run("NIfTI-1", "save="+dir+"native_"+input_image+".nii");

setBatchMode(false);

run("Quit");
