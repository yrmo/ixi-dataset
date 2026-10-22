import random
from pathlib import Path

import matplotlib.pyplot as plt
import nibabel as nib


def load(path):
    return nib.load(path).get_fdata()


if __name__ == "__main__":
    paths = list(Path("data/IXI-T1").glob("*.nii"))
    path = random.choice(paths)
    volume = load(path)

    plt.imshow(volume[:, :, volume.shape[2] // 2].T, cmap="gray", origin="lower")
    plt.title(path.name)
    plt.axis("off")
    plt.show()
