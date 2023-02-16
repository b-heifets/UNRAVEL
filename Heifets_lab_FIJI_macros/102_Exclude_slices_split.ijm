// (c) Daniel Ryskamp Rijsketic, Boris Heifets @ Stanford University, 2021-2023
// divide_Exclude_substack_into_3 (Daniel Rijsketic Jan. 29, 2021)
//opens 102_slice_exclude_substack and splits into 3 substacks and saves. Shell script deletes original csv and tif having 3dc error.

//Inputs: 1) if csv has error, process corresponding tif file 

//3d_count_cluster3.sh at /usr/local/miracl/miracl/seg

setBatchMode(true); 

filelist = getArgument();
file = split(filelist,'#');

//************ 1) Open tif substack ************************************************
open(file[0]); 
dir = getDirectory("image");
substack=getTitle();

//for 102e if error -> -floor(102/3)+1=34+1 -> 35e 34i 35e
//e1-35      i35-68    e68-102
run("Duplicate...", "duplicate range=1-35");
run("NIfTI-1", "save="+dir+"/"+substack+"_1_35_ExcludeMid.nii"); //This is an Exclude objects on edges substack Mid level split
close();
selectWindow(substack);
run("Duplicate...", "duplicate range=35-68");
run("NIfTI-1", "save="+dir+"/"+substack+"_35_68_IncludeMid.nii"); //This is an Include objects on edges substack Mid level split
close();
selectWindow(substack);
run("Duplicate...", "duplicate range=68-102");
run("NIfTI-1", "save="+dir+"/"+substack+"_68_102_ExcludeMid.nii"); //This is an Exclude objects on edges substack Mid level split
close();
selectWindow(substack);
close();

setBatchMode(false);
EndTime=getTime();

run("Quit");


