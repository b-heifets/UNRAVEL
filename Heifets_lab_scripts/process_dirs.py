#!/usr/bin/env python3

import argparse
import subprocess

def run_script(script_name, directory):
    print(f"Running {script_name} on {directory}")
    result = subprocess.run([script_name, "--directory", directory], capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error in {directory}: {result.stderr}")
    else:
        print(result.stdout)

def main():
    parser = argparse.ArgumentParser(description="Process multiple directories with a specified script.")
    parser.add_argument('script', type=str, help='The script to run on each directory.')
    parser.add_argument('directories', type=str, nargs='+', help='The list of directories to process.')
    args = parser.parse_args()

    for directory in args.directories:
        run_script(args.script, directory)

if __name__ == "__main__":
    main()
