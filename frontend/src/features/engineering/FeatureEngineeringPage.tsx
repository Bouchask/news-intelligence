import { useEffect, useState } from 'react'
import { CircleAlert, Layers3, Play, Sparkles } from 'lucide-react'
import { apiGet, apiPost } from '../../api'

type Topic = { topic_id: number; terms: { term: string; weight: number }[] }
type TopicRun = { id: string; status: string; num_topics: number; max_iter: number; results: { topics?: Topic[]; document_count?: number; vocabulary_size?: number }; error: string }

export default function FeatureEngineeringPage() {
  const [runs, setRuns] = useState<TopicRun[]>([])
  const [current, setCurrent] = useState<TopicRun | null>(null)
  const [numTopics, setNumTopics] = useState(8)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const load = () => apiGet<{ items: TopicRun[] }>('/api/v1/analytics/topics/').then(result => { setRuns(result.items); if (!current && result.items[0]) setCurrent(result.items[0]) }).catch(reason => setError(reason.message))
  useEffect(() => { void load() }, [])
  useEffect(() => {
    if (!current || !['queued', 'running'].includes(current.status)) return
    let canceled = false
    const poll = async () => {
      await new Promise(resolve => setTimeout(resolve, 2000))
      if (canceled) return
      try {
        const response = await apiGet<{ topic_run: TopicRun }>(`/api/v1/analytics/topics/${current.id}/`)
        if (!canceled) setCurrent(response.topic_run)
      } catch (reason) { if (!canceled) setError(reason instanceof Error ? reason.message : 'Could not check topic job.') }
    }
    void poll()
    return () => { canceled = true }
  }, [current])

  const run = async () => {
    setBusy(true); setError('')
    try {
      const response = await apiPost<{ topic_run: TopicRun }>('/api/v1/analytics/topics/run/', { num_topics: numTopics, max_iter: 30 })
      setCurrent(response.topic_run)
      setRuns(previous => [response.topic_run, ...previous])
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'Could not start Spark LDA.') }
    finally { setBusy(false) }
  }

  return <section className="features-layout"><div className="feature-summary-grid"><div className="panel feature-card"><span className="feature-card-icon"><Layers3 size={18} /></span><div><div className="panel-kicker">TERM FREQUENCIES</div><h2>TF-IDF</h2><p>Built during each training fold; the fitted vocabulary is saved with the model artifact.</p></div></div><div className="panel feature-card"><span className="feature-card-icon topic"><Sparkles size={18} /></span><div><div className="panel-kicker">LATENT TOPIC MODEL</div><h2>Spark MLlib LDA</h2><p>Uses CountVectorizer term counts, keeping LDA input nonnegative as required.</p></div></div></div>
    <div className="panel topic-control"><div><div className="panel-kicker">TOPIC DISCOVERY</div><h2>Train LDA on the BBC archive</h2><p>The Spark job runs in the Celery worker and saves model plus per-document topic distributions.</p></div><div className="topic-actions"><label>Topics<select value={numTopics} onChange={event => setNumTopics(Number(event.target.value))}>{[5, 8, 10, 12, 15].map(count => <option key={count} value={count}>{count}</option>)}</select></label><button className="button primary" disabled={busy || !!current && ['queued', 'running'].includes(current.status)} onClick={run}><Play size={14} />{busy ? 'Queueing…' : 'Run Spark LDA'}</button></div>{error && <div className="page-error"><CircleAlert size={14} />{error}</div>}</div>
    {current && ['queued', 'running'].includes(current.status) && <div className="panel topic-progress"><span className="spin-dot" /><b>{current.status === 'queued' ? 'Waiting for a worker' : 'Spark is fitting the topic model'}</b><span>Job {current.id.slice(0, 8)}</span></div>}
    {current?.status === 'failed' && <div className="page-error"><CircleAlert size={14} />{current.error || 'Spark topic job failed.'}</div>}
    {current?.status === 'succeeded' && <><div className="topic-run-meta"><span>{current.results.document_count?.toLocaleString()} documents</span><span>{current.results.vocabulary_size?.toLocaleString()} terms in vocabulary</span><span>{current.num_topics} topics</span></div><div className="topic-grid">{(current.results.topics ?? []).map(topic => <article className="panel topic-card" key={topic.topic_id}><div className="topic-card-head"><span>TOPIC {String(topic.topic_id + 1).padStart(2, '0')}</span><span>{topic.terms.length} terms</span></div><div className="topic-terms">{topic.terms.map(item => <div className="topic-term" key={item.term}><span>{item.term}</span><div><i style={{ width: `${Math.max(4, item.weight / Math.max(...topic.terms.map(term => term.weight)) * 100)}%` }} /></div><b>{item.weight.toFixed(3)}</b></div>)}</div></article>)}</div></>}
    {!current && runs.length === 0 && <div className="panel empty-state topic-empty"><div className="empty-icon"><Layers3 size={20} /></div><b>No topic model has been run</b><span>Start Spark and a Celery worker to discover topics from the archive.</span></div>}
  </section>
}
