from pathlib import Path

import nibabel as nib
import numpy as np

img = nib.load(Path(__file__).parent / "data" / "IXI-T1" / "IXI169_brain.nii.gz")
data = img.get_fdata()
voxel_vol = np.prod(img.header.get_zooms())

brain_voxels = np.count_nonzero(data)
print(f"{brain_voxels * voxel_vol / 1000:.1f} ml")
