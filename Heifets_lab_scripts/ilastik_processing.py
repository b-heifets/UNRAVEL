import sys
import numpy as np
from ilastik import app
from ilastik.applets.dataSelection import PreloadedArrayDatasetInfo
from ilastik.workflows.pixelClassification import PixelClassificationWorkflow

# Load the ndarray from the .npy file
img_array = np.load(sys.argv[2])

# Setup ilastik
args = app.parse_args(['--headless', f'--project={sys.argv[1]}'])
shell = app.main(args)
assert isinstance(shell.workflow, PixelClassificationWorkflow)

# Prepare data for ilastik
dataset_info = PreloadedArrayDatasetInfo(preloaded_array=img_array)
role_data_dict = {"Raw Data": [dataset_info]}

# Process the data
results = shell.workflow.batchProcessingApplet.run_export(role_data_dict, export_to_array=True)

# Optionally, save the results
np.save(f'{sys.argv[3]}', results[0])