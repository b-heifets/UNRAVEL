#!/usr/bin/env python3

"""
Use ``360_animation.py`` from UNRAVEL to create a 360° rotation animation of a 3D image.

Usage:
------
    360_animation.py -i path/image -o path/video.mp4 [-min 0] [-max 1] [-f 120] [-sa 0] [-fps 20] [-r mip]
"""

import os
import imageio
import napari
import numpy as np
from napari_animation import Animation
from pathlib import Path
from rich import print
from rich.traceback import install
from skimage.io import imsave

from unravel.core.help_formatter import RichArgumentParser, SuppressMetavar, SM
from unravel.core.config import Configuration
from unravel.core.img_io import load_3D_img
from unravel.core.utils import log_command, verbose_start_msg, verbose_end_msg, print_func_name_args_times

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

    img = load_3D_img(args.input, desired_axis_order='zyx')

    if not args.min_value:
        args.min_value = img.min()

    if not args.max_value:
        args.max_value = img.max()

    print(f"\n    Contrast limits: ({args.min_value}, {args.max_value})\n")

    # Create the Napari viewer and animation
    os.environ["QT_QPA_PLATFORM"] = "offscreen"  # Prevents Qt from trying to open a window
    viewer = napari.Viewer()

    print(f"Camera angles: {viewer.camera.angles}")
    print(f"Camera zoom: {viewer.camera.zoom}")
    print(f"Camera center: {viewer.camera.center}")

    layer = viewer.add_image(img, rendering=args.rendering)
    layer.contrast_limits = (args.min_value, args.max_value)

    # Capture two identical keyframes
    animation = Animation(viewer)
    animation.capture_keyframe()  # First keyframe
    viewer.camera.angles = (args.start_angle + 0.1, 0, 0)  # Slightly adjust the angle for the second keyframe
    animation.capture_keyframe()  # Second keyframe

    # Save the animation with two keyframes as a short video
    temp_video_path = "temp_frame_video.mp4"  # Temporary path to store the two-frame video
    animation.animate(temp_video_path, fps=args.fps)

    # Extract the first frame and save it as a single-frame video
    with imageio.get_reader(temp_video_path, "ffmpeg") as reader:
        frame = reader.get_next_data()  # Extract the first frame

    with imageio.get_writer(args.output, fps=args.fps, codec='libx264', quality=10) as writer:
        writer.append_data(frame)  # Repeat the single frame in the final output

    # Clean up temporary file
    os.remove(temp_video_path)
    viewer.close()

    import sys ; sys.exit()

    verbose_end_msg()


    

    viewer.camera.center = [img.shape[1] // 2, img.shape[2] // 2, img.shape[0] // 2] # Center the camera
    viewer.camera.zoom = 1  # Adjust as needed
    viewer.camera.angles = (0, 0, 0)  # Reset angles
    # viewer.camera.angles = (args.start_angle, 0, 0)  # (azimuth, elevation, roll)

    layer = viewer.add_image(img, rendering=args.rendering)

    # Set contrast limits
    layer.contrast_limits = (args.min_value, args.max_value)

    # Initialize the animation
    animation = Animation(viewer)

    # Set up a 360° rotation
    angles = np.linspace(args.start_angle, args.start_angle + 360, args.frames)  # Full rotation starting at initial_angle

    for angle in angles:
        viewer.camera.angles = (angle, 0, 0)  # Keep elevation and roll fixed
        animation.capture_keyframe()  # Capture each frame

    # Save animation and clean up
    animation.animate(args.output, fps=args.fps)
    viewer.close()


    verbose_end_msg()

if __name__ == '__main__':
    main()
