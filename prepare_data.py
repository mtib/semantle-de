"""
One-shot data preparation for the semantle-de container. Replaces the shell-
level wget/unzip/gzip dance so the runtime image can stay on plain
python:3.10-slim (no apt packages, ~20MB smaller).

On first boot this:
  1. streams cc.de.300.vec.gz from fasttext into data/cc.de.300.vec
  2. downloads German.zip from winedt.org and extracts de.dic
  3. invokes process_vecs.py to build data/valid_guesses.db and
     data/valid_nearest_mat.npy (+ valid_nearest_words.pkl)

The presence of valid_nearest_words.pkl is the "setup complete" marker — if it
exists we exit early and gunicorn boots immediately.
"""
import gzip
import os
import shutil
import ssl
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

DATA_DIR = Path('data')

VEC_URL = 'https://dl.fbaipublicfiles.com/fasttext/vectors-crawl/cc.de.300.vec.gz'
VEC_GZ = DATA_DIR / 'cc.de.300.vec.gz'
VEC_PATH = DATA_DIR / 'cc.de.300.vec'

DICT_URL = 'https://winedt.org/dict/German.zip'
DICT_ZIP = DATA_DIR / 'German.zip'
DICT_PATH = DATA_DIR / 'de.dic'

DONE_MARKER = DATA_DIR / 'valid_nearest_words.pkl'
DB_PATH = DATA_DIR / 'valid_guesses.db'
MAT_PATH = DATA_DIR / 'valid_nearest_mat.npy'


def _download(url: str, dest: Path, verify_tls: bool = True) -> None:
    print(f"downloading {url} -> {dest}")
    ctx = None if verify_tls else ssl._create_unverified_context()
    with urllib.request.urlopen(url, context=ctx) as resp, open(dest, 'wb') as out:
        shutil.copyfileobj(resp, out, length=1 << 20)


def ensure_vec() -> None:
    if VEC_PATH.exists():
        return
    if not VEC_GZ.exists():
        _download(VEC_URL, VEC_GZ)
    print("decompressing cc.de.300.vec.gz")
    with gzip.open(VEC_GZ, 'rb') as src, open(VEC_PATH, 'wb') as dst:
        shutil.copyfileobj(src, dst, length=1 << 20)
    VEC_GZ.unlink()


def ensure_dict() -> None:
    if DICT_PATH.exists():
        return
    if not DICT_ZIP.exists() or DICT_ZIP.stat().st_size == 0:
        # winedt.org currently serves with an expired TLS cert; skip verification.
        _download(DICT_URL, DICT_ZIP, verify_tls=False)
    print("extracting de.dic from German.zip")
    with zipfile.ZipFile(DICT_ZIP) as zf:
        zf.extractall(DATA_DIR)


def cleanup_partial() -> None:
    """Wipe half-written artifacts from an earlier crashed run so we start fresh."""
    for p in (DB_PATH, MAT_PATH, DATA_DIR / 'valid_guesses.db-journal',
              DATA_DIR / 'valid_nearest.dat'):
        if p.exists():
            print(f"removing partial {p}")
            p.unlink()


def main() -> int:
    if DONE_MARKER.exists() and DB_PATH.exists() and MAT_PATH.exists():
        print("data already prepared, skipping")
        return 0

    print(">>> initial data setup starting (this takes a while)...")
    DATA_DIR.mkdir(exist_ok=True)
    ensure_vec()
    ensure_dict()
    cleanup_partial()

    print(">>> running process_vecs.py")
    rc = subprocess.call([sys.executable, 'process_vecs.py'])
    if rc != 0:
        print(f"process_vecs.py exited {rc}", file=sys.stderr)
        return rc

    # Reclaim the ~4.5GB raw vec dump — it's only needed for the one-time
    # processing pass. Keeping it around bloats the volume with no runtime use.
    for p in (VEC_PATH, VEC_GZ, DICT_ZIP):
        if p.exists():
            print(f"cleaning up {p.name} ({p.stat().st_size // (1 << 20)}MB)")
            p.unlink()

    print(">>> data setup complete")
    return 0


if __name__ == '__main__':
    sys.exit(main())
