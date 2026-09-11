// An empty setting uses the reader's browser timezone.
const timeZone = process.env.NEXT_PUBLIC_TIME_ZONE || undefined;
const formats = {
  full: new Intl.DateTimeFormat('en-US', {
    timeZone, weekday: 'short', year: 'numeric', month: 'short', day: 'numeric',
    hour: 'numeric', minute: '2-digit', second: '2-digit', timeZoneName: 'short',
  }),
  day: new Intl.DateTimeFormat('en-US', {timeZone, month: 'numeric', day: 'numeric'}),
  time: new Intl.DateTimeFormat('en-US', {
    timeZone, hour: '2-digit', minute: '2-digit', timeZoneName: 'short',
  }),
};

export function formatMessageDate(value: string | number, style: keyof typeof formats = 'full') {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? 'Date unavailable' : formats[style].format(date);
}
