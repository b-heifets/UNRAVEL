// (c) Daniel Ryskamp Rijsketic, Boris Heifets @ Stanford University, 2022-2023
// extract_most_sig_slice (Daniel Rijsketic May 31, 2022; Heifets lab)
//==========================================================

setBatchMode(true);

inputlist = getArgument();
input = split(inputlist,'#');

open(input[0]); 
image = getTitle()
dir = getDirectory("image");

Stack.setSlice(input[1]); 	
run("Duplicate...", " ");

saveAs("Tiff", dir+"/most_sig_slice_"+image);

setBatchMode(false);

run("Quit");


