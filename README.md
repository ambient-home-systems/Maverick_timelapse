# Maverick Timelapse

Create timelapse videos from cameras already integrated into Home Assistant. Choose a camera, snapshot interval, recording duration, and start time. Maverick captures snapshots and turns them into a downloadable MP4.

**For Home Assistant OS.** This repository is a custom app repository (formerly called an add-on repository). Version 0.1.3 is an early release; test a short recording on your camera before scheduling a long one.

[![Click here to add to Home Assistant](https://img.shields.io/badge/Click%20here%20to%20add%20to-Home%20Assistant-41BDF5?style=for-the-badge&logo=homeassistant&logoColor=white)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Fambient-home-systems%2FMaverick_timelapse)

## Install

1. Click the button above and confirm adding this repository in Home Assistant.
2. Open **Settings → Apps → App store** (older versions: **Settings → Add-ons → Add-on store**), refresh/check for updates if needed, and find **Maverick Timelapse**.
3. Install the app. The first installation builds its container locally and can take several minutes.
4. Review its configuration, start it, and select **Open Web UI**. Enable **Show in sidebar** for quick access.

If the button does not work, open the store’s **Repositories** menu and add:

```text
https://github.com/ambient-home-systems/Maverick_timelapse
```

Supported architectures: **amd64** and **aarch64**. A 64-bit Raspberry Pi OS installation is supported; 32-bit ARM installations are not supported in this first version. Home Assistant Container/Core installations do not have the app store.

## Make your first timelapse

1. Confirm that your camera shows an image in Home Assistant. For Reolink, add the camera through Home Assistant’s Reolink integration first.
2. Open Maverick, name the recording, and choose a camera.
3. Choose a **Capture preset** or enter a custom snapshot interval, then set the recording duration. Choose **Start now** (the default) to begin immediately, or **Schedule for later** and select a future date and time. The timezone is shown below the date and time controls.
4. Select **Create timelapse**. Check the latest snapshot and failed-capture count while recording.
5. When the recording ends, Maverick renders the video. Select **Watch** or **Download MP4** when it completes. **Finish video now** ends a recording early and renders the frames already captured.

Example: one snapshot every **30 seconds** over **8 hours**, played at **30 fps**, produces approximately **960 frames** and a **32-second video**. Missed captures reduce the frame count and video duration.

### Which snapshot interval should I use?

Choose one of the built-in starting presets:

| Scene | Snapshot every | Why |
| --- | --- | --- |
| Daytime landscape (interface default) | **10 seconds** | Balanced capture of scenery, changing light, and gentle motion. |
| Quiet nighttime landscape | **30 seconds** | Slow changes across several hours; use 5–10s for traffic or clouds. |
| Stars / astronomy | **30 seconds** | Gradual star motion, provided the camera already shows stars; match its actual image-refresh/exposure cycle. |
| Clouds / sky | **5 seconds** | More frames for cloud motion; try 10s for slow clouds. |
| Sunrise / sunset | **5 seconds** | Changing light and moving clouds; scheduling remains manual. |
| Landscape over a whole day | **60 seconds** | Slow changes over many hours with fewer saved images. |

Presets change **only** the interval. The number stays editable: editing it selects **Custom interval**, and choosing Custom preserves your value. Recording duration and finished video FPS are left as you set them. Custom intervals range from 5 to 86,400 seconds. Existing recordings keep their intervals.

There is no universal ideal value. Shorter intervals preserve motion but use more storage. Longer intervals skip more changes. **Waiting longer between snapshots does not lengthen exposure or brighten nighttime images.** The camera must already capture stars; this app does not enable long exposure or create stacked/star-trail images. Start with a short test and check for fresh images.

The defaults are Maverick's practical choices informed by GoPro Labs and Allsky documentation. See [capture interval research and sources](docs/capture-intervals.md) for tuning advice, exposure/cadence distinctions, example calculations, and research limitations.

### What does finished video FPS do?

FPS means frames per second in the **finished MP4**. Each captured snapshot becomes one video frame. This setting does **not** need to match your camera's video FPS; Maverick captures still images rather than recording the camera stream.

Start with **30 FPS**, the recommended default. For the same 900 snapshots:

| Finished video FPS | Video duration | Playback |
| --- | --- | --- |
| 24 | 37.5 seconds | Slower |
| 30 | 30 seconds | Recommended starting point |
| 60 | 15 seconds | Faster |

The snapshot interval controls how often pictures are captured. FPS controls how quickly those pictures play back. Increasing FPS does not capture more images or increase resolution. The form estimates the finished video duration as you change either setting.

## Features

- Camera discovery through Home Assistant, without separate camera credentials.
- Scene presets for capture intervals, with explanations and editable custom values.
- Immediate or future, one-time recordings, with up to eight active jobs.
- Snapshot intervals of 5 seconds or longer; recordings up to 30 days and 100,000 planned frames.
- Persistent schedules and recovery after an app restart. Missed intervals are skipped rather than captured in a burst.
- Latest snapshot, capture-error count, recording progress, and completed-video gallery.
- H.264 MP4 output at 1920 × 1080, preserving image proportions with padding, at 1–60 fps (the interface offers 24, 30, and 60 fps).
- One video renders at a time, with bounded encoder threads.
- Retry video creation after a rendering or storage failure; delete finished or failed jobs and their files.
- Home Assistant ingress access; no public listening port is exposed by the app configuration.

Recurring daily schedules, sunrise/sunset schedules, notifications, automatic age-based deletion, and a companion integration for entities/automations are planned follow-ups. They are not included in this release.

## Configuration and storage

| Option | Default | Meaning |
| --- | --- | --- |
| `max_storage_gb` | `10` | Combined storage budget for jobs, snapshots, videos, and the job database, in GiB. |
| `keep_snapshots` | `false` | Keep source JPEGs after successful video creation. Failed jobs always retain their snapshots for retry. |

Files are stored in the app’s persistent `/data` directory. Restart the app after changing options. Download videos before uninstalling the app. Include the app in Home Assistant backups if you want its jobs and videos backed up.

The app pauses during backups to keep the job database and snapshots consistent, then resumes its existing schedules. Intervals missed during a backup are skipped.

Maverick reserves at least 256 MiB of filesystem free space and stops capture/rendering when its storage budget is exhausted. Rendering needs room for both source images and the MP4. The budget is monitored, rather than enforced as a filesystem quota, so concurrent writes can briefly exceed it. It does **not** automatically delete videos. Download and delete older jobs, or raise the budget if your system has sufficient space. **Retry video** uses retained frames; it does not resume an expired recording.

## Camera compatibility

Maverick requests still images from Home Assistant’s camera API. It does not record RTSP streams or connect directly to Reolink devices. Compatibility depends on the camera entity’s ability to provide a usable still image. Camera integrations may cache images; identical frames can also be a legitimate static scene, so Maverick does not discard duplicates or claim to detect stale images.

Battery cameras may sleep or provide images less often than the requested interval. Test your actual camera first. Failed snapshots are counted and retried at the next scheduled interval; gaps are omitted from the video. Once a job has saved a frame, its latest image is shown until successful rendering removes snapshots, unless `keep_snapshots` is enabled.

## Troubleshooting

- **No cameras:** add a camera integration in Home Assistant, check its entity, then select **Refresh cameras**.
- **HTTP 401/403:** check the app log and Home Assistant API access. The app normally receives authentication automatically from Supervisor; do not enter Reolink credentials or a Home Assistant token in app options.
- **Unavailable camera or repeated timeouts:** check the camera in Home Assistant and try a longer interval.
- **Failed video:** resolve the storage/FFmpeg issue shown by the job and select **Retry video**. A job with no captured frames cannot generate a video.
- **After a restart:** capture resumes only within the original recording window; an expired recording renders its saved frames. An interrupted render restarts from those frames.

## Development

Python 3.12+, FFmpeg with the `libx264` encoder, and ffprobe are required. Each cloud task already has an isolated workspace; use the existing checkout without creating a Git worktree.

From the repository root:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
PYTHONPATH=maverick_timelapse .venv/bin/python -m unittest discover -s tests -v
node --check maverick_timelapse/app/static/app.js
TZ=America/New_York node --test tests/test_schedule.mjs
docker build -t maverick-timelapse:0.1.3 maverick_timelapse
```

The Dockerfile pins a multi-architecture base-image digest and includes the app labels required by current Supervisor versions. For networks using a trusted TLS inspection proxy, an optional build-only CA bundle can be supplied with `docker build --secret id=build_ca,src=/path/to/trusted-ca-bundle.pem -t maverick-timelapse:0.1.3 maverick_timelapse`. Certificate verification remains enabled; the bundle is not stored in the image.

For local development against a Home Assistant instance, set `HA_API_URL` to its API base (for example, `http://homeassistant.local:8123/api`) and supply a long-lived access token as `HA_TOKEN` through your local environment. Never commit or print tokens. The production app uses `SUPERVISOR_TOKEN` automatically.

```bash
export MAVERICK_DEV=1
export MAVERICK_DATA_DIR="$PWD/.local-data"
PYTHONPATH=maverick_timelapse .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8099
```

Development mode allows loopback requests. Bind to `127.0.0.1`; keep development mode disabled in Home Assistant. The `/health` route checks the scheduler and returns HTTP 200 when ready. Open the local interface to check camera discovery and capture; health alone does not establish camera compatibility.

The automated tests exercise the Home Assistant HTTP adapter, capture failures, restart recovery, storage limits, ingress restrictions, and actual FFmpeg rendering. GitHub Actions also builds the app image for both supported architectures. Testing on a real Home Assistant OS system and your Reolink models remains necessary before treating the release as production-ready.

## License

MIT. See [LICENSE](LICENSE).
