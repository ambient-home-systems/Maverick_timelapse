# Maverick Timelapse

Version 0.1.4 and later download prebuilt containers from GitHub Container Registry for amd64 and aarch64. Updates preserve existing jobs and videos. Home Assistant may briefly show 0% while downloading or extracting layers; check the Supervisor logs for progress.

Use **Open Web UI** to create a recording from an existing Home Assistant camera entity. Choose a snapshot interval and duration, then select **Start now** (the default) or **Schedule for later**. Scheduled recordings use separate date and time controls; your browser’s timezone is shown below them.

The app automatically authenticates through Home Assistant Supervisor. No camera passwords or access tokens are needed in its configuration.

## Capture presets

Start with daytime landscape **10s**, quiet nighttime landscape **30s**, stars/astronomy **30s**, clouds/sky **5s**, sunrise/sunset **5s**, or all-day landscape **60s**. These are starting points for different motion speeds, not automatic camera settings.

A preset changes only the snapshot interval. You can edit the number at any time to select Custom; selecting Custom preserves the number. Faster capture preserves more motion and uses more storage. Recording duration, output FPS, and existing jobs are unchanged.

Night and astronomy presets do not change exposure, camera night mode, or image quality. The camera must already show stars in its snapshots. Match the interval to the camera's actual image update cycle; a camera updating once a minute cannot deliver new images every 5 seconds. Very fast clouds and brief astronomical events may need capture methods beyond this app's 5-second minimum.

Research and tuning: https://github.com/ambient-home-systems/Maverick_timelapse/blob/main/docs/capture-intervals.md

## Finished video FPS

FPS is the number of captured snapshots shown per second in the finished MP4. It does not need to match your camera's video FPS. Choose **30 FPS** as a starting point. With the same snapshots, 24 FPS produces a longer, slower video; 60 FPS produces a shorter, faster video. For example, 900 snapshots make a 30-second video at 30 FPS or a 15-second video at 60 FPS.

The snapshot interval controls how often images are captured. Changing finished video FPS does not capture more images or increase their resolution. The form estimates the finished duration as you change these settings.

## Options

- **max_storage_gb** (default 10): total storage budget in GiB. This must leave room for both snapshots and rendered videos. Delete older completed or failed jobs when the limit is reached. No automatic deletion occurs.
- **keep_snapshots** (default false): retain source images after video creation. Source images from failed jobs are always retained so video creation can be retried.

Restart the app after changing its configuration. Files live in persistent app storage; download videos before uninstalling. Include the app in Home Assistant backups to preserve its data.

## Recording

Check the latest snapshot to confirm your camera returns fresh images. Battery-powered or unavailable cameras may miss captures. Each missed capture is counted; the app tries again at the next interval. Missed frames are omitted from the finished video.

**Finish video now** ends capture early and renders saved snapshots. **Retry video** is available for failed jobs with saved frames. Delete removes a finished/failed job and its files permanently. Recordings without snapshots cannot create a video.

Jobs survive restarts. Active recordings resume within their original window; expired recordings and interrupted renders create a video from saved frames. Missed intervals are not replayed.

This initial release supports one-time schedules, not recurring or sunrise/sunset schedules. Videos use H.264 MP4 at 1080p with image proportions preserved.

Full installation, compatibility, troubleshooting, and development documentation: https://github.com/ambient-home-systems/Maverick_timelapse
