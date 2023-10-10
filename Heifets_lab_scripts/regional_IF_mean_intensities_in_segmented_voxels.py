#!/usr/bin/env python3

import argparse
import csv
import numpy as np
import nibabel as nib
import unravel_utils as unrvl

def parse_args():
    parser = argparse.ArgumentParser(description='Measure mean intensity of immunofluorescence staining in brain regions for segmented voxels.')
    parser.add_argument('-t', '--tif_dir', help='path/dir with raw immunuofluo tif series', required=True, metavar='')
    parser.add_argument('-s', '--seg', help='path/sample??_ABA_<IF>_seg_ilastik_*.nii.gz (segmented image with regional intensities)', required=True, metavar='')
    parser.add_argument('-o', '--output', help='path/name.csv', default=None, metavar='')
    return parser.parse_args()

def get_regional_IF_mean_intensities_in_seg_voxels(raw_image_dir, segmented_image_path):
    # Load the images
    raw_img = unrvl.load_tifs(raw_image_dir)
    raw_img = np.transpose(raw_img, (2, 1, 0))
    # raw_img = tiff_series_to_numpy(raw_image_dir)
    print(f"{raw_img.shape=}")
    segmented_img = nib.load(segmented_image_path).get_fdata()
    segmented_img = np.squeeze(segmented_img)
    print(f"{segmented_img.shape=}")

    # Ensure the images have the same shape
    if segmented_img.shape != raw_img.shape:
        raise ValueError("  Both images must have the same shape.")

    # Get unique region labels from the segmented image (excluding 0 if it's present, as it's usually background)
    unique_labels = [int(label) for label in np.unique(segmented_img) if label != 0]

    # Calculate mean intensity and voxel count for each region
    mean_intensities = {}
    voxel_counts = {}
    for label in unique_labels:
        print(f"Processing Region ID: {label}")

        # Get mask for the current region
        mask = segmented_img == label
        
        # Compute the mean intensity of raw image for the current region
        mean_intensities[label] = raw_img[mask].mean()
        
        # Count the number of segmented voxels for the region
        voxel_counts[label] = mask.sum()

    return mean_intensities, voxel_counts

def write_to_csv(region_IDs, mean_intensities, voxel_counts, output_file):
    with open(output_file, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["Region_Intensity", "Mean_IF_Intensity", "Voxel_Count"])
        for region in region_IDs: 
            writer.writerow([region, mean_intensities[region], voxel_counts[region]])

def main():
    args = parse_args()

    #list of region intensities/IDs in atlas
    region_IDs = [1, 2, 6, 7, 9, 10, 12, 15, 17, 19, 20, 22, 23, 26, 27, 28, 30, 33, 35, 36, 38, 41, 42, 50, 52, 54, 56, 58, 59, 62, 63, 64, 66, 67, 68, 72, 74, 75, 78, 81, 83, 84, 88, 91, 93, 96, 97, 98, 100, 101, 102, 105, 106, 108, 113, 114, 115, 117, 118, 120, 121, 122, 123, 125, 126, 128, 129, 131, 132, 133, 136, 139, 140, 143, 145, 146, 147, 148, 149, 153, 155, 156, 158, 159, 162, 163, 164, 169, 171, 173, 177, 178, 180, 181, 184, 186, 187, 188, 189, 190, 194, 196, 197, 198, 201, 202, 203, 204, 206, 207, 209, 210, 211, 214, 215, 217, 218, 222, 223, 225, 226, 229, 230, 231, 233, 234, 237, 238, 243, 246, 249, 250, 251, 252, 255, 257, 258, 260, 262, 263, 266, 268, 269, 271, 272, 274, 279, 280, 281, 286, 287, 288, 289, 292, 296, 298, 301, 303, 304, 305, 307, 310, 311, 313, 314, 318, 320, 321, 325, 326, 327, 328, 329, 330, 332, 333, 334, 335, 336, 338, 342, 344, 347, 349, 350, 351, 354, 355, 356, 358, 362, 363, 364, 366, 368, 372, 374, 377, 380, 381, 382, 390, 393, 397, 401, 403, 412, 413, 414, 421, 422, 423, 427, 428, 429, 430, 433, 434, 436, 437, 440, 441, 442, 443, 445, 448, 449, 450, 451, 452, 456, 460, 461, 463, 466, 469, 470, 477, 478, 482, 483, 484, 488, 501, 502, 506, 507, 510, 512, 515, 520, 523, 525, 526, 527, 530, 531, 534, 538, 540, 542, 543, 544, 549, 551, 553, 556, 558, 559, 564, 565, 566, 573, 574, 575, 576, 577, 579, 580, 581, 582, 583, 587, 588, 590, 591, 593, 595, 596, 597, 598, 599, 600, 601, 603, 604, 605, 608, 609, 610, 611, 612, 613, 614, 616, 620, 621, 622, 625, 628, 629, 630, 632, 633, 634, 638, 639, 642, 643, 648, 649, 651, 653, 654, 655, 656, 657, 658, 661, 662, 663, 664, 665, 667, 670, 671, 672, 673, 675, 678, 679, 680, 681, 685, 687, 689, 690, 692, 693, 694, 696, 697, 698, 699, 702, 703, 704, 706, 707, 711, 718, 721, 725, 727, 728, 729, 732, 733, 735, 741, 743, 744, 749, 750, 753, 754, 755, 757, 759, 763, 765, 767, 771, 772, 773, 774, 776, 778, 780, 781, 783, 784, 786, 788, 791, 794, 795, 797, 798, 800, 802, 803, 804, 805, 806, 810, 811, 812, 814, 816, 819, 820, 821, 827, 828, 830, 831, 832, 834, 836, 838, 839, 841, 842, 843, 844, 846, 847, 849, 850, 851, 852, 854, 857, 859, 862, 863, 866, 867, 869, 872, 873, 874, 878, 880, 882, 884, 888, 889, 893, 897, 898, 900, 902, 903, 905, 906, 907, 908, 910, 911, 912, 914, 916, 919, 924, 927, 929, 930, 931, 935, 936, 939, 940, 943, 944, 945, 946, 949, 950, 951, 952, 954, 955, 956, 957, 959, 961, 962, 963, 964, 965, 966, 968, 969, 970, 971, 973, 974, 975, 976, 977, 978, 980, 981, 982, 984, 986, 988, 989, 990, 996, 997, 998, 1004, 1005, 1006, 1007, 1009, 1010, 1015, 1016, 1020, 1021, 1022, 1023, 1025, 1026, 1029, 1030, 1031, 1033, 1035, 1037, 1038, 1039, 1041, 1043, 1044, 1045, 1046, 1047, 1048, 1049, 1052, 1054, 1056, 1058, 1060, 1061, 1062, 1064, 1066, 1069, 1070, 1072, 1074, 1077, 1079, 1081, 1084, 1085, 1086, 1088, 1089, 1090, 1091, 1092, 1093, 1094, 1096, 1097, 1098, 1101, 1102, 1104, 1105, 1106, 1107, 1108, 1109, 1111, 1113, 1114, 1116, 1120, 1121, 1123, 1125, 1126, 1127, 1128, 1139, 1140, 1141, 1142]

    mean_intensities, voxel_counts = get_regional_IF_mean_intensities_in_seg_voxels(args.tif_dir, args.seg)

    if args.output is None:
        args.output = args.seg.replace('.nii.gz', '_regional_mean_intensities.csv')

    # Write to CSV
    write_to_csv(region_IDs, mean_intensities, voxel_counts, args.output)


if __name__ == '__main__':
    main()

