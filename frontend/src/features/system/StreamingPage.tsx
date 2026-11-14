import { useCallback, useEffect, useState } from 'react'
import { Cable, CircleAlert, ExternalLink, Radio, RefreshCw, Send } from 'lucide-react'
import { apiGet, apiPost } from '../../api'

type Service = { name: string; status: string; detail: string }
type NewsItem = { id: number; title: string; url: string; sections: string[]; last_seen_at: string }
type StreamStatus = { broker: string; available_topics: string[]; configured_topics: string[]; topic_counts: Record<string, number>; processed_predictions: number; dead_lettered: number }

export default function StreamingPage() {
  const [kafka, setKafka] = useState<Service | null>(null)
  const [items, setItems] = useState<NewsItem[]>([])
  const [error, setError] = useState('')
  const [status, setStatus] = useState<StreamStatus | null>(null)
  const [replaying, setReplaying] = useState(false)
  const [notice, setNotice] = useState('')
  const refresh = useCallback(async () => {
    try {
      const [serviceResult, feedResult, streamResult] = await Promise.all([
        apiGet<{ services: Service[] }>('/api/v1/system/services/'),
        apiGet<{ items: NewsItem[] }>('/api/v1/news/live/?lang=english&limit=20'),
        apiGet<StreamStatus>('/api/v1/system/streaming/'),
      ])
      setKafka(serviceResult.services.find(item => item.name === 'Kafka') ?? null)
      setItems(feedResult.items); setStatus(streamResult); setError('')
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'Could not read stream status.') }
  }, [])
  const replay = async () => {
    setReplaying(true); setNotice(''); setError('')
    try {
      const result = await apiPost<{ published: number }>('/api/v1/system/streaming/replay/')
      setNotice(`Published ${result.published} saved BBC headlines to news.raw. Start the three consumers to process them.`)
      await refresh()
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'Kafka replay failed.') }
    finally { setReplaying(false) }
  }
  useEffect(() => { void refresh(); const timer = window.setInterval(() => void refresh(), 15000); return () => window.clearInterval(timer) }, [refresh])
  return <section className="streaming-page"><div className="panel stream-status-banner"><div className="stream-banner-icon"><Cable size={20} /></div><div><div className="panel-kicker">STREAMING STATUS</div><h2>BBC API polling and Kafka</h2><p>BBC headlines are fetched when requested. Kafka broker status is checked from the backend; no streaming metrics are invented.</p></div><button className="icon-button" onClick={() => void refresh()} title="Refresh"><RefreshCw size={16} /></button></div>{error && <div className="page-error"><CircleAlert size={14} />{error}</div>}
    {notice && <div className="success-notice">{notice}</div>}<div className="stream-metrics"><div className="metric-card"><div className="metric-top"><span>Kafka broker</span><Cable size={16} /></div><div className="stream-metric-value">{kafka?.status.replace('_', ' ') ?? 'Checking'}</div><div className="metric-note">{kafka?.detail ?? 'Backend health probe'}</div></div><div className="metric-card"><div className="metric-top"><span>Saved API headlines</span><Radio size={16} /></div><div className="stream-metric-value">{items.length}</div><div className="metric-note">Recent items in the local database</div></div><div className="metric-card"><div className="metric-top"><span>Classified from Kafka</span><Radio size={16} /></div><div className="stream-metric-value">{status?.processed_predictions ?? '—'}</div><div className="metric-note">Persisted prediction results</div></div></div>
    <div className="panel stream-status-banner"><div><div className="panel-kicker">KAFKA PIPELINE</div><h2>{status?.available_topics.length ?? 0} / {status?.configured_topics.length ?? 0} topics available</h2><p>Dead-lettered events: {status?.dead_lettered ?? 0}. Topic counts reflect events handled by consumers.</p></div><button className="primary-button" disabled={replaying || kafka?.status !== 'reachable'} onClick={() => void replay()}><Send size={15} />{replaying ? 'Publishing…' : 'Replay saved BBC items'}</button></div>
    <div className="panel stream-events"><div className="panel-heading"><div><div className="panel-kicker">RECENT BBC ITEMS</div><h2>Imported headline activity</h2></div><button className="text-button" onClick={() => window.dispatchEvent(new CustomEvent('news-nav', { detail: 'BBC Live Feed' }))}>Open feed <ExternalLink size={13} /></button></div>{items.map(item => <div className="stream-event" key={item.id}><span className="stream-event-dot" /><div><b>{item.title}</b><small>{item.sections.join(' · ') || 'BBC News'} · seen {new Date(item.last_seen_at).toLocaleString()}</small></div><a href={item.url} target="_blank" rel="noreferrer" aria-label="Open BBC article"><ExternalLink size={14} /></a></div>)}{!items.length && <div className="empty-state compact-empty"><div className="empty-icon"><Radio size={18} /></div><b>No BBC feed items imported yet</b><span>Import the latest snapshot from BBC Live Feed.</span></div>}</div></section>
}
