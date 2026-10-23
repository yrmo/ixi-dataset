"""Skull-strip every IXI T1 with FreeSurfer SynthStrip and store brain volume.

Run from anywhere:

    python process.py

Stripped images go to data/brains/. Volumes go to results/volumes.csv.
Subjects already recorded with status ok are skipped.
"""

import argparse
import csv
import os
import re
import shlex
import subprocess
import tempfile
import threading
import time
from pathlib import Path

from nibabel_volume import measure

ROOT = Path(__file__).resolve().parent
SOURCE_DIR = ROOT / "data" / "IXI-T1"
BRAIN_DIR = ROOT / "data" / "brains"
RESULTS = ROOT / "results" / "volumes.csv"
STATUS = ROOT / "results" / "process.status"

# 2 jobs x 2 threads matched the 4 CPUs this WSL instance exposes.
DEFAULT_WORKERS = 2
DEFAULT_THREADS = 2

COLUMNS = [
    "subject",
    "ixi_id",
    "site",
    "source",
    "brain",
    "voxels",
    "voxel_mm3",
    "volume_ml",
    "status",
    "error",
]

SUBJECT_RE = re.compile(r"(IXI\d+)-([A-Za-z]+)-\d+-T1$")

# Each finished scan renames its image into place, or writes a sibling .fail file.
# Polling those files avoids depending on WSL stdout being flushed line by line.
BATCH = r"""#!/bin/bash
setup="$1"
threads="$2"
workers="$3"
list="$4"
export FREESURFER_HOME="$(cd "$(dirname "$setup")" && pwd)"
source "$setup" >/dev/null
running=0
while IFS=$'\t' read -r src dest; do
  [ -n "${src:-}" ] || continue
  while [ "$running" -ge "$workers" ]; do
    wait -n || true
    running=$((running - 1))
  done
  (
    log=$(mktemp)
    fail="${dest}.fail"
    ok="${dest}.ok"
    rm -f "$fail" "$ok" "$dest"
    if mri_synthstrip -t "$threads" -i "$src" -o "$dest" >"$log" 2>&1; then
      printf 'ok\n' > "$ok"
    else
      msg=$(tail -c 400 "$log" | tr '\n\t' '  ')
      printf '%s\n' "$msg" > "$fail"
      rm -f "$dest"
    fi
    rm -f "$log"
  ) &
  running=$((running + 1))
done < "$list"
wait || true
"""


def freesurfer_home() -> str:
    text = (ROOT / "freesurfer.sh").read_text(encoding="utf-8")
    match = re.search(r"^export FREESURFER_HOME=(\S+)", text, re.M)
    if not match:
        raise SystemExit("freesurfer.sh does not set FREESURFER_HOME")
    return match.group(1)


def to_wsl(path: Path) -> str:
    resolved = path.resolve()
    drive = resolved.drive[0].lower()
    tail = resolved.as_posix().split(":", 1)[1]
    return f"/mnt/{drive}{tail}"


