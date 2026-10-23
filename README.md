# Source

[IXI – Information eXtraction from Images (EPSRC GR/S21533/02)](https://brain-development.org/ixi-dataset/):
- http://biomedic.doc.ic.ac.uk/brain-development/downloads/IXI/IXI-T1.tar
- http://biomedic.doc.ic.ac.uk/brain-development/downloads/IXI/IXI.xls

Download `IXI-T1.tar` and put it in `./data`. From the repository root, run:

```sh
python unzip.py
```

This uses only the Python standard library. It extracts every T1 `.nii.gz` from the tar into `data/IXI-T1`, flattens nested folders, decompresses each file to `.nii`, and deletes the `.nii.gz` files and any empty directories. `IXI-T1.tar` is left in `./data`.

# Brain volumes

Install the Python packages, then skull-strip every T1 and write brain volume:

```sh
pip install -r requirements.txt
python process.py
```

`process.py` runs FreeSurfer `mri_synthstrip` (the install named in `freesurfer.sh`; on Windows, through WSL) and then the same calculation as `nibabel_volume.py`: nonzero voxels in the stripped image times the voxel volume. Stripped images are written to `data/brains/`. The table is `results/volumes.csv` with one row per scan (`subject`, `ixi_id`, `site`, `voxels`, `voxel_mm3`, `volume_ml`, `status`). Rows already marked `ok` are skipped, so the command can be stopped and run again.

SynthStrip runs on CPU. The PyTorch build shipped with this FreeSurfer install has no CUDA, and the full IXI T1 set takes a few hours.

If you use these volumes, cite SynthStrip: Hoopes et al., NeuroImage 260 (2022) 119474. https://doi.org/10.1016/j.neuroimage.2022.119474