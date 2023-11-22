setBatchMode(true);

// Load the TIFF image sequence
inputlist = getArgument();
input = split(inputlist, '#');
run("Image Sequence...", "open=[" + input[0] + "] sort");
name = getTitle();
dir = getDirectory("image");
ParentFolderPath = File.getParent(dir);
ParentFolder = File.getName(ParentFolderPath);

// Create duplicates for cell and fiber processing
run("Duplicate...", "title=cells.tif duplicate");
run("Duplicate...", "title=fibers_and_cells.tif duplicate");

// Convert intensities for cells
selectWindow("cells.tif");
setThreshold(0.9, 1.1); // Threshold for cells (intensity 1)
run("Convert to Mask", "method=Default background=Dark black");
run("NIfTI-1", "save=" + ParentFolderPath + "/" + ParentFolder + "_cells.nii");

// Convert intensities for fibers and cells combined
selectWindow("fibers_and_cells.tif");
setThreshold(1.9, 2.1); // Threshold for fibers and cells (intensity 1 and 2)
run("Convert to Mask", "method=Default background=Dark black");

// Subtract cell mask from fibers and cells mask to get only fibers
imageCalculator("Subtract create 32-bit stack", "fibers_and_cells.tif","cells.tif");
rename("fibers.tif");
run("Convert to Mask", "method=Default background=Dark black"); // Convert to binary mask
run("Invert", "stack");
run("NIfTI-1", "save=" + ParentFolderPath + "/" + ParentFolder + "_fibers.nii");

setBatchMode(false);

run("Quit");

