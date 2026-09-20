const cache = new Map<string, Intl.DateTimeFormat>();
export function formatMessageDate(
  value: string | number,
  style: 'full' | 'day' | 'time' = 'full',
  timeZone = process.env.NEXT_PUBLIC_TIME_ZONE || '',
) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return 'Date unavailable';
  const key = `${timeZone}:${style}`;
  if (!cache.has(key)) {
    const options: Intl.DateTimeFormatOptions =
      style === 'full'
        ? {
            weekday: 'short',
            year: 'numeric',
            month: 'short',
            day: 'numeric',
            hour: 'numeric',
            minute: '2-digit',
            second: '2-digit',
            timeZoneName: 'short',
          }
        : style === 'day'
          ? { month: 'numeric', day: 'numeric' }
          : { hour: '2-digit', minute: '2-digit', timeZoneName: 'short' };
    cache.set(
      key,
      new Intl.DateTimeFormat('en-US', {
        ...options,
        timeZone: timeZone || undefined,
      }),
    );
  }
  return cache.get(key)!.format(date);
}
