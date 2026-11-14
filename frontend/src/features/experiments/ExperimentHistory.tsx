import { useEffect, useState } from 'react'
import { ChevronDown, CircleAlert, ExternalLink } from 'lucide-react'
import { apiGet, apiPost } from '../../api'

type Experiment = { id: string; name: string; algorithm: string; status: string; configuration: Record<string, unknown>; metrics: Record<string, number>; confusion_matrix: { labels: string[]; values: number[][] }; artifact_available: boolean; error: string; created_at: string }

export default function ExperimentHistory() {
  const [items, setItems] = useState<Experiment[]>([])
  const [error, setError] = useState('')
  const [busy, setBusy] = useState('')
  const load = () => apiGet<{ items: Experiment[] }>('/api/v1/experiments/').then(result => setItems(result.items)).catch(reason => setError(reason.message))
  useEffect(() => { void load() }, [])

  const register = async (item: Experiment) => {
    setBusy(item.id); setError('')
    try {
      await apiPost(`/api/v1/experiments/${item.id}/register/`, {})
      await load()
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'Registration failed.') }
    finally { setBusy('') }
  }

  return <section className="panel table-panel"><div className="panel-heading"><div><div className="panel-kicker">MODEL EVALUATION</div><h2>Experiment history</h2></div><span className="muted-tag">{items.length} runs</span></div><p className="section-description">Validation scores come from stratified folds on training data. Test scores use the untouched stratified holdout.</p>{error && <div className="page-error"><CircleAlert size={14} />{error}</div>}
    <div className="table-scroll"><table><thead><tr><th>Experiment</th><th>Status</th><th>Algorithm / selector</th><th>CV macro F1</th><th>Test macro F1</th><th>Accuracy</th><th>Duration</th><th /></tr></thead><tbody>{items.map(item => <tr key={item.id}><td><b>{item.name}</b><small>{new Date(item.created_at).toLocaleString()}</small></td><td><span className={`run-status status-${item.status}`}>{item.status}</span></td><td>{item.algorithm.replace('_', ' ')}<small>{String(item.configuration.selector ?? 'none')}</small></td><td>{format(item.metrics.cv_f1_macro)}</td><td><b>{format(item.metrics.f1_macro)}</b>{typeof item.metrics.f1_macro === 'number' && <div className="score-track"><i style={{ width: `${item.metrics.f1_macro * 100}%` }} /></div>}</td><td>{format(item.metrics.accuracy)}</td><td>{typeof item.metrics.training_seconds === 'number' ? `${item.metrics.training_seconds}s` : '—'}</td><td>{item.status === 'succeeded' && item.artifact_available ? <button className="table-action" onClick={() => register(item)} disabled={busy === item.id}>{busy === item.id ? 'Saving…' : 'Register model'}</button> : item.error ? <details className="error-details"><summary><CircleAlert size={14} /></summary><p>{item.error}</p></details> : null}</td></tr>)}</tbody></table>{!items.length && <div className="empty-state"><b>No experiment runs yet</b><span>Start a training run to populate model comparisons.</span><a className="inline-link" href="#training" onClick={event => { event.preventDefault(); window.dispatchEvent(new CustomEvent('news-nav', { detail: 'Model training' })) }}>Go to training <ExternalLink size={13} /></a></div>}</div>
    {items.some(item => item.confusion_matrix.labels.length) && <details className="confusion-details"><summary>Show confusion matrices <ChevronDown size={14} /></summary><div className="confusion-grid">{items.filter(item => item.confusion_matrix.labels.length).map(item => <div key={item.id}><h3>{item.name}</h3><table><tbody>{item.confusion_matrix.values.map((row, index) => <tr key={item.confusion_matrix.labels[index]}><th>{item.confusion_matrix.labels[index]}</th>{row.map((value, column) => <td key={column}>{value}</td>)}</tr>)}</tbody></table></div>)}</div></details>}
  </section>
}

function format(value?: number) { return typeof value === 'number' ? value.toFixed(4) : '—' }
