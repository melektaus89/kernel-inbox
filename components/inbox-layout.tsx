'use client';

import {Children, useEffect, useState, type ReactNode} from 'react';
import {Group, Panel, Separator, type Layout} from 'react-resizable-panels';

const storageKey = 'kernel-pane-widths';
const panelIds = ['feeds', 'messages', 'reading'];

function readLayout(): Layout | undefined {
  try {
    const saved: unknown = JSON.parse(localStorage.getItem(storageKey) || 'null');
    if (!saved || typeof saved !== 'object') return;
    const layout = saved as Layout;
    if (panelIds.every(id => Number.isFinite(layout[id]) && layout[id] > 0) &&
        Math.abs(panelIds.reduce((sum, id) => sum + layout[id], 0) - 100) < 0.1) {
      return Object.fromEntries(panelIds.map(id => [id, layout[id]]));
    }
  } catch { /* Storage may be unavailable. */ }
}

export function InboxLayout({children, reading}: {children: ReactNode; reading: boolean}) {
  const [desktop, setDesktop] = useState(false);
  const [defaults, setDefaults] = useState([215, 370]);
  const [layout, setLayout] = useState<Layout | undefined>(undefined);
  const [sidebar, mailbox, reader, ...overlays] = Children.toArray(children);

  useEffect(() => {
    const media = window.matchMedia('(min-width: 851px)');
    const update = () => {
      setLayout(readLayout());
      setDefaults(window.innerWidth >= 1550 ? [235, 410] : window.innerWidth <= 1100 ? [180, 320] : [215, 370]);
      setDesktop(media.matches);
    };
    update();
    media.addEventListener('change', update);
    return () => media.removeEventListener('change', update);
  }, []);

  function saveLayout(next: Layout) {
    try { localStorage.setItem(storageKey, JSON.stringify(next)); } catch { /* Resizing still works without storage. */ }
  }

  return <main className={`app ${reading ? 'reading' : ''} ${desktop ? 'resizable-app' : ''}`}>
    {desktop ? <Group className="inbox-panels" defaultLayout={layout} onLayoutChanged={saveLayout}>
      <Panel id="feeds" defaultSize={defaults[0]} minSize={180} maxSize={400} className="inbox-pane">{sidebar}</Panel>
      <Separator className="pane-divider" aria-label="Resize feed sidebar" title="Drag to resize sidebar · Arrow keys to adjust" />
      <Panel id="messages" defaultSize={defaults[1]} minSize={280} maxSize={700} className="inbox-pane">{mailbox}</Panel>
      <Separator className="pane-divider" aria-label="Resize message list and reading pane" title="Drag to resize messages and reader · Arrow keys to adjust" />
      <Panel id="reading" minSize={300} className="inbox-pane">{reader}</Panel>
    </Group> : <>{sidebar}{mailbox}{reader}</>}
    {overlays}
  </main>;
}
