import { useEffect, useState } from 'react'
import { BadgeCheck, CircleAlert, ShieldCheck } from 'lucide-react'
import { apiGet, apiPost } from '../../api'

type Model = { id: string; name: string; version: number; algorithm: string; is_active: boolean; metrics: Record<string, number>; created_at: string; experiment_id: string }

export default function ModelRegistry() {
  const [items, setItems] = useState<Model[]>([])
  const [error, setError] = useState('')
  const [busy, setBusy] = useState('')
  const load = () => apiGet<{ items: Model[] }>('/api/v1/models/').then(result => setItems(result.items)).catch(reason => setError(reason.message))
  useEffect(() => { void load() }, [])
  const activate = async (item: Model) => {
    setBusy(item.id); setError('')
    try { await apiPost(`/api/v1/models/${item.id}/activate/`); await load() }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'Could not activate model.') }
    finally { setBusy('') }
  }
  return <section className="panel table-panel"><div className="panel-heading"><div><div className="panel-kicker">MODEL VERSIONS</div><h2>Registry</h2></div><span className="muted-tag">{items.length} registered</span></div><p className="section-description">Artifacts stay on disk. One registered version is active for predictions at a time.</p>{error && <div className="page-error"><CircleAlert size={14} />{error}</div>}
    <div className="registry-grid">{items.map(item => <article className={`registry-card ${item.is_active ? 'registry-active' : ''}`} key={item.id}><div className="registry-card-top"><span className="registry-icon"><ShieldCheck size={18} /></span>{item.is_active && <span className="active-label"><BadgeCheck size={13} />ACTIVE</span>}</div><h3>{item.name} <small>v{item.version}</small></h3><p>{item.algorithm.replace('_', ' ')} · registered {new Date(item.created_at).toLocaleDateString()}</p><div className="registry-score"><span>Test macro F1</span><b>{typeof item.metrics.f1_macro === 'number' ? item.metrics.f1_macro.toFixed(4) : '—'}</b></div><button className={item.is_active ? 'button secondary' : 'button primary'} disabled={item.is_active || busy === item.id} onClick={() => activate(item)}>{item.is_active ? 'Active for predictions' : busy === item.id ? 'Activating…' : 'Activate version'}</button></article>)}</div>{!items.length && <div className="empty-state"><div className="empty-icon"><ShieldCheck size={20} /></div><b>No models registered</b><span>Register a successful experiment to create a version.</span></div>}
  </section>
}
