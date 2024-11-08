#!/usr/bin/env python3

"""
Use ``cstats_clusters`` (``clusters``) from UNRAVEL to make a cluster index image from a .nii.gz image.
Note:
    - This uses the cluster command from FSL and then reverses the clusters so that the largest cluster is 1, the second largest is 2, etc.

Usage
-----
    cstats_clusters -i path/image.nii.gz [-ms 100] [-t 0.5] [-o path/image_rev_cluster_index.nii.gz] [-v]
"""

import numpy as np
import nibabel as nib
from rich.traceback import install

from unravel.cluster_stats.fdr import cluster_index, reverse_clusters
from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.config import Configuration
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-i', '--input', help='path/image.nii.gz', required=True, action=SM)

    opts = parser.add_argument_group('Optional args')
    opts.add_argument('-ms', '--min_size', help='Min cluster size in voxels. Default: 100', default=100, type=int, action=SM)
    opts.add_argument('-t', '--threshold', help='Threshold for cluster formation. Default: 0.5', default=0.5, type=float, action=SM)
    opts.add_argument('-o', '--output', help='path/image_cluster_index.nii.gz', default=None, action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity. Default: False', default=False, action='store_true')

    return parser.parse_args()


@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    output = args.output if args.output else args.input.replace('.nii.gz', '_rev_cluster_index.nii.gz')

    cluster_index(args.input, args.min_size, args.threshold, output)

    # Load the cluster index and convert to an ndarray
    cluster_index_nii = nib.load(output)
    cluster_index_img = np.asanyarray(cluster_index_nii.dataobj, dtype=np.uint16).squeeze()

    # Lower the data type if the max cluster ID is less than 256 
    max_cluster_id = int(cluster_index_img.max())
    data_type = np.uint16 if max_cluster_id >= 256 else np.uint8
    cluster_index_img = cluster_index_img.astype(data_type)

    # Reverse cluster ID order in cluster_index and save it
    rev_cluster_index_img = reverse_clusters(cluster_index_img, output, data_type, cluster_index_nii)

    verbose_end_msg()
    

if __name__ == '__main__':
    main()