#!/usr/bin/env python3

"""
Use ``abca_percent_expression_color_scale`` or ``pecs`` from UNRAVEL to save a color scale for the percent of cells expressing a gene.

Usage:
------ 
    abca_percent_expression_color_scale
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
    opts.add_argument('-min', '--min', help='min percent value for the colormap. Default: 0', default=0, type=float, action=SM)
    opts.add_argument('-max', '--max', help='max percent value for the colormap. Default: 100', default=100, type=float, action=SM)
    opts.add_argument('-o', '--output', help='path/percent_expression_scale.pdf', default='percent_expression_scale.pdf', action=SM)

    return parser.parse_args()

@log_command
def main():
    install()
    args = parse_args()

    # Define min and max values for the colormap (percent of expressing cells)
    vmin, vmax = args.min, args.max

    print(f"Percent expression colormap min: {vmin}")
    print(f"Percent expression colormap max: {vmax}")

    # Create a color map normalization instance
    norm = mcolors.Normalize(vmin=vmin, vmax=vmax)
    cmap = plt.cm.viridis_r  # Using reversed viridis colormap

    # Create the figure and axis
    fig, ax = plt.subplots(figsize=(6, 1))
    fig.subplots_adjust(bottom=0.5)

    # Create colorbar
    cbar = fig.colorbar(plt.cm.ScalarMappable(norm=norm, cmap=cmap), cax=ax, orientation='horizontal')
    cbar.set_label("% of Expressing Cells")

    # Remove y-axis labels
    cbar.ax.set_yticks([])

    # Save the color scale to a PDF file
    plt.savefig(args.output, bbox_inches='tight')
    

if __name__ == '__main__':
    main()
