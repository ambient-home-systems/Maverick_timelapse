"""Check the exact release manifest without using GitHub credentials."""
import json
import sys
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def verify(image, version):
    if not image.startswith("ghcr.io/"):
        raise ValueError("Expected a ghcr.io image")
    repository = image.removeprefix("ghcr.io/")
    query = urlencode({"service": "ghcr.io", "scope": f"repository:{repository}:pull"})
    try:
        with urlopen(f"https://ghcr.io/token?{query}", timeout=30) as response:
            token = json.load(response)["token"]
        request = Request(
            f"https://ghcr.io/v2/{repository}/manifests/{version}",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.oci.image.index.v1+json, application/vnd.docker.distribution.manifest.list.v2+json",
            },
        )
        with urlopen(request, timeout=30) as response:
            manifest = json.load(response)
    except HTTPError as error:
        raise SystemExit(
            f"Anonymous download failed (HTTP {error.code}). In the GitHub package settings, "
            "set maverick_timelapse visibility to Public, then rerun this job. "
            "Keep config.yaml on local builds until this check passes."
        ) from None
    platforms = {
        (item.get("platform", {}).get("os"), item.get("platform", {}).get("architecture"))
        for item in manifest.get("manifests", [])
    }
    if not {("linux", "amd64"), ("linux", "arm64")} <= platforms:
        raise SystemExit(f"Release manifest is missing a supported architecture: {platforms}")
    print(f"Anonymous downloads verified: {image}:{version} (amd64 and arm64).")


if __name__ == "__main__":
    verify(*sys.argv[1:])
