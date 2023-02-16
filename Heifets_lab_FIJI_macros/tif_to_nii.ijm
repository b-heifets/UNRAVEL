// (c) Daniel Ryskamp Rijsketic, Boris Heifets @ Stanford University, 2021-2023
setBatchMode(true);

filelist = getArgument();
file = split(filelist,'#');

//************ 1) Open image ************************************************
open(file[0]);
name = getTitle(); 
dir = getDirectory("image");

run("NIfTI-1", "save="+dir+"/"+name+".nii");

setBatchMode(false);

run("Quit");

//Daniel Ryskamp Rijsketic 07/21/21 (Heifets lab)
