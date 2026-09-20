export type Feed = {
  id: string;
  name: string;
  short: string;
  address: string;
  base: string;
  index: string;
  url?: string;
};
export type Category = { id: string; name: string; ids: string[] };
export type Preferences = {
  theme: 'auto' | 'dark' | 'light';
  fontSize: number;
  density: 'comfortable' | 'compact';
  timeZone: string;
  feeds: Feed[];
  categories: Category[];
};
export const defaultFeeds: Feed[] = [
  {
    id: 'lkml',
    name: 'Linux kernel',
    short: 'LKML',
    address: 'linux-kernel@vger.kernel.org',
    base: 'https://lkml.org',
    index: '/lkml/last100',
  },
  {
    id: 'linus',
    name: 'Linus threads',
    short: 'Linus threads',
    address: 'torvalds@linux-foundation.org',
    base: 'https://lkml.org',
    index: '/lkml/last100',
  },
  {
    id: 'regressions',
    name: 'Regressions',
    short: 'Regressions',
    address: 'regressions@lists.linux.dev',
    base: 'https://lore.kernel.org',
    index: '/regressions/',
  },
  {
    id: 'stable',
    name: 'Stable kernel',
    short: 'Stable kernel',
    address: 'stable@vger.kernel.org',
    base: 'https://lore.kernel.org',
    index: '/stable/',
  },
  {
    id: 'linux-next',
    name: 'linux-next',
    short: 'linux-next',
    address: 'linux-next@vger.kernel.org',
    base: 'https://lore.kernel.org',
    index: '/linux-next/',
  },
  {
    id: 'netdev',
    name: 'Networking',
    short: 'Networking',
    address: 'netdev@vger.kernel.org',
    base: 'https://lists.openwall.net',
    index: '/netdev/',
  },
  {
    id: 'releases',
    name: 'Releases & pulls',
    short: 'Releases & pulls',
    address: 'linux-kernel@vger.kernel.org',
    base: 'https://lkml.org',
    index: '/lkml/last100',
  },
  {
    id: 'linux-cve-announce',
    name: 'Kernel CVEs',
    short: 'Kernel CVEs',
    address: 'linux-cve-announce@vger.kernel.org',
    base: 'https://lists.openwall.net',
    index: '/linux-cve-announce/',
  },
  {
    id: 'oss-security',
    name: 'OSS Security',
    short: 'OSS Security',
    address: 'oss-security@lists.openwall.com',
    base: 'https://www.openwall.com/lists',
    index: '/oss-security/',
  },
];
export const defaultCategories: Category[] = [
  { id: 'overview', name: 'Overview', ids: ['releases', 'linus', 'lkml'] },
  {
    id: 'fixes-security',
    name: 'Fixes & security',
    ids: ['regressions', 'stable', 'linux-cve-announce', 'oss-security'],
  },
  { id: 'development', name: 'Development', ids: ['linux-next', 'netdev'] },
];

export const defaultPreferences: Preferences = {
  theme: 'auto',
  fontSize: 14,
  density: 'comfortable',
  timeZone: process.env.NEXT_PUBLIC_TIME_ZONE || '',
  feeds: defaultFeeds,
  categories: defaultCategories,
};
export function readPreferences(): Preferences {
  try {
    const p = JSON.parse(localStorage.getItem('kernel-preferences') || 'null');
    if (!p || !Array.isArray(p.feeds) || !Array.isArray(p.categories))
      return defaultPreferences;
    const feeds: Feed[] = [];
    for (const f of p.feeds) {
      if (
        !f ||
        typeof f.id !== 'string' ||
        typeof f.name !== 'string' ||
        feeds.some((x) => x.id === f.id)
      )
        continue;
      const builtIn = defaultFeeds.find((d) => d.id === f.id);
      if (builtIn) {
        feeds.push({
          ...builtIn,
          name: f.name || builtIn.name,
          short: f.short || f.name || builtIn.short,
        });
        continue;
      }
      try {
        const url = new URL(f.url);
        if (
          !['https:', 'http:'].includes(url.protocol) ||
          url.username ||
          url.password
        )
          continue;
        feeds.push({
          id: f.id,
          name: f.name || url.hostname,
          short: f.name || url.hostname,
          address: url.hostname,
          base: url.origin,
          index: url.pathname + url.search,
          url: url.href,
        });
      } catch {
        /* Ignore invalid saved feeds. */
      }
    }
    const categories: Category[] = [];
    const assigned = new Set<string>();
    for (const c of p.categories) {
      if (
        !c ||
        typeof c.id !== 'string' ||
        typeof c.name !== 'string' ||
        !Array.isArray(c.ids) ||
        categories.some((x) => x.id === c.id)
      )
        continue;
      const ids: string[] = c.ids.filter((id: string) => {
        if (!feeds.some((f) => f.id === id) || assigned.has(id)) return false;
        assigned.add(id);
        return true;
      });
      categories.push({ id: c.id, name: c.name || 'Unnamed category', ids });
    }
    let timeZone = typeof p.timeZone === 'string' ? p.timeZone : '';
    try {
      new Intl.DateTimeFormat('en', { timeZone: timeZone || undefined });
    } catch {
      timeZone = '';
    }
    return {
      theme: ['auto', 'dark', 'light'].includes(p.theme) ? p.theme : 'auto',
      fontSize: [14, 16, 18].includes(p.fontSize) ? p.fontSize : 14,
      density: p.density === 'compact' ? 'compact' : 'comfortable',
      timeZone,
      feeds,
      categories,
    };
  } catch {
    return defaultPreferences;
  }
}
