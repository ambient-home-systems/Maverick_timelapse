// Practical starting points for Home Assistant snapshots, not exposure settings.
// Research and the reasoning for these app defaults: docs/capture-intervals.md.
export const capturePresets = [
  {
    id: "landscape_day", name: "Landscape — daytime", seconds: 10,
    description: "Start at 10 seconds for scenery, changing light, and gentle motion. Try 5 seconds for more movement, or 30–60 seconds for a mostly static view over many hours.",
  },
  {
    id: "landscape_night", name: "Landscape — nighttime", seconds: 30,
    description: "Start at 30 seconds for a quiet nighttime view over several hours. Use 5–10 seconds for traffic or moving clouds. A longer interval does not brighten the image; exposure is controlled by your camera.",
  },
  {
    id: "stars", name: "Stars / astronomy", seconds: 30,
    description: "Start at 30 seconds for gradual star movement over several hours. Your camera must already show stars in its snapshots. Match the interval to its image refresh and exposure time; try 60 seconds or longer if new images arrive slowly. This does not enable long exposures, image stacking, or star-trail composites.",
  },
  {
    id: "clouds", name: "Clouds / sky", seconds: 5,
    description: "Start at 5 seconds to preserve cloud movement. Try 10 seconds for slow clouds. This app’s minimum is 5 seconds; very fast clouds may still look jumpy. Check that your camera returns fresh images at this rate.",
  },
  {
    id: "sunrise_sunset", name: "Sunrise / sunset", seconds: 5,
    description: "Start at 5 seconds for changing light and moving clouds. Allow enough recording time for the full transition. This preset changes the interval only; it does not schedule sunrise or sunset automatically.",
  },
  {
    id: "all_day", name: "Landscape — all day", seconds: 60,
    description: "Start at 60 seconds for slow changes over 8–24 hours with fewer snapshots. Use 10–30 seconds if cloud movement matters. Long intervals can skip brief events.",
  },
];

export const defaultPreset = "landscape_day";
