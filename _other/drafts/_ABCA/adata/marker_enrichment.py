#!/usr/bin/env python3
import sys
import numpy as np
import pandas as pd

fname = sys.argv[1]

df = pd.read_csv(fname)

print(df)
