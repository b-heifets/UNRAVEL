// (c) Daniel Ryskamp Rijsketic, Boris Heifets @ Stanford University, 2022-2023
// 3D_count_CPU (Daniel Rijsketic May. 17, 2022; Heifets lab)
//==========================================================

setBatchMode(true);

// Input data
filelist = getArgument();
file = split(filelist,'#');
open(file[0]); 
dirCSV = getDirectory("image"); //directory where CSV will be saved
image = getTitle();

// Includes objects on edges
run("3D OC Options", "nb_of_obj._voxels close_original_images_while_processing_(saves_memory) store_results_within_a_table_named_after_the_image_(macro_friendly) redirect_to=none");

run("3D Objects Counter", "threshold=1 slice=1 min.=1 max.=1000 statistics");

saveAs("Results", dirCSV+image+".csv");

setBatchMode(false);

run("Quit");


