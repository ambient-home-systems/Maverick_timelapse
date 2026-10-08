import assert from "node:assert/strict";
import test from "node:test";
import { defaultSchedule, scheduledStart } from "../maverick_timelapse/app/static/schedule.mjs";

// Run with TZ=America/New_York to check the local-to-UTC conversion explicitly.
test("a complete 11 AM date converts correctly in the browser timezone", () => {
  const now = Date.parse("2026-10-08T14:24:00Z");
  assert.equal(scheduledStart("2026-10-08", "11:00", now), "2026-10-08T15:00:00.000Z");
  assert.equal(scheduledStart("2026-10-08", "11:00:00", now), "2026-10-08T15:00:00.000Z");
});

test("winter schedules use the standard-time offset", () => {
  assert.equal(scheduledStart("2026-12-08", "11:00", Date.parse("2026-10-08T14:24:00Z")),
    "2026-12-08T16:00:00.000Z");
});

test("missing or malformed dates and times produce an actionable error", () => {
  for (const [date, time] of [["", "11:00"], ["2026-10-08", ""], ["10/08/2026", "11:00"], ["2026-10-08", "11:00 AM"]]) {
    assert.throws(() => scheduledStart(date, time), /complete start date and time/);
  }
});

test("past and current times suggest Start now", () => {
  const now = Date.parse("2026-10-08T15:00:00Z");
  assert.throws(() => scheduledStart("2026-10-08", "10:59", now), /select Start now/);
  assert.throws(() => scheduledStart("2026-10-08", "11:00", now), /select Start now/);
});

test("nonexistent calendar dates and daylight-saving times are rejected", () => {
  const now = Date.parse("2026-01-01T00:00:00Z");
  for (const [date, time] of [["2026-02-30", "11:00"], ["2026-03-08", "02:30"], ["2026-10-08", "25:00"]]) {
    assert.throws(() => scheduledStart(date, time, now), /does not exist/);
  }
});

test("the suggested schedule stays in local time across midnight", () => {
  assert.deepEqual(defaultSchedule(new Date("2026-01-01T04:58:30Z")), { date: "2026-01-01", time: "00:03" });
});
