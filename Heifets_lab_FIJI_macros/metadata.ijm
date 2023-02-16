// (c) Daniel Ryskamp Rijsketic, Boris Heifets @ Stanford University, 2022-2023
setBatchMode(true);

inputlist = getArgument();
input = split(inputlist,'#');

//************ 1) Open 3D image ************************************************
run("Bio-Formats Importer", "open="+input[0]+" color_mode=Default rois_import=[ROI manager] view=Hyperstack stack_order=XYCZT use_virtual_stack");
dir=getDirectory("image");
run("Show Info...");
run("Text...", "save="+dir+"/metadata");

setBatchMode(false);

run("Quit");

//Daniel Ryskamp Rijsketic 07/08/22 (Heifets lab)
