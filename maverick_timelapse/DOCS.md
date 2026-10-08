# Maverick Timelapse

Use **Open Web UI** to create a recording from an existing Home Assistant camera entity. Choose a snapshot interval, duration, and optional future start time. The start-time picker uses your browser’s timezone.

The app automatically authenticates through Home Assistant Supervisor. No camera passwords or access tokens are needed in its configuration.

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
