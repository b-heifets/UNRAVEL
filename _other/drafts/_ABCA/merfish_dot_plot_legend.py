#!/usr/bin/env python3

"""
Use merfish_dot_plot_legend.py from UNRAVEL for a standalone legend for the MERFISH dot plot.
"""

import matplotlib.pyplot as plt
import seaborn as sns
import argparse
import numpy as np
from pathlib import Path
from rich import print
from rich.traceback import install

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.config import Configuration
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg

def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-o', '--output', help='Path/legend.pdf. Default: dot_plot_legend.pdf', default='dot_plot_legend.pdf', action=SM)
    opts.add_argument('--min_color', help='Min color value. Default: 0', default=0, type=float)
    opts.add_argument('--max_color', help='Max color value. Default: 8', default=8, type=float)
    opts.add_argument('--min_size', help='Min dot size. Default: 0', default=0, type=float)
    opts.add_argument('--max_size', help='Max dot size. Default: 100', default=100, type=float)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity', action='store_true', default=False)

    return parser.parse_args()

def save_legend(output_path, min_color=0, max_color=8, min_size=1, max_size=100):
    """
    Generate and save a standalone legend with separate labels for Mean Expression and Percent Expression.
    """

    fig, ax = plt.subplots(figsize=(3, 5))  # Adjusted size for better spacing
    ax.axis("off")

    # Define mean expression color gradient
    mean_values = np.linspace(min_color, max_color, 5)
    mean_colors = [sns.color_palette("magma_r", as_cmap=True)(v / max_color) for v in mean_values]

    # Define percent expressing sizes
    percent_values = np.array([0, 25, 50, 75, 100])  # Ensuring 100% is included
    percent_sizes = np.interp(percent_values, [0, 100], [min_size, max_size])

    # Adjust positioning for better alignment
    mean_y_start = 0.85
    percent_y_start = 0.4
    spacing = 0.08  # Reduced spacing

    # Plot Mean Expression Legend
    ax.text(0.5, mean_y_start + 0.05, "Mean Expression", fontsize=12, ha="center", fontweight="bold", transform=ax.transAxes)
    for i, (val, color) in enumerate(zip(mean_values, mean_colors)):
        y_pos = mean_y_start - i * spacing
        ax.scatter(0.2, y_pos, s=100, c=[color], edgecolors="black", lw=0.5, transform=ax.transAxes)
        ax.text(0.4, y_pos, f"{val:.1f}", fontsize=11, verticalalignment="center", transform=ax.transAxes)

    # Plot Percent Expressing Legend
    ax.text(0.5, percent_y_start + 0.05, "Percent Expressing", fontsize=12, ha="center", fontweight="bold", transform=ax.transAxes)
    for i, (val, size) in enumerate(zip(percent_values, percent_sizes)):
        y_pos = percent_y_start - i * spacing
        ax.scatter(0.2, y_pos, s=size, c="black", edgecolors="black", lw=0.5, transform=ax.transAxes)
        ax.text(0.4, y_pos, f"{val:.1f}", fontsize=11, verticalalignment="center", transform=ax.transAxes)

    # Save the legend as a PDF file
    pdf_output = output_path if output_path.endswith(".pdf") else output_path + ".pdf"
    fig.savefig(pdf_output, bbox_inches="tight", dpi=300, format="pdf")
    print(f"\nLegend saved to {pdf_output}\n")

@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    save_legend(args.output, args.min_color, args.max_color, args.min_size, args.max_size)

    verbose_end_msg()


if __name__ == '__main__':
    main()
