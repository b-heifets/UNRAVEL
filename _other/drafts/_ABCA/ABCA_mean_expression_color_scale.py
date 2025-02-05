#!/usr/bin/env python3

"""
Use ``ABCA_mean_expression_color_scale.py`` from UNRAVEL to plot a color scale for mean expression values in the ABCA.

Usage:
------ 
    ABCA_mean_expression_color_scale.py
"""

import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import numpy as np
from rich import print
from rich.traceback import install

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.utils import log_command


def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    opts = parser.add_argument_group('Optional args')
    opts.add_argument('-min', '--min', help='min value for the gene expression colormap', default=0, action=SM)
    opts.add_argument('-max', '--max', help='max value for the gene expression colormap', default=8, action=SM)
    opts.add_argument('-o', '--output', help='path/magma_r_scale.pdf', default='magma_r_scale.pdf', action=SM)

    return parser.parse_args()

@log_command
def main():
    install()
    args = parse_args()

    # Define min and max values for the gene expression colormap
    vmin, vmax = float(args.min), float(args.max)

    print(f"Log2(CPM+1) Expression min: {vmin}")
    print(f"Log2(CPM+1) Expression max: {vmax}")

    # Create a color map normalization instance
    norm = mcolors.Normalize(vmin=vmin, vmax=vmax)
    cmap = plt.cm.magma_r

    # Create the figure and axis
    fig, ax = plt.subplots(figsize=(6, 1))
    fig.subplots_adjust(bottom=0.5)

    # Create colorbar
    cbar = fig.colorbar(plt.cm.ScalarMappable(norm=norm, cmap=cmap), cax=ax, orientation='horizontal')
    cbar.set_label("Log2(CPM+1) Expression")

    # Remove y-axis ticks and labels
    cbar.ax.set_yticks([])  # Remove y-axis labels

    # Save the color scale to a PDF file
    plt.savefig(args.output, bbox_inches='tight')

if __name__ == '__main__':
    main()