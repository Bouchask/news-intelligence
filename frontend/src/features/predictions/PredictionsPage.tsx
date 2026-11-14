import { FormEvent, useEffect, useState } from 'react'
import { ArrowUpRight, CircleAlert, FileText, Zap } from 'lucide-react'
import { apiGet, apiPost } from '../../api'

type Prediction = { id: string; predicted_category: string; confidence: number | null; probabilities: Record<string, number>; latency_ms: number; model: string; created_at: string }
type Result = { prediction_id: string; predicted_category: string; confidence: number | null; probabilities: Record<string, number>; model: { name: string; version: number }; latency_ms: number }

export default function PredictionsPage() {
  const [title, setTitle] = useState('')
  const [content, setContent] = useState('')
  const [result, setResult] = useState<Result | null>(null)
  const [history, setHistory] = useState<Prediction[]>([])
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const loadHistory = () => apiGet<{ items: Prediction[] }>('/api/v1/predictions/').then(value => setHistory(value.items)).catch(() => undefined)
  useEffect(() => { void loadHistory() }, [])
  const classify = async (event: FormEvent) => {
    event.preventDefault(); setError(''); setResult(null); setBusy(true)
    try { const value = await apiPost<Result>('/api/v1/predictions/classify/', { title, content }); setResult(value); await loadHistory() }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'Classification failed.') }
    finally { setBusy(false) }
  }
  return <section className="prediction-layout"><form className="panel prediction-form" onSubmit={classify}><div className="panel-kicker">LIVE INFERENCE</div><h2>Classify a news article</h2><p>Uses the currently active registered model. Prediction history stores a content hash, not the article text.</p><label className="field-label">Title<input maxLength={500} value={title} onChange={event => setTitle(event.target.value)} placeholder="Optional article headline" /></label><label className="field-label">Article content<textarea required maxLength={50000} rows={11} value={content} onChange={event => setContent(event.target.value)} placeholder="Paste article text to classify…" /></label><div className="form-footer"><span>{content.length.toLocaleString()} / 50,000 characters</span><button className="button primary" disabled={busy || !content.trim()}><Zap size={15} />{busy ? 'Classifying…' : 'Classify article'}</button></div>{error && <div className="page-error"><CircleAlert size={15} />{error}</div>}</form>
    <div className="prediction-side">{result ? <div className="panel prediction-result"><div className="panel-kicker">PREDICTION RESULT</div><span className={`prediction-category category-badge badge-${result.predicted_category.toLowerCase()}`}>{result.predicted_category}</span><div className="confidence-line"><span>Confidence</span><b>{result.confidence === null ? 'Unavailable' : `${(result.confidence * 100).toFixed(1)}%`}</b></div><div className="probability-list">{Object.entries(result.probabilities).sort((a, b) => b[1] - a[1]).map(([category, probability]) => <div key={category} className="probability-row"><span>{category}</span><div><i style={{ width: `${probability * 100}%` }} /></div><b>{(probability * 100).toFixed(1)}%</b></div>)}</div><div className="prediction-meta"><span>{result.model.name} v{result.model.version}</span><span><Zap size={12} />{result.latency_ms.toFixed(1)} ms</span></div></div> : <div className="panel prediction-placeholder"><div className="empty-icon"><FileText size={21} /></div><b>Your model output appears here</b><span>Confidence and class probabilities are returned by supported classifiers.</span></div>}
      <div className="panel recent-predictions"><div className="panel-heading"><div><div className="panel-kicker">PERSISTED HISTORY</div><h2>Recent predictions</h2></div><span className="muted-tag">{history.length}</span></div>{history.slice(0, 6).map(item => <div className="prediction-history-row" key={item.id}><span className={`category-badge badge-${item.predicted_category.toLowerCase()}`}>{item.predicted_category}</span><div><b>{item.model}</b><small>{new Date(item.created_at).toLocaleString()}</small></div><span>{item.confidence === null ? '—' : `${(item.confidence * 100).toFixed(0)}%`}</span><ArrowUpRight size={13} /></div>)}{!history.length && <div className="history-empty">No predictions saved yet.</div>}</div></div>
  </section>
}
