// (c) Daniel Ryskamp Rijsketic, Boris Heifets @ Stanford University, 2021-2023
// 3D_count_IncludeEdges (Daniel Rijsketic Feb. 2, 2021; Heifets lab)
//==========================================================

//will run out of GPU memory if >50000-100000 cells with 6GB or GPU memory used by other processes

setBatchMode(true);

// Input data
filelist = getArgument();
file = split(filelist,'#');
open(file[0]); 
dirCSV = getDirectory("image"); //directory where CSV will be saved
image = getTitle();

//// 3D objects counter (max = max # of pixels to be counted as a single cell) 
run("3D Objects Counter on GPU (CLIJx, Experimental)", "cl_device=[Quadro P6000] threshold=1 min.=1 max.=1000 statistics");

saveAs("Results", dirCSV+image+"_I.csv");

setBatchMode(false);

run("Quit");


