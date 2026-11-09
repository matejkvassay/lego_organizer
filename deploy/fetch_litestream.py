"""Download a pinned Litestream release for this CPU architecture and verify its SHA-256 (used by the Dockerfile)."""
import hashlib
import io
import platform
import sys
import tarfile
import urllib.request

VERSION = "0.5.18"
SHA256 = {
    "x86_64": "d3687b9fd0f2e9426bbd3da828429ff3f1dfc5c9b74d54fdf028e4ee510e7dea",
    "arm64": "922a09e6a7ac67f2095571894dc6382e94e1dd4cdd9674883ddf1a8e74ab982d",
}

arch = {"x86_64": "x86_64", "amd64": "x86_64", "aarch64": "arm64", "arm64": "arm64"}[platform.machine()]
url = f"https://github.com/benbjohnson/litestream/releases/download/v{VERSION}/litestream-{VERSION}-linux-{arch}.tar.gz"
data = urllib.request.urlopen(url).read()
got = hashlib.sha256(data).hexdigest()
if got != SHA256[arch]:
    sys.exit(f"Litestream checksum mismatch for {arch}: expected {SHA256[arch]}, got {got}")
with tarfile.open(fileobj=io.BytesIO(data)) as tar:
    member = tar.getmember("litestream")
    open("/litestream", "wb").write(tar.extractfile(member).read())
