'use client';
import { useEffect, useRef, useState } from 'react';
import { X, Plus, Trash2 } from 'lucide-react';
import { defaultFeeds, type Preferences, type Feed } from '../lib/preferences';

export function SettingsPanel({
  open,
  onClose,
  value: savedValue,
  onChange,
  saveError,
}: {
  open: boolean;
  onClose: () => void;
  value: Preferences;
  onChange: (value: Preferences) => boolean;
  saveError: string;
}) {
  const [value, setDraft] = useState(savedValue);
  const [addingFeed, setAddingFeed] = useState(false);
  const content = useRef<HTMLDivElement>(null);
  const dialog = useRef<HTMLDialogElement>(null);
  const [tab, setTab] = useState('Appearance'),
    [name, setName] = useState(''),
    [url, setUrl] = useState(''),
    [category, setCategory] = useState(''),
    [categoryName, setCategoryName] = useState(''),
    [error, setError] = useState(''),
    [busy, setBusy] = useState(false),
    [zone, setZone] = useState(value.timeZone);
  const [zones, setZones] = useState<string[]>([]);
  const latest = useRef(value);
  latest.current = value;
  const request = useRef<AbortController | null>(null);
  useEffect(() => {
    if (open) dialog.current?.showModal();
    else {
      dialog.current?.close();
      request.current?.abort();
      setBusy(false);
    }
  }, [open]);
  useEffect(() => () => request.current?.abort(), []);

  useEffect(() => {
    setZones(
      (
        Intl as typeof Intl & { supportedValuesOf?: (key: string) => string[] }
      ).supportedValuesOf?.('timeZone') || [],
    );
  }, []);
  function change(patch: Partial<Preferences>) {
    setDraft({ ...value, ...patch });
  }
  function addFeed(feed: Feed) {
    const p = latest.current;
    if (
      p.feeds.some((f) => f.id === feed.id || (feed.url && f.url === feed.url))
    )
      return;
    setDraft({
      ...p,
      feeds: [...p.feeds, feed],
      categories: p.categories.map((c) =>
        c.id === category ? { ...c, ids: [...c.ids, feed.id] } : c,
      ),
    });
  }
  function assign(id: string, to: string) {
    change({
      categories: value.categories.map((c) => ({
        ...c,
        ids: [...c.ids.filter((x) => x !== id), ...(c.id === to ? [id] : [])],
      })),
    });
  }
  async function customFeed(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    let address: URL;
    try {
      address = new URL(url);
      if (
        !['http:', 'https:'].includes(address.protocol) ||
        address.username ||
        address.password
      )
        throw Error();
    } catch {
      setError(
        'Enter a public RSS or Atom URL beginning with https:// or http://.',
      );
      return;
    }
    if (value.feeds.some((f) => f.url === address.href)) {
      setError('This feed is already in your inbox.');
      return;
    }
    const controller = new AbortController();
    request.current = controller;
    setBusy(true);
    try {
      const response = await fetch(
        '/api/feed?url=' + encodeURIComponent(address.href),
        { signal: controller.signal },
      );
      const data = (await response.json()) as { error?: string };
      if (!response.ok) throw Error(data.error || 'Unable to load this feed.');
      if (controller.signal.aborted) return;
      addFeed({
        id: 'custom-' + crypto.randomUUID(),
        name: name.trim(),
        short: name.trim(),
        address: address.hostname,
        base: address.origin,
        index: address.pathname + address.search,
        url: address.href,
      });
      setName('');
      setUrl('');
    } catch (e) {
      if (!controller.signal.aborted)
        setError(e instanceof Error ? e.message : 'Unable to load feed.');
    } finally {
      if (request.current === controller) setBusy(false);
    }
  }
  const dirty =
    JSON.stringify({ ...value, timeZone: zone.trim() }) !==
    JSON.stringify(savedValue);
  const removed = savedValue.feeds.filter(
    (f) => !value.feeds.some((d) => d.id === f.id),
  );
  function apply(close: boolean) {
    if (busy) return;
    try {
      new Intl.DateTimeFormat('en', { timeZone: zone.trim() || undefined });
    } catch {
      setError('Choose a valid timezone, such as America/Los_Angeles or UTC.');
      setTab('Appearance');
      return;
    }
    if (
      value.feeds.some((f) => !f.name.trim()) ||
      value.categories.some((c) => !c.name.trim())
    ) {
      setError('Feed and category names cannot be blank.');
      return;
    }
    if (name.trim() || url.trim() || categoryName.trim()) {
      setError(
        'Finish adding your feed or category, or clear its fields, before saving.',
      );
      return;
    }
    const next = { ...value, timeZone: zone.trim() };
    if (dirty && !onChange(next)) return;
    setDraft(next);
    setError('');
    if (close) onClose();
  }
  return (
    <dialog
      ref={dialog}
      className="settings-dialog"
      aria-labelledby="settings-title"
      onClose={onClose}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <header className="profile-header">
        <div>
          <h2 id="settings-title">Settings</h2>
          <p className="settings-hint">
            Changes are saved only when you choose Apply or OK.
          </p>
        </div>
        <button
          className="icon-button"
          aria-label="Close settings"
          onClick={onClose}
        >
          <X size={20} />
        </button>
      </header>
      <nav className="settings-tabs" aria-label="Settings sections">
        {['Appearance', 'Feeds', 'Categories'].map((t) => (
          <button
            key={t}
            aria-pressed={tab === t}
            onClick={() => {
              setTab(t);
              setError('');
              content.current?.scrollTo(0, 0);
            }}
          >
            {t}
          </button>
        ))}
      </nav>
      <div className="settings-content" ref={content}>
        {tab === 'Appearance' && (
          <>
            <h3>Make it yours</h3>
            <label className="settings-field">
              Theme
              <select
                value={value.theme}
                onChange={(e) =>
                  change({ theme: e.target.value as Preferences['theme'] })
                }
              >
                <option value="auto">Desktop theme (when available)</option>
                <option value="dark">Ethereal dark</option>
                <option value="light">Light</option>
              </select>
            </label>
            <label className="settings-field">
              Reading text size
              <select
                value={value.fontSize}
                onChange={(e) => change({ fontSize: Number(e.target.value) })}
              >
                <option value={14}>Standard · 14px</option>
                <option value={16}>Medium · 16px</option>
                <option value={18}>Large · 18px</option>
              </select>
            </label>
            <label className="settings-field">
              Message spacing
              <select
                value={value.density}
                onChange={(e) =>
                  change({ density: e.target.value as Preferences['density'] })
                }
              >
                <option value="comfortable">Comfortable</option>
                <option value="compact">Compact</option>
              </select>
            </label>
            <div>
              <label className="settings-field">
                Timezone
                <input
                  list="timezone-options"
                  value={zone}
                  placeholder="Browser timezone"
                  onChange={(e) => setZone(e.target.value)}
                />
              </label>
              <datalist id="timezone-options">
                <option value="UTC" />
                {zones.map((z) => (
                  <option key={z} value={z} />
                ))}
              </datalist>
              <p className="settings-hint">
                Leave blank to follow your browser. All message and sync times
                use this setting.
              </p>
            </div>
          </>
        )}
        {tab === 'Feeds' && (
          <>
            <div className="settings-section-heading">
              <h3>Feeds</h3>
              <button
                className="settings-action"
                aria-expanded={addingFeed}
                aria-controls="add-feed-fields"
                onClick={() => setAddingFeed(!addingFeed)}
              >
                <Plus size={16} /> {addingFeed ? 'Hide add feed' : 'Add feed'}
              </button>
            </div>
            {addingFeed && (
              <section
                id="add-feed-fields"
                className="settings-add-form"
                aria-label="Add a feed"
              >
                <label className="settings-field">
                  Category for new feeds
                  <select
                    value={
                      value.categories.some((c) => c.id === category)
                        ? category
                        : ''
                    }
                    onChange={(e) => setCategory(e.target.value)}
                  >
                    <option value="">Uncategorized</option>
                    {value.categories.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name}
                      </option>
                    ))}
                  </select>
                </label>
                {defaultFeeds.some(
                  (f) => !value.feeds.some((x) => x.id === f.id),
                ) && (
                  <label className="settings-field">
                    Built-in feed
                    <select
                      value=""
                      onChange={(e) => {
                        const f = defaultFeeds.find(
                          (f) => f.id === e.target.value,
                        );
                        if (f) addFeed(f);
                      }}
                    >
                      <option value="">Choose a feed to add…</option>
                      {defaultFeeds
                        .filter((f) => !value.feeds.some((x) => x.id === f.id))
                        .map((f) => (
                          <option key={f.id} value={f.id}>
                            {f.name}
                          </option>
                        ))}
                    </select>
                  </label>
                )}
                <form onSubmit={customFeed}>
                  <label className="settings-field">
                    Name
                    <input
                      required
                      maxLength={80}
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      placeholder="My feed"
                    />
                  </label>
                  <label className="settings-field">
                    RSS or Atom URL
                    <input
                      type="url"
                      required
                      value={url}
                      onChange={(e) => setUrl(e.target.value)}
                      placeholder="https://example.org/feed.xml"
                    />
                  </label>
                  <p className="settings-hint">
                    Public RSS and Atom feeds are supported. Feed content is
                    shown as plain text.
                  </p>
                  <button
                    className="settings-action"
                    disabled={busy || !name.trim()}
                  >
                    <Plus size={16} />
                    {busy ? 'Checking feed…' : 'Add feed'}
                  </button>
                </form>
              </section>
            )}
            <p className="settings-hint">
              Edit names and categories below. Removals stay pending until you
              save.
            </p>
            <h3>
              Your feeds <span className="muted">({value.feeds.length})</span>
            </h3>
            {value.feeds.length === 0 && (
              <p>No feeds yet. Use Add feed above.</p>
            )}
            {value.feeds.map((f) => (
              <div className="settings-feed" key={f.id}>
                <label className="settings-field">
                  Feed name
                  <input
                    aria-label={'Name for ' + f.name}
                    value={f.name}
                    maxLength={80}
                    onChange={(e) =>
                      change({
                        feeds: value.feeds.map((x) =>
                          x.id === f.id
                            ? {
                                ...x,
                                name: e.target.value,
                                short: e.target.value,
                              }
                            : x,
                        ),
                      })
                    }
                  />
                </label>
                <div className="settings-feed-row">
                  <label className="settings-field">
                    Category
                    <select
                      value={
                        value.categories.find((c) => c.ids.includes(f.id))
                          ?.id || ''
                      }
                      onChange={(e) => assign(f.id, e.target.value)}
                    >
                      <option value="">Uncategorized</option>
                      {value.categories.map((c) => (
                        <option key={c.id} value={c.id}>
                          {c.name}
                        </option>
                      ))}
                    </select>
                  </label>
                  <button
                    className="settings-action"
                    aria-label={'Remove ' + f.name}
                    onClick={() =>
                      change({
                        feeds: value.feeds.filter((x) => x.id !== f.id),
                        categories: value.categories.map((c) => ({
                          ...c,
                          ids: c.ids.filter((id) => id !== f.id),
                        })),
                      })
                    }
                  >
                    <Trash2 size={16} /> Remove
                  </button>
                </div>
                {f.url && (
                  <small className="settings-hint feed-url">{f.url}</small>
                )}
              </div>
            ))}
          </>
        )}
        {tab === 'Categories' && (
          <>
            <h3>Organize your feeds</h3>
            <p className="settings-hint">
              Removing a category moves its feeds to Uncategorized.
            </p>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                const name = categoryName.trim();
                if (!name) return;
                if (
                  value.categories.some(
                    (c) => c.name.toLowerCase() === name.toLowerCase(),
                  )
                ) {
                  setError('A category with that name already exists.');
                  return;
                }
                change({
                  categories: [
                    ...value.categories,
                    { id: crypto.randomUUID(), name, ids: [] },
                  ],
                });
                setCategoryName('');
                setError('');
              }}
            >
              <label className="settings-field">
                New category
                <input
                  required
                  maxLength={80}
                  value={categoryName}
                  onChange={(e) => setCategoryName(e.target.value)}
                  placeholder="Category name"
                />
              </label>
              <button
                className="settings-action"
                disabled={!categoryName.trim()}
              >
                <Plus size={16} /> Add category
              </button>
            </form>
            {value.categories.map((c) => (
              <div className="settings-feed-row category-row" key={c.id}>
                <label className="settings-field">
                  Category name
                  <input
                    value={c.name}
                    maxLength={80}
                    aria-label={'Category ' + c.name}
                    onChange={(e) =>
                      change({
                        categories: value.categories.map((x) =>
                          x.id === c.id ? { ...x, name: e.target.value } : x,
                        ),
                      })
                    }
                  />
                </label>
                <button
                  className="settings-action"
                  aria-label={'Remove category ' + c.name}
                  onClick={() =>
                    change({
                      categories: value.categories.filter((x) => x.id !== c.id),
                    })
                  }
                >
                  <Trash2 size={16} /> Remove
                </button>
              </div>
            ))}
          </>
        )}
      </div>
      <div className="settings-footer">
        {(error || saveError) && (
          <p className="error" role="alert">
            {error || saveError}
          </p>
        )}
        <p className="settings-save-status" role="status">
          {removed.length
            ? `${removed.length} feed${removed.length === 1 ? '' : 's'} will be removed when you save.`
            : dirty
              ? 'You have unapplied changes.'
              : 'No unapplied changes.'}
        </p>
        <div className="settings-footer-actions">
          <button className="settings-action" onClick={onClose}>
            Cancel
          </button>
          <button
            className="settings-action"
            disabled={!dirty || busy}
            onClick={() => apply(false)}
          >
            Apply
          </button>
          <button
            className="settings-action settings-primary"
            disabled={busy}
            onClick={() => apply(true)}
          >
            OK
          </button>
        </div>
      </div>
    </dialog>
  );
}