def parse_subject(subject: str) -> tuple[str, str]:
    match = SUBJECT_RE.search(subject)
    if not match:
        return "", ""
    return match.group(1), match.group(2)


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def load_rows(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    with path.open(newline="", encoding="utf-8") as handle:
        return {row["subject"]: row for row in csv.DictReader(handle)}


def save_rows(path: Path, rows: dict[str, dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS, lineterminator="\n")
        writer.writeheader()
        for subject in sorted(rows):
            writer.writerow(rows[subject])
    os.replace(temporary, path)


def write_status(**fields: object) -> None:
    STATUS.parent.mkdir(parents=True, exist_ok=True)
    temporary = STATUS.with_suffix(".status.tmp")
    lines = [f"{key}={value}" for key, value in fields.items()]
    temporary.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.replace(temporary, STATUS)


def check_synthstrip(home: str) -> None:
    binary = f"{home}/bin/mri_synthstrip"
    script = f"test -x {shlex.quote(binary)}"
    proc = subprocess.run(
        ["wsl", "-e", "bash", "-lc", script],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()
        raise SystemExit(f"mri_synthstrip is not executable in WSL at {binary}. {detail}")


def row_for(src: Path, brain: Path, voxels: int, voxel_mm3: float, ml: float) -> dict:
    subject = src.stem
    ixi_id, site = parse_subject(subject)
    return {
        "subject": subject,
        "ixi_id": ixi_id,
        "site": site,
        "source": src.name,
        "brain": rel(brain),
        "voxels": str(voxels),
        "voxel_mm3": f"{voxel_mm3:.6f}",
        "volume_ml": f"{ml:.3f}",
        "status": "ok",
        "error": "",
    }


def error_row(src: Path, message: str) -> dict:
    subject = src.stem
    ixi_id, site = parse_subject(subject)
    return {
        "subject": subject,
        "ixi_id": ixi_id,
        "site": site,
        "source": src.name,
        "brain": "",
        "voxels": "",
        "voxel_mm3": "",
        "volume_ml": "",
        "status": "error",
        "error": message.replace("\n", " ")[:500],
    }


def try_measure(brain: Path):
    voxels, voxel_mm3, ml = measure(brain)
    if voxels == 0:
        raise RuntimeError("stripped image has no nonzero voxels")
    return voxels, voxel_mm3, ml


def record(rows: dict[str, dict], src: Path, brain: Path) -> str:
    voxels, voxel_mm3, ml = try_measure(brain)
    rows[src.stem] = row_for(src, brain, voxels, voxel_mm3, ml)
    save_rows(RESULTS, rows)
    return f"{ml:.1f} ml"


class Progress:
    def __init__(self, total: int, already_ok: int):
        self.total = total
        self.done = already_ok
        self.ok = already_ok
        self.error = 0
        self.worked = 0
        self.started = time.time()

    def tick(self, subject: str, summary: str, ok: bool) -> None:
        self.done += 1
        self.worked += 1
        if ok:
            self.ok += 1
        else:
            self.error += 1
        elapsed = max(time.time() - self.started, 1e-6)
        remaining = (self.total - self.done) * (elapsed / self.worked)
        print(
            f"[{self.done}/{self.total}] {subject} {summary}  eta {format_eta(remaining)}",
            flush=True,
        )
        write_status(
            state="running",
            done=self.done,
            total=self.total,
            ok=self.ok,
            error=self.error,
            last=subject,
        )


def format_eta(seconds: float) -> str:
    seconds = int(max(seconds, 0))
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


def brain_path(src: Path) -> Path:
    return BRAIN_DIR / f"{src.stem}_brain.nii.gz"


def run_batch(
    pending: list[Path],
    home: str,
    workers: int,
    threads: int,
    rows: dict[str, dict],
    progress: Progress,
) -> None:
    BRAIN_DIR.mkdir(parents=True, exist_ok=True)
    by_dest: dict[str, Path] = {}
    with tempfile.NamedTemporaryFile(
        "w", delete=False, suffix=".tsv", encoding="utf-8", newline="\n"
    ) as handle:
        for src in pending:
            dest = brain_path(src)
            dest_wsl = to_wsl(dest)
            by_dest[dest_wsl] = src
            handle.write(f"{to_wsl(src)}\t{dest_wsl}\n")
        list_path = Path(handle.name)
    script_path = list_path.with_suffix(".sh")
    script_path.write_text(BATCH, encoding="utf-8", newline="\n")

    command = [
        "wsl",
        "-e",
        "bash",
        to_wsl(script_path),
        f"{home}/SetUpFreeSurfer.sh",
        str(threads),
        str(workers),
        to_wsl(list_path),
    ]
    proc = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert proc.stdout is not None and proc.stderr is not None
    stderr_box: list[str] = []

    def drain(pipe, box: list[str]) -> None:
        box.append(pipe.read())

    drainers = [
        threading.Thread(target=drain, args=(proc.stdout, []), daemon=True),
        threading.Thread(target=drain, args=(proc.stderr, stderr_box), daemon=True),
    ]
    for drainer in drainers:
        drainer.start()

    pending_dests = dict(by_dest)
    try:
        while pending_dests:
            collect(pending_dests, rows, progress)
            if proc.poll() is not None:
                collect(pending_dests, rows, progress)
                break
            time.sleep(2)
    finally:
        returncode = proc.wait()
        for drainer in drainers:
            drainer.join()
        list_path.unlink(missing_ok=True)
        script_path.unlink(missing_ok=True)

    detail = "".join(stderr_box).strip().replace("\n", " ")[-500:]
    for src in list(pending_dests.values()):
        Path(str(brain_path(src)) + ".fail").unlink(missing_ok=True)
        Path(str(brain_path(src)) + ".ok").unlink(missing_ok=True)
        rows[src.stem] = error_row(src, detail or f"synthstrip batch exited {returncode}")
        save_rows(RESULTS, rows)
        progress.tick(src.stem, "ERROR no synthstrip result", False)


def collect(pending_dests: dict[str, Path], rows: dict[str, dict], progress: Progress) -> None:
    for dest_wsl, src in list(pending_dests.items()):
        brain = brain_path(src)
        fail = Path(str(brain) + ".fail")
        done = Path(str(brain) + ".ok")
        if fail.exists():
            message = fail.read_text(encoding="utf-8", errors="replace").strip() or "mri_synthstrip failed"
            fail.unlink(missing_ok=True)
            brain.unlink(missing_ok=True)
            rows[src.stem] = error_row(src, message)
            save_rows(RESULTS, rows)
            progress.tick(src.stem, f"ERROR {message}", False)
            del pending_dests[dest_wsl]
            continue
        if done.exists() and brain.exists():
            try:
                summary = record(rows, src, brain)
                ok = True
            except Exception as exc:
                brain.unlink(missing_ok=True)
                rows[src.stem] = error_row(src, f"volume calc failed: {exc}")
                save_rows(RESULTS, rows)
                summary = f"ERROR {exc}"
                ok = False
            done.unlink(missing_ok=True)
            progress.tick(src.stem, summary, ok)
            del pending_dests[dest_wsl]


def summarise(rows: dict[str, dict], subjects: list[str]) -> None:
    chosen = [rows[subject] for subject in subjects if subject in rows]
    ok = [row for row in chosen if row["status"] == "ok"]
    error = [row for row in chosen if row["status"] == "error"]
    print(f"ok {len(ok)}  error {len(error)}", flush=True)
    by_site: dict[str, list[float]] = {}
    for row in ok:
        by_site.setdefault(row["site"] or "?", []).append(float(row["volume_ml"]))
    for site in sorted(by_site):
        values = by_site[site]
        mean = sum(values) / len(values)
        print(f"{site}  n={len(values)}  mean={mean:.1f} ml", flush=True)
    print(f"wrote {rel(RESULTS)}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=0, help="Process only the first N scans. 0 means all.")
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    parser.add_argument("--threads", type=int, default=DEFAULT_THREADS)
    args = parser.parse_args()
    if args.workers < 1 or args.threads < 1:
        raise SystemExit("--workers and --threads must be at least 1")

    sources = sorted(SOURCE_DIR.glob("*.nii"))
    if not sources:
        raise SystemExit(f"no .nii files in {SOURCE_DIR}. Run unzip.py first.")
    if args.limit:
        sources = sources[: args.limit]

    home = freesurfer_home()
    check_synthstrip(home)
    rows = load_rows(RESULTS)
    wanted = [src.stem for src in sources]
    pending: list[Path] = []
    skipped = 0
    reused = 0
    for src in sources:
        if rows.get(src.stem, {}).get("status") == "ok":
            skipped += 1
            continue
        brain = brain_path(src)
        if brain.exists() and not Path(str(brain) + ".fail").exists():
            try:
                record(rows, src, brain)
            except Exception:
                brain.unlink(missing_ok=True)
            else:
                reused += 1
                continue
        pending.append(src)

    print(
        f"{len(sources)} scans, {skipped} already done, {reused} measured from existing brains, "
        f"{len(pending)} to skull-strip ({args.workers} workers, {args.threads} threads)",
        flush=True,
    )
    progress = Progress(len(sources), skipped + reused)
    write_status(
        state="running",
        done=progress.done,
        total=progress.total,
        ok=progress.ok,
        error=progress.error,
        last="",
    )
    if pending:
        run_batch(pending, home, args.workers, args.threads, rows, progress)

    summarise(rows, wanted)
    ok = sum(1 for subject in wanted if rows.get(subject, {}).get("status") == "ok")
    error = sum(1 for subject in wanted if rows.get(subject, {}).get("status") == "error")
    state = "done" if error == 0 and ok == len(sources) else "error"
    write_status(state=state, done=ok + error, total=len(sources), ok=ok, error=error, last="")
    if state != "done":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
