"""One-shot in-memory dependency installer for the remaining C-extension packages.

Downloads each wheel fully into memory (BytesIO) and extracts with zipfile,
avoiding both pip's tempfile usage and the cross-process file-sync issue that
truncated large wheels on disk in this sandbox.
"""
import io
import json
import os
import shutil
import sys
import urllib.request
import zipfile

TARGET = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".py-deps")

# package -> import-name hint (not strictly needed here)
PACKAGES = [
    "joblib",
    "threadpoolctl",
    "scikit-learn",
    "pandas",
    "python-dateutil",
    "pytz",
    "tzdata",
    "narwhals",
    "six",
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


def install(name: str) -> str:
    meta_url = f"https://pypi.org/pypi/{name}/json"
    with urllib.request.urlopen(meta_url, timeout=30) as resp:
        data = json.load(resp)
    version = data["info"]["version"]
    wheel = pick_wheel(data["releases"].get(version, []))
    if wheel is None:
        return f"{name}: NO WHEEL"
    pkg_dir = os.path.join(TARGET, wheel["filename"].split("-")[0].replace("_", "-"))
    if os.path.isdir(pkg_dir):
        return f"{name}: already present"
    buf = io.BytesIO()
    req = urllib.request.Request(wheel["url"], headers={"User-Agent": "finsignal/1.0"})
    with urllib.request.urlopen(req, timeout=900) as resp:
        while True:
            c = resp.read(262144)
            if not c:
                break
            buf.write(c)
    buf.seek(0)
    if buf.getbuffer().nbytes != wheel["size"]:
        return f"{name}: SIZE MISMATCH {buf.getbuffer().nbytes} != {wheel['size']}"
    with zipfile.ZipFile(buf) as zf:
        zf.extractall(TARGET)
    return f"{name}: installed {version}"


def main() -> int:
    os.makedirs(TARGET, exist_ok=True)
    for name in PACKAGES:
        print(install(name), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
