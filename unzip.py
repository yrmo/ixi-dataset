from pathlib import Path
import gzip
import shutil
import tarfile

data_dir = Path("data")
archive = data_dir / "IXI-T1.tar"
out_dir = data_dir / "IXI-T1"

if not archive.is_file():
    raise FileNotFoundError(f"put IXI-T1.tar in {data_dir}")

out_dir.mkdir(parents=True, exist_ok=True)


def archive_filename(member_name: str) -> str:
    """Keep only the file name so nested tar paths land in one folder."""
    filename = member_name.replace("\\", "/").rstrip("/").split("/")[-1]
    if filename in ("", ".", ".."):
        raise ValueError(f"refusing tar member {member_name!r}")
    return filename


with tarfile.open(archive, "r:*") as tar:
    for member in tar.getmembers():
        if not member.isreg():
            continue
        filename = archive_filename(member.name)
        if not filename.endswith(".nii.gz"):
            continue
        source = tar.extractfile(member)
        if source is None:
            raise RuntimeError(f"could not read {member.name}")
        with source, (out_dir / filename).open("wb") as dest:
            shutil.copyfileobj(source, dest)

gzip_paths = list(out_dir.rglob("*.nii.gz"))
destinations = {}
for gzip_path in gzip_paths:
    nii_name = Path(gzip_path.name).with_suffix("").name  # ".nii.gz" -> ".nii"
    destinations.setdefault(nii_name, []).append(gzip_path)

collisions = {name: paths for name, paths in destinations.items() if len(paths) > 1}
if collisions:
    raise FileExistsError(f"more than one volume would be named {sorted(collisions)}")

for nii_name, paths in destinations.items():
    gzip_path = paths[0]
    with gzip.open(gzip_path, "rb") as source, (out_dir / nii_name).open("wb") as dest:
        shutil.copyfileobj(source, dest)
    gzip_path.unlink()

for directory in sorted(out_dir.rglob("*"), reverse=True):
    if directory.is_dir() and not any(directory.iterdir()):
        directory.rmdir()

print(f"wrote {len(list(out_dir.glob('*.nii')))} volumes to {out_dir}")
