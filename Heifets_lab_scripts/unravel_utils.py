#!/usr/bin/env python3

import os
import sys
from termcolor import colored
from datetime import datetime

def print_cmd():
    print("\nRunning " +  colored(f"{os.path.basename(sys.argv[0])}", 'magenta', None, ['bold']) + f" starting at {datetime.now().strftime('%H:%M:%S')}\n")
    cmd_args = [os.path.basename(sys.argv[0])] + sys.argv[1:]
    print(colored(' '.join(cmd_args), 'cyan') + "\n")
    
# Daniel Rijsketic 08/17/2023 (Heifets lab)
