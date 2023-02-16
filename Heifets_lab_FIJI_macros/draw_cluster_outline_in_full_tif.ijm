// (c) Daniel Ryskamp Rijsketic, Boris Heifets @ Stanford University, 2022-2023
setBatchMode(true); 

inputlist = getArgument();
input = split(inputlist,'#');

open(input[0]);
setSlice(input[1]);
setThreshold(1, 255);
setOption("BlackBackground", true);
run("Create Selection");
run("Make Inverse");

open(input[2]);
dir = getDirectory("image");
image = getTitle();
run("Restore Selection");
setBackgroundColor(255, 255, 255);
setForegroundColor(255, 255, 255);
run("Draw", "slice");
saveAs("Tiff", input[3]+"outline_"+image);

setBatchMode(false);
run("Quit");

// Daniel Ryskamp Rijsketic 9/7/22 (Heifets lab)
