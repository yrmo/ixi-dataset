# Source

[IXI – Information eXtraction from Images (EPSRC GR/S21533/02)](https://brain-development.org/ixi-dataset/):
- http://biomedic.doc.ic.ac.uk/brain-development/downloads/IXI/IXI-T1.tar
- http://biomedic.doc.ic.ac.uk/brain-development/downloads/IXI/IXI.xls

Download `IXI-T1.tar` and put it in `./data`. From the repository root, run:

```sh
python unzip.py
```

This uses only the Python standard library. It extracts every T1 `.nii.gz` from the tar into `data/IXI-T1`, flattens nested folders, decompresses each file to `.nii`, and deletes the `.nii.gz` files and any empty directories. `IXI-T1.tar` is left in `./data`.