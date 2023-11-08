#!/usr/bin/env python3

import argparse
import os

def process_directory(directory):
    # Extract the folder name if needed
    folder_name = os.path.basename(directory)
    print(f"Processing {folder_name} in {directory}")
    # Your processing logic here

def main():
    parser = argparse.ArgumentParser(description="Process a given directory.")
    parser.add_argument('--directory', type=str, required=True, help='The directory to process')
    args = parser.parse_args()

    process_directory(args.directory)

if __name__ == "__main__":
    main()