import { useEffect, useState } from 'react'
import { BrainCircuit, CircleAlert, LoaderCircle, Play, RotateCw } from 'lucide-react'
import { apiGet, apiPost } from '../../api'

type Experiment = { id: string; name: string; algorithm: string; status: string; configuration: Record<string, unknown>; metrics: Record<string, number>; error: string; created_at: string }
const pause = (ms: number) => new Promise(resolve => setTimeout(resolve, ms))

export default function TrainingPage() {
  const [algorithm, setAlgorithm] = useState('naive_bayes')
  const [selector, setSelector] = useState('none')
  const [experiment, setExperiment] = useState<Experiment | null>(null)
  const [error, setError] = useState('')
  const [starting, setStarting] = useState(false)

  useEffect(() => {
    apiGet('/api/v1/experiments/').catch(() => undefined)
  }, [])

  useEffect(() => {
    if (!experiment || !['queued', 'running'].includes(experiment.status)) return
    let canceled = false
    const poll = async () => {
      try {
        await pause(1800)
        if (canceled) return
        const result = await apiGet<{ experiment: Experiment }>(`/api/v1/experiments/${experiment.id}/`)
        if (canceled) return
        setExperiment(result.experiment)
      } catch (reason) {
        if (!canceled) setError(reason instanceof Error ? reason.message : 'Could not read training status.')
      }
    }
    void poll()
    return () => { canceled = true }
  }, [experiment])

  const start = async () => {
    setStarting(true); setError('')
    try {
      const result = await apiPost<{ experiment: Experiment }>('/api/v1/experiments/train/', { algorithm, selector, test_size: 0.2, folds: 5, random_state: 42 })
      setExperiment(result.experiment)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Could not start training.')
    } finally { setStarting(false) }
  }

  return <section className="training-layout">
    <div className="panel training-config"><div className="panel-kicker">REPRODUCIBLE EXPERIMENT</div><h2>Train a classifier</h2><p>Every run uses a stratified 80/20 holdout. Hyperparameters are selected with stratified five-fold CV on the training split only.</p>
      <label className="field-label">Algorithm<select value={algorithm} onChange={event => setAlgorithm(event.target.value)}><option value="spark_naive_bayes">Spark MLlib · Multinomial Naive Bayes (distributed)</option><option value="naive_bayes">scikit-learn · Multinomial Naive Bayes</option><option value="knn">scikit-learn · K-Nearest Neighbors</option><option value="baseline">Majority-class baseline</option></select></label>
      <label className="field-label">Feature selection<select value={selector} onChange={event => setSelector(event.target.value)}><option value="none">No selection</option><option value="variance">Variance threshold</option><option value="chi2">Chi-square · top 500</option></select></label>
      <div className="config-pills"><span>{algorithm === 'spark_naive_bayes' ? 'Spark MLlib · distributed TF-IDF' : 'TF-IDF · 1–2 grams'}</span><span>Stratified 80 / 20 split</span><span>Stratified {algorithm === 'spark_naive_bayes' ? 'CV' : '5-fold CV'}</span></div>
      {error && <div className="page-error"><CircleAlert size={15} />{error}</div>}
      <button className="button primary train-button" onClick={start} disabled={starting || !!experiment && ['queued', 'running'].includes(experiment.status)}><Play size={15} />{starting ? 'Queueing…' : 'Start training'}</button>
      <div className="queue-note"><BrainCircuit size={16} /><span>{algorithm === 'spark_naive_bayes' ? 'Spark MLlib trains over distributed DataFrames. Start Redis, Celery, and a Java 17+ / PySpark worker; the registered model uses a compact Spark-compatible serving artifact.' : 'Training runs in a Celery worker. Start Redis and the worker before launching from this page.'}</span></div>
    </div>
    <div className="panel training-result"><div className="panel-heading"><div><div className="panel-kicker">RUN STATUS</div><h2>{experiment ? experiment.name : 'No run started'}</h2></div>{experiment && <span className={`run-status status-${experiment.status}`}>{experiment.status}</span>}</div>
      {!experiment ? <div className="empty-state"><div className="empty-icon"><BrainCircuit size={20} /></div><b>Ready when you are</b><span>Training output and test-set metrics will appear here.</span></div> : ['queued', 'running'].includes(experiment.status) ? <div className="running-state"><LoaderCircle className="spin" size={24} /><b>{experiment.status === 'queued' ? 'Waiting for a worker' : 'Training and evaluating'}</b><span>Progress updates are read from the job record.</span></div> : experiment.status === 'failed' ? <div className="page-error"><CircleAlert size={15} />{experiment.error || 'Training failed. Open experiment history for details.'}</div> : <div className="result-content"><div className="result-highlight"><span>Test macro F1</span><strong>{(experiment.metrics.f1_macro ?? 0).toFixed(4)}</strong><small>Test metrics are calculated once on the held-out 20%.</small></div><div className="result-metrics"><Metric label="Accuracy" value={experiment.metrics.accuracy} /><Metric label="Macro precision" value={experiment.metrics.precision_macro} /><Metric label="Macro recall" value={experiment.metrics.recall_macro} /><Metric label="CV macro F1" value={experiment.metrics.cv_f1_macro} /></div><div className="result-foot"><span>{experiment.metrics.train_documents} train · {experiment.metrics.test_documents} test</span><span>{experiment.metrics.cv_folds}-fold CV · {experiment.metrics.training_seconds}s</span></div><a className="inline-link" href="#experiments" onClick={event => { event.preventDefault(); window.dispatchEvent(new CustomEvent('news-nav', { detail: 'Experiments' })) }}>Open experiment history <RotateCw size={13} /></a></div>}
    </div>
  </section>
}

function Metric({ label, value }: { label: string; value?: number }) {
  return <div><span>{label}</span><b>{typeof value === 'number' ? value.toFixed(4) : '—'}</b></div>
}
