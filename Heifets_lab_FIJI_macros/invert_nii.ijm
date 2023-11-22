setBatchMode(true); 

inputlist = getArgument();
input = split(inputlist,'#');

open(input[0]);
name = getTitle(); 
dir = getDirectory("image");

run("Invert", "stack");

run("NIfTI-1", "save="+dir+name+".nii");

setBatchMode(false);

run("Quit");

