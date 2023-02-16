// (c) Daniel Ryskamp Rijsketic, Boris Heifets @ Stanford University, 2022-2023
// to_native (Daniel Rijsketic May. 12, 2022; Heifets lab)
//===================================================

// "Resample, crop padding, reorient $image to 2xDS native and native res"
// /usr/local/miracl/depends/Fiji.app/ImageJ-linux64 --ij2 -macro to_native $PWD/clar_allen_reg/$image#$new_x_dim#$new_y_dim#$new_z_dim#$xmin#$DS_atlas_x#$ymin#$DS_atlas_y#$zmin#$DS_atlas_z#$tif_x_dim#$tif_y_dim#$tif_z_dim
// Outputs: 2xDS_native_$image and native_$image in reg_final 

setBatchMode(true);

inputlist=getArgument();
input=split(inputlist,'#');

open(input[0]);
dir=getDirectory("image");
ParentFolderPath=File.getParent(dir);
ParentFolder=File.getName(ParentFolderPath); 
reg_final_path=ParentFolderPath+"/reg_final/"
input_image=getTitle();

//Scale to 2xDS native res
run("Scale...", "x=- y=- z=- width="+input[1]+" height="+input[2]+" depth="+input[3]+" interpolation=None process");

//Crop padding
makeRectangle(input[4], input[6], input[5], input[7]); 
run("Crop");
run("Duplicate...", "duplicate range="+input[8]+"-"+input[9]);

//Reorient to native
run("Rotate 90 Degrees Right");
wait(1000);
run("Flip Horizontally", "stack");

//Save 2x downsampled native
run("NIfTI-1", "save="+dir+"2xDS_native_"+input_image+".nii");

//Scale to full res
//run("Scale...", "x=- y=- z=- width="+input[10]+" height="+input[11]+" depth="+input[12]+" interpolation=None process");

//Save native full res 
//run("NIfTI-1", "save="+dir+"native_"+input_image+".nii");

setBatchMode(false);

run("Quit");
