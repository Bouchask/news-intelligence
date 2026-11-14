import { useCallback, useEffect, useState } from 'react'
import { AlertCircle, Clock3, ExternalLink, Radio, RefreshCw } from 'lucide-react'

type LiveItem = {
  id: number
  title: string
  summary: string
  url: string
  image_url: string | null
  sections: string[]
  language: string
  snapshot_at: string
  last_seen_at: string
}
type ImportResult = { fetched: number; created: number; updated: number; snapshot_at: string }

function csrfToken(): string {
  return document.cookie.split('; ').find(cookie => cookie.startsWith('csrftoken='))?.split('=').slice(1).join('=') ?? ''
}

export default function LiveFeed() {
  const [items, setItems] = useState<LiveItem[]>([])
  const [loading, setLoading] = useState(true)
  const [importing, setImporting] = useState(false)
  const [error, setError] = useState('')
  const [importResult, setImportResult] = useState<ImportResult | null>(null)

  const loadItems = useCallback(async () => {
    const response = await fetch('/api/v1/news/live/?lang=english&limit=100', { cache: 'no-store' })
    const body = await response.json()
    if (!response.ok) throw new Error(body.error ?? 'Could not load saved headlines.')
    setItems(body.items as LiveItem[])
  }, [])

  useEffect(() => {
    loadItems().catch(reason => setError(reason instanceof Error ? reason.message : 'Could not load headlines.'))
      .finally(() => setLoading(false))
  }, [loadItems])

  const importNow = async () => {
    setImporting(true)
    setError('')
    setImportResult(null)
    try {
      const response = await fetch('/api/v1/news/live/import/?lang=english', { method: 'POST', headers: { 'X-CSRFToken': csrfToken() } })
      const body = await response.json()
      if (!response.ok) throw new Error(body.error ?? 'BBC News API import failed.')
      setImportResult(body as ImportResult)
      await loadItems()
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'BBC News API import failed.')
    } finally {
      setImporting(false)
      setLoading(false)
    }
  }

  return <section className="live-feed-wrap">
    <div className="panel live-feed-intro">
      <div className="feed-title"><span className="feed-icon"><Radio size={18} /></span><div><div className="panel-kicker">CURRENT BBC SNAPSHOT · ENGLISH</div><h2>Latest BBC headlines</h2></div></div>
      <button className="button primary" onClick={importNow} disabled={loading || importing}><RefreshCw size={15} className={importing ? 'spin' : ''} />{importing ? 'Fetching latest…' : loading ? 'Loading saved feed…' : 'Fetch latest headlines'}</button>
      <p>The feed is refreshed on demand from the configured public BBC News API. Headlines and summaries are saved locally with BBC article links; this feed does not provide full article text or the archive’s five training labels.</p>
      {error && <div className="feed-message feed-error"><AlertCircle size={15} />{error}</div>}
      {importResult && <div className="feed-message feed-success"><Clock3 size={14} />Fetched {importResult.fetched} unique headlines · {importResult.created} new · {importResult.updated} refreshed · {new Date(importResult.snapshot_at).toLocaleString()}</div>}
    </div>
    <div className="live-results-heading"><div><div className="panel-kicker">SAVED FEED ITEMS</div><h2>{items.length ? `${items.length} headlines` : 'No headlines imported yet'}</h2></div>{items.length > 0 && <span className="live-count"><i />Updated from the API snapshot</span>}</div>
    {loading && items.length === 0 ? <div className="panel feed-empty">Loading saved headlines…</div> : items.length === 0 ? <div className="panel feed-empty"><Radio size={23} /><b>Fetch the latest BBC feed</b><span>The importer deduplicates repeated links returned under multiple API sections.</span></div> : <div className="live-news-grid">{items.map(item => <article className="panel live-news-card" key={item.id}>{item.image_url && <img src={item.image_url} alt="" loading="lazy" referrerPolicy="no-referrer" />}<div className="live-news-content"><div className="live-news-meta"><span>{item.sections.slice(0, 2).join(' · ') || 'BBC News'}</span><time>{new Date(item.last_seen_at).toLocaleString()}</time></div><h3>{item.title}</h3>{item.summary && <p>{item.summary}</p>}<a href={item.url} target="_blank" rel="noreferrer">Read at BBC <ExternalLink size={13} /></a></div></article>)}</div>}
  </section>
}
