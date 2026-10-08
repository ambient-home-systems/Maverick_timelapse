# Changelog

## 0.1.7

- Use release-specific URLs for styles, JavaScript, and imported modules so cached assets from earlier versions do not retain the old dialog layout.
- Disable caching for the interface document and assets, and derive the displayed version from the app release.
- Keep asset routes available for previously opened interfaces.

## 0.1.6

- Center the New timelapse dialog on desktop and widen it from 460px to 640px.
- Keep the full-screen phone layout and scrollable settings with fixed action buttons.

## 0.1.5

- Redesign the interface with Material-style controls, a compact toolbar, and automatic light/dark appearance.
- Make the timelapse library the main screen, with recording/video filters and camera/video previews.
- Move creation into a focused side panel that fills the screen on phones.
- Keep setting guidance available beside presets and FPS controls, and show form errors within the panel.
- Show friendly camera names, preserve expanded recording details, and update recording progress between captures.

## 0.1.4

- Build and publish versioned amd64/aarch64 container images in GitHub Actions, with native architecture checks and a combined manifest.
- Use publicly downloadable prebuilt images for Home Assistant installs and updates.
- Cache dependency layers and keep version labels after dependency installation.
- Check anonymous registry access before switching Home Assistant to prebuilt images.

## 0.1.3

- Add explained capture presets for daytime/nighttime landscapes, stars, clouds, sunrise/sunset, and all-day views.
- Allow custom intervals without losing the entered value or changing duration/FPS.
- Show each job's capture interval and document the research, tuning, and astronomy limitations.

## 0.1.2

- Explain finished video FPS, recommended settings, and how it differs from the snapshot interval and camera FPS.
- Include the selected output FPS in the finished-video duration estimate.

## 0.1.1

- Add an explicit Start now option, selected by default.
- Replace the combined start-time picker with separate date and time controls for browser compatibility.
- Show the scheduling timezone and actionable errors for incomplete, past, and nonexistent times.
- Correct the README button for adding the repository to Home Assistant.

## 0.1.0

- Initial Home Assistant OS app for scheduled camera timelapses.
- Persistent jobs, snapshot previews, capture-error reporting, and restart recovery.
- H.264 MP4 rendering, playback, downloads, and video retries.
- Configurable storage budget and source-image retention.
- Home Assistant ingress interface for amd64 and aarch64.
