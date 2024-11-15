#!/usr/bin/env python3

"""
Use ``360_animation.py`` from UNRAVEL to create a 360° rotation animation of a 3D image.

Usage:
------
    360_animation.py -i path/image -o path/video.mp4 [-min 0] [-max 1] [-f 120] [-sa 0] [-fps 20] [-r mip]
"""

import os
import napari
import numpy as np
from napari_animation import Animation
from pathlib import Path
from rich import print
from rich.traceback import install

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.config import Configuration
from unravel.core.img_io import load_3D_img
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg

def parse_args():
    parser = RichArgumentParser(formatter_class=SuppressMetavar, add_help=False, docstring=__doc__)

    reqs = parser.add_argument_group('Required arguments')
    reqs.add_argument('-i', '--input', help='path/image', required=True, action=SM)
    reqs.add_argument('-o', '--output', help='path/video.mp4', required=True, action=SM)

    opts = parser.add_argument_group('Optional arguments')
    opts.add_argument('-min', '--min_value', help='Minimum contrast value.', type=float, action=SM)
    opts.add_argument('-max', '--max_value', help='Maximum contrast value.', type=float, action=SM)
    opts.add_argument('-f', '--frames', help='Number of frames for the animation. Default: 120', default=120, type=int, action=SM)
    opts.add_argument('-sa', '--start_angle', help='Starting angle for the rotation. Default: 0', default=0, type=float, action=SM)
    opts.add_argument('-fps', '--fps', help='Frames per second for the animation. Default: 20', default=20, type=int, action=SM)
    opts.add_argument('-r', '--rendering', help='Rendering mode. Default: mip', default='mip', type=str, action=SM)

    general = parser.add_argument_group('General arguments')
    general.add_argument('-v', '--verbose', help='Increase verbosity', action='store_true', default=False)

    return parser.parse_args()

@log_command
def main():
    install()
    args = parse_args()
    Configuration.verbose = args.verbose
    verbose_start_msg()

    img = load_3D_img(args.input)

    if not args.min_value:
        args.min_value = img.min()

    if not args.max_value:
        args.max_value = img.max()

    os.environ["QT_QPA_PLATFORM"] = "offscreen"  # Prevents Qt from trying to open a window

    # Create a napari viewer and add your image
    viewer = napari.Viewer()
    layer = viewer.add_image(img, rendering=args.rendering)

    # Set contrast limits
    layer.contrast_limits = (args.min_value, args.max_value)

    # Optionally, set the initial rotation angle
    viewer.camera.angles = (args.start_angle, 0, 0)  # (azimuth, elevation, roll)

    # Initialize the animation
    animation = Animation(viewer)

    # Set up a 360° rotation
    angles = np.linspace(args.start_angle, args.start_angle + 360, args.frames)  # Full rotation starting at initial_angle

    for angle in angles:
        viewer.camera.angles = (angle, 0, 0)  # Keep elevation and roll fixed
        animation.capture_keyframe()  # Capture each frame

    # Save the animation
    animation.animate(args.output, fps=args.fps)

    verbose_end_msg()

if __name__ == '__main__':
    main()
