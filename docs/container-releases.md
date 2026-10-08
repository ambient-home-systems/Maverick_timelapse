# Container releases

GitHub Actions builds Maverick on native **amd64** and **arm64** runners and publishes images to **GitHub Container Registry (GHCR)**. The Home Assistant `aarch64` architecture uses the `arm64` image. There is no Docker Hub account or extra registry token to configure: publication uses the workflow's built-in `GITHUB_TOKEN`, with `packages: write` restricted to publishing jobs.

The release workflow runs app tests first, builds both images, checks their version/architecture labels, and renders a small H.264 video inside each published container. Only after both checks pass does it publish the combined version manifest. Version 0.1.4 introduced publicly downloadable images. `config.yaml` selects the released version:

```text
ghcr.io/ambient-home-systems/maverick_timelapse:0.1.4
```

Home Assistant uses the exact `config.yaml` version as the image tag. It does not use a moving `latest` tag. Cached dependency layers speed up subsequent GitHub builds; Home Assistant downloads and extracts prebuilt layers once the `image` setting is enabled.

## First publication

1. Push a `v0.1.4` tag on the commit with version `0.1.4`, or run **Actions → Publish app images → Run workflow** on that commit.
2. After the package first appears, open [the account's packages](https://github.com/ambient-home-systems?tab=packages), choose **maverick_timelapse**, and open **Package settings → Change visibility → Public**. GitHub creates new container packages as private even for a public source repository. Account policy must permit public packages and Actions package publication.
3. Wait for the release workflow to succeed. If its final anonymous-download check ran before the package was made public, rerun the failed job. The check fetches the version manifest without repository credentials and requires both supported architectures.
4. After that check succeeds, set this in `maverick_timelapse/config.yaml` and push it to `main`:

   ```yaml
   image: ghcr.io/ambient-home-systems/maverick_timelapse
   ```

For a new fork or registry target, keep the `image` setting absent until the published version is publicly downloadable. Otherwise Home Assistant installs/updates can fail because it cannot pull a private or missing image. Maverick's initial publication passed this check before enabling the setting.

Existing installations need no reinstall. Once the repository advertises the prebuilt image, refresh the app store and update Maverick. The existing `/data` directory, jobs, options, and videos remain in place. Downloads and extraction can still pause at 0% briefly; they no longer involve installing Python dependencies or FFmpeg on the Home Assistant host.

## Subsequent releases

1. Prepare a release branch with the next version in `config.yaml`, the Dockerfile's default `BUILD_VERSION`, and the interface version badge. Update the changelog and README examples.
2. Push the branch and its matching `vX.Y.Z` tag. The workflow rejects a tag that does not match `config.yaml`. Keep `main` advertising the previous published version while the new images build.
3. Wait for **Publish app images** to pass, including the anonymous check. Then merge the tested release into `main` so Home Assistant discovers it.

Do not reuse a released version for different application code. Use a new version for each release; rerunning a failed publication on the same commit is fine. Ordinary pull requests and branch pushes validate images without publishing them.

## Verify locally

```bash
python3 .github/scripts/verify-public-image.py ghcr.io/ambient-home-systems/maverick_timelapse 0.1.4
docker pull ghcr.io/ambient-home-systems/maverick_timelapse:0.1.4
```

The verification script requests an anonymous pull token and checks the combined manifest. It does not read credentials from the environment or Docker's login configuration.
