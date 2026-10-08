function pad(value) { return String(value).padStart(2, "0"); }

export function defaultSchedule(now = new Date()) {
  const start = new Date(now.getTime() + 5 * 60 * 1000);
  start.setSeconds(0, 0);
  return {
    date: `${start.getFullYear()}-${pad(start.getMonth() + 1)}-${pad(start.getDate())}`,
    time: `${pad(start.getHours())}:${pad(start.getMinutes())}`,
  };
}

export function scheduledStart(date, time, now = Date.now()) {
  const dateParts = /^(\d{4})-(\d{2})-(\d{2})$/.exec(date || "");
  const timeParts = /^(\d{2}):(\d{2})(?::00)?$/.exec(time || "");
  if (!dateParts || !timeParts) throw new Error("Choose a complete start date and time, or select Start now.");
  const [year, month, day] = dateParts.slice(1).map(Number);
  const [hour, minute] = timeParts.slice(1).map(Number);
  // Numeric construction avoids browser differences when parsing a local datetime string.
  const start = new Date(year, month - 1, day, hour, minute, 0, 0);
  if (start.getFullYear() !== year || start.getMonth() !== month - 1 || start.getDate() !== day ||
      start.getHours() !== hour || start.getMinutes() !== minute) {
    throw new Error("That date or time does not exist in your timezone. Choose another start time.");
  }
  if (start.getTime() <= now) throw new Error("Choose a future start time, or select Start now.");
  return start.toISOString();
}
