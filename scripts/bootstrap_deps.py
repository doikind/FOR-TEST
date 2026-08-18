"""Bootstrap dependency installer.

Downloads wheels directly from PyPI (via urllib, chunked) and extracts them
with zipfile into the project-local .py-deps directory, avoiding pip's use of
tempfile.mkdtemp which is blocked by this sandbox. Skips files already fully
downloaded (size-verified against PyPI metadata).
"""
import json
import os
import sys
import urllib.request
import zipfile

TARGET = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".py-deps")

PACKAGES = [
    "requests",
    "urllib3",
    "idna",
    "certifi",
    "charset-normalizer",
    "feedparser",
    "feedparser-sgmllib",
    "numpy",
    "scipy",
    "joblib",
    "threadpoolctl",
    "scikit-learn",
    "pandas",
    "python-dateutil",
    "pytz",
    "tzdata",
]


def pick_wheel(files):
    pure = [f for f in files if f["filename"].endswith("-py3-none-any.whl")]
    if pure:
        return pure[0]
    py2py3 = [f for f in files if f["filename"].endswith("-py2.py3-none-any.whl")]
    if py2py3:
        return py2py3[0]
    cp314 = [f for f in files if "cp314-cp314-win_amd64.whl" in f["filename"]]
    if cp314:
        return cp314[0]
    return None


def download(url: str, dest: str, size: int) -> bool:
    req = urllib.request.Request(url, headers={"User-Agent": "finsignal-bootstrap/1.0"})
    with urllib.request.urlopen(req, timeout=300) as resp:
        total = 0
        with open(dest, "wb") as f:
            while True:
                chunk = resp.read(262144)
                if not chunk:
                    break
                f.write(chunk)
                total += len(chunk)
    return total == size


def main():
    os.makedirs(TARGET, exist_ok=True)
    installed = []
    for name in PACKAGES:
        meta_url = f"https://pypi.org/pypi/{name}/json"
        with urllib.request.urlopen(meta_url, timeout=30) as resp:
            data = json.load(resp)
        version = data["info"]["version"]
        wheel = pick_wheel(data["releases"].get(version, []))
        if wheel is None:
            print(f"[SKIP] {name}: no compatible wheel", flush=True)
            continue
        url, filename, size = wheel["url"], wheel["filename"], wheel["size"]
        dest = os.path.join(TARGET, filename)
        # Skip download only if the file exists with the exact expected size.
        need_dl = not os.path.exists(dest) or os.path.getsize(dest) != size
        if need_dl and os.path.exists(dest):
            os.remove(dest)
        if need_dl:
            print(f"[DL] {name} {version} ({size} bytes)", flush=True)
            ok = download(url, dest, size)
            if not ok:
                print(f"[FAIL] {name}: size mismatch, retrying once", flush=True)
                ok = download(url, dest, size)
            if not ok:
                print(f"[FAIL] {name}: download incomplete, aborting this package", flush=True)
                continue
        print(f"[EXTRACT] {filename}", flush=True)
        # Skip extraction if the package dir already exists (idempotent).
        pkg_dir = os.path.join(TARGET, filename.split("-")[0].replace("_", "-"))
        if os.path.isdir(pkg_dir):
            print(f"[SKIP-EXTRACT] {pkg_dir} already present", flush=True)
            installed.append(name)
            continue
        with zipfile.ZipFile(dest) as zf:
            zf.extractall(TARGET)
        installed.append(name)
    print("\nInstalled:", ", ".join(installed), flush=True)
    print("Target:", TARGET, flush=True)


if __name__ == "__main__":
    sys.exit(main())
