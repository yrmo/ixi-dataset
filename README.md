# IXI T1

Brain volumes for the [IXI](https://brain-development.org/ixi-dataset/) T1 set (EPSRC GR/S21533/02).

- [IXI-T1.tar](http://biomedic.doc.ic.ac.uk/brain-development/downloads/IXI/IXI-T1.tar)
- [IXI.xls](http://biomedic.doc.ic.ac.uk/brain-development/downloads/IXI/IXI.xls)

## Unpack

From the repository root, with `IXI-T1.tar` in `data/`:

```sh
python unzip.py
```

Standard library only. Writes flat `.nii` files to `data/IXI-T1` and leaves the tar in `data/`.

## Volumes

FreeSurfer `mri_synthstrip`, from the install in `freesurfer.sh` (WSL on Windows).

```sh
pip install -r requirements.txt
python process.py
```

Stripped images go to `data/brains/`. Volumes go to `results/volumes.csv`: millilitres per scan, from nonzero voxels times voxel size. Rows with `status` `ok` are skipped on the next run.

CPU only with this FreeSurfer build. The full set takes a few hours.

SynthStrip: Hoopes et al., NeuroImage 260 (2022) 119474. https://doi.org/10.1016/j.neuroimage.2022.119474
