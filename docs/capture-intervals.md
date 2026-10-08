# Choosing snapshot intervals

Research reviewed on October 8, 2026. The defaults below are Maverick's practical starting points for Home Assistant camera snapshots. They are product choices informed by the sources below, rather than a manufacturer chart or a measured optimum for every Reolink model.

## Defaults and tuning

| Scene | Start with | When to adjust | Frames per hour | Video per hour at 30 FPS |
| --- | --- | --- | ---: | ---: |
| Daytime landscape | 10 seconds | Try 5s for visible movement; 30–60s for slow shadows or a mostly static scene over many hours. | 360 | 12 seconds |
| Quiet nighttime landscape | 30 seconds | Try 5–10s for traffic or moving clouds. Darkness alone does not require a longer interval. | 120 | 4 seconds |
| Stars / astronomy | 30 seconds | Match the camera's actual image refresh and exposure cycle. Try 15s if it delivers fresh star images that quickly; 60s or longer if images update slowly. | 120 | 4 seconds |
| Clouds / sky | 5 seconds | Try 10s for slow clouds; keep 5s for faster clouds. Fast motion may need shorter intervals than this app currently supports. | 720 | 24 seconds |
| Sunrise / sunset | 5 seconds | Try 10s for slower changes or lower storage use; record before and after the transition. | 720 | 24 seconds |
| Landscape over a whole day | 60 seconds | Try 10–30s if cloud movement matters. This is for slow change, not smooth fast action. | 60 | 2 seconds |

The daytime landscape preset is selected by default in the interface. Selecting a preset changes **only** the snapshot interval. It does not change the recording duration, playback FPS, camera exposure, camera resolution, or schedule. The API retains its existing 30-second default when callers omit the interval; the interface sends the number shown in the form.

The number remains editable. Changing it switches the scene selector to **Custom interval**. Selecting Custom preserves the number already entered. Existing recordings keep their original interval.

## Why there is no single ideal interval

Choose an interval based on what changes in the image and the period you want to condense. Moving clouds need more frames than slowly moving shadows. A quiet view at night can use fewer frames; busy nighttime traffic cannot. Short intervals make longer, more detailed videos but increase camera requests, saved images, and render work.

The basic calculation is:

```text
Approximate frames = recording seconds / interval seconds
Finished video seconds = frames / output FPS
```

For example, eight hours at a 10-second interval produces approximately 2,880 frames, or 96 seconds at 30 FPS. At 60-second intervals it produces 480 frames, or 16 seconds. These estimates assume successful captures throughout the period. The interface rounds planned frames up to include a capture at the start of the recording.

## Astronomy and night capture

**An interval is not an exposure time.** Waiting 30 seconds between snapshot requests does not make a 30-second exposure. Maverick requests images already provided by Home Assistant and does not set shutter speed, ISO/gain, infrared illumination, or camera night mode.

Use the stars preset only if the selected camera entity already supplies images showing stars. Security cameras may not capture faint stars adequately, even when an interval is appropriate. Maverick creates a normal timelapse; it does not stack exposures, create star-trail composites, or perform astronomical calibration.

Dedicated astronomical cameras can spend tens of seconds exposing an image. Check their real update cycle: requesting images every 5 seconds will not produce new images if the source refreshes once a minute. A 30-second stars preset is a starting cadence, not a universal astronomy setting. Brief meteors, satellites, or fast-changing aurora can be missed by periodic still images and may call for a different capture method.

Maverick's interval is the nominal time between requests, while some photography tools express a delay **after** exposure. Do not copy those values without accounting for exposure and processing time. Home Assistant integrations can cache images. Maverick's snapshot request timeout is 20 seconds; increasing the interval does not increase that timeout. An endpoint that blocks for longer can still fail. Slow requests cause missed capture slots rather than a burst of catch-up images.

The app currently accepts custom intervals from 5 to 86,400 seconds. Sources discussing 1–2 second gaps do not establish that a Home Assistant camera can sustain that rate. The 5-second lower bound remains in place.

## Sources actually reviewed

1. [Allsky: creating timelapses](https://github.com/AllskyTeam/allsky/blob/2b2c7b1347d076a489df5e614acf27de450738fb/docs/source/allsky_guide/howtos/timelapse.md). Explains how reducing the delay improves star/cloud motion and increases storage. Its exposure examples distinguish a 30- or 60-second exposure from the following processing delay. These principles informed the cloud and astronomy guidance; its delay values are not copied as Maverick intervals.
2. [Allsky: camera settings](https://github.com/AllskyTeam/allsky/blob/2b2c7b1347d076a489df5e614acf27de450738fb/docs/source/allsky_guide/settings/allsky.md). Separates daytime/nighttime exposure controls from delay, documents a 5,000 ms daytime delay, and defines start-to-start timing as exposure plus delay for relevant capture modes. This supports separating cadence from image brightness and exposing custom adjustments.
3. [GoPro Labs: eclipse timelapses](https://github.com/gopro/labs/blob/80d419a4bfed0d0e99631e20d79c5db09784cf74/docs/control/eclipse/README.md). Gives 4-second and 10-second examples for different lighting/motion goals and shows how shutter limits change the result. These are eclipse examples, not a generic landscape/cloud prescription. Maverick uses 5s as its supported fast-scene cadence and 10s as a balanced daytime starting point.
4. [GoPro Labs: very long timelapses](https://github.com/gopro/labs/blob/80d419a4bfed0d0e99631e20d79c5db09784cf74/docs/control/longtimelapse/README.md). Discusses spreading limited frames over hours or days, including intervals beyond 60 seconds. It supports the longer-interval option for slow, long projects; the 60s all-day default is Maverick's choice.

PhotoPills' timelapse guide and GoPro's general timelapse article were attempted but blocked by this cloud environment's network policy. Their contents were not reviewed and are not used as evidence for these settings. No benchmark of these presets on the user's Reolink cameras was performed.
