// ABA_cell_count_3D (Daniel Rijsketic Feb. 2, 2021)
//==========================================================

//Inputs: 1) ABAvox substack (ilastik_segemtation in ABA intensities from MIRACL)
//Outputs: csv with cell counts  to  seg_ilastik_XX/ABAvox_stacks folder. Object intensity denotes ABA region. 

setBatchMode(true);

// Input data
filelist = getArgument();
file = split(filelist,'#');
open(file[0]); //ABAseg substack (full stack will run out of GPU memory or time)
dirCSV = getDirectory("image"); //directory where CSV will be saved
ABAseg = getTitle();

//// Init GPU
//run("CLIJ Macro Extensions", "cl_device=");
//Ext.CLIJ_clear(); // Cleanup GPU memory 

//// 3D objects counter (max = max # of pixels to be counted as a single cell) 
run("3D Objects Counter on GPU (CLIJx, Experimental)", "cl_device=[Quadro P6000] threshold=1 min.=1 max.=1000 exclude_objects_on_edges statistics");

//Ext.CLIJ_clear(); // Cleanup GPU memory 

//export results as CSV in ilastik_segmentation directory                           
saveAs("Results", dirCSV+ABAseg+"_E.csv");

selectWindow(ABAseg);
close();

setBatchMode(false);

run("Quit");

//check 50 slice substack with max of 1000 and sort by pixel number to determine reasonable cutoff (or use bounding box Z dim)

