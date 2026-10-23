from pathlib import Path

import nibabel as nib
import numpy as np


def measure(path: Path) -> tuple[int, float, float]:
    """Return brain voxel count, voxel volume in mm^3, and brain volume in ml.

    Matches the one-off calculation below: nonzero voxels in a SynthStrip
    image, times the spatial voxel size. SynthStrip writes background as 0.
    """
    img = nib.load(path)
    data = img.get_fdata()
    zooms = np.array(img.header.get_zooms()[:3], dtype=np.float64)
    voxel_mm3 = float(np.prod(zooms))
    voxels = int(np.count_nonzero(data))
    return voxels, voxel_mm3, voxels * voxel_mm3 / 1000.0


if __name__ == "__main__":
    path = Path(__file__).parent / "data" / "IXI-T1" / "IXI169_brain.nii.gz"
    _, _, ml = measure(path)
    print(f"{ml:.1f} ml")
