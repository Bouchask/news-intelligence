import { useEffect, useState } from 'react'
import { Activity, Archive, ArrowDownToLine, BookOpenText, Boxes, BrainCircuit, Cable, ChartNoAxesCombined, ChevronDown, CircleHelp, Command, Database, FileChartColumn, FlaskConical, Gauge, Layers3, ListFilter, Menu, Network, Search, Settings2, ShieldCheck, Sparkles, Workflow } from 'lucide-react'
import LiveFeed from './features/live/LiveFeed'
import DatasetExplorer from './features/datasets/DatasetExplorer'
import TrainingPage from './features/experiments/TrainingPage'
import ExperimentHistory from './features/experiments/ExperimentHistory'
import ModelRegistry from './features/experiments/ModelRegistry'
import PredictionsPage from './features/predictions/PredictionsPage'
import PreprocessingPage from './features/datasets/PreprocessingPage'
import FeatureEngineeringPage from './features/engineering/FeatureEngineeringPage'
import ServicesPage from './features/system/ServicesPage'
import StreamingPage from './features/system/StreamingPage'
import { apiGet } from './api'

type Health = { status: string; database: string }
type Dataset = { status: 'available'; article_count: number; category_count: number; categories: Record<string, number>; word_count: { min: number; median: number; max: number }; vocabulary_size: number }
const navigation = [
  { section: 'WORKSPACE', items: [
    { label: 'Overview', icon: Gauge }, { label: 'Dataset explorer', icon: Database }, { label: 'Ingestion', icon: ArrowDownToLine },
  ] },
  { section: 'MACHINE LEARNING', items: [
    { label: 'Preprocessing', icon: Sparkles }, { label: 'Features & topics', icon: Layers3 }, { label: 'Model training', icon: BrainCircuit }, { label: 'Model comparison', icon: FlaskConical }, { label: 'Experiment history', icon: FileChartColumn }, { label: 'Model registry', icon: ShieldCheck },
  ] },
  { section: 'OPERATIONS', items: [
    { label: 'BBC Live Feed', icon: Cable }, { label: 'Predictions', icon: FileChartColumn }, { label: 'Streaming', icon: Cable }, { label: 'System health', icon: Activity },
  ] },
]

type Overview = {
  dataset: { article_count: number; category_count: number; categories: Record<string, number>; vocabulary_size: number; word_count: { median: number } } | null
  processed_articles: number
  pending_jobs: number
  active_model: { id: string; name: string; version: number; metrics: Record<string, number> } | null
  best_model_f1_macro: number | null
  latest_experiment: { id: string; name: string; algorithm: string; status: string; metrics: Record<string, number>; created_at: string } | null
  prediction_count: number
  average_prediction_latency_ms: number | null
  live_news_items: number
}

function App() {
  const [health, setHealth] = useState<Health | null>(null)
  const [dataset, setDataset] = useState<Dataset | null>(null)
  const [overview, setOverview] = useState<Overview | null>(null)
  const [active, setActive] = useState('Overview')
  const [sidebarOpen, setSidebarOpen] = useState(false)

  useEffect(() => {
    fetch('/api/v1/system/health/')
      .then(async response => {
        const body = await response.json()
        setHealth(body)
      })
      .catch(() => setHealth({ status: 'offline', database: 'unavailable' }))
    fetch('/api/v1/datasets/summary/')
      .then(async response => response.ok ? await response.json() as Dataset : null)
      .then(data => setDataset(data?.status === 'available' ? data : null))
      .catch(() => setDataset(null))
    apiGet<Overview>('/api/v1/dashboard/overview/').then(setOverview).catch(() => setOverview(null))
  }, [])

  useEffect(() => {
    const handleNav = (event: Event) => setActive((event as CustomEvent<string>).detail)
    window.addEventListener('news-nav', handleNav)
    return () => window.removeEventListener('news-nav', handleNav)
  }, [])

  return <div className="app-shell">
    <aside className={`sidebar ${sidebarOpen ? 'sidebar-open' : ''}`}>
      <div className="brand"><div className="brand-mark"><Network size={19} strokeWidth={2.1} /></div><div><strong>Signal<span>Desk</span></strong><small>NEWS INTELLIGENCE</small></div><button className="mobile-close" onClick={() => setSidebarOpen(false)}>×</button></div>
      <button className="workspace"><div className="workspace-avatar">N</div><div className="workspace-copy"><b>News Intelligence</b><small>Local workspace</small></div><ChevronDown size={15} /></button>
      <div className="nav-scroll">{navigation.map(group => <section className="nav-group" key={group.section}><div className="nav-label">{group.section}</div>{group.items.map(item => <button key={item.label} className={`nav-item ${active === item.label ? 'selected' : ''}`} onClick={() => { setActive(item.label); setSidebarOpen(false) }}><item.icon size={17} strokeWidth={1.8} /><span>{item.label}</span>{item.label === 'Streaming' && <i className="nav-dot" />}</button>)}</section>)}</div>
      <div className="sidebar-bottom"><div className="storage-card"><div className="storage-top"><span>PROJECT STATUS</span><span className="status-pill"><i />In setup</span></div><div className="storage-track"><span /></div><p>Foundation is being assembled</p></div><button className="nav-item"><Settings2 size={17} /><span>Settings</span></button><button className="profile"><div className="profile-avatar">A</div><div><b>Administrator</b><small>Local account</small></div><ChevronDown size={15} /></button></div>
    </aside>
    {sidebarOpen && <button aria-label="Close navigation" className="scrim" onClick={() => setSidebarOpen(false)} />}
    <main className="main-area">
      <header className="topbar"><div className="crumb"><button className="menu-button" onClick={() => setSidebarOpen(true)}><Menu size={19} /></button><span>Workspace</span><b>/</b><strong>{active}</strong></div><div className="top-actions"><label className="search-box"><Search size={16} /><input placeholder="Search workspace" /><kbd>⌘ K</kbd></label><button className="icon-button" title="Help"><CircleHelp size={18} /></button><div className="top-divider" /><div className="avatar-small">A</div></div></header>
      <div className="content-wrap">
        <div className="page-heading"><div><div className="eyebrow"><span className="eyebrow-line" /> {active === 'BBC Live Feed' ? 'LIVE NEWS' : active === 'Overview' ? 'INTELLIGENCE OVERVIEW' : 'WORKSPACE'}</div><h1>{active === 'Overview' ? 'Good morning.' : active}<span className="heading-period">{active === 'Overview' ? ' Your workspace is ready to take shape.' : ''}</span></h1><p>{active === 'BBC Live Feed' ? 'Fetch the current English-language BBC headline snapshot and save it locally.' : active === 'Overview' ? 'Track your archive, experiments, active model, and recent predictions.' : `Work with ${active.toLowerCase()} using data from your local workspace.`}</p></div>{active === 'Overview' && <div className="heading-actions"><button className="button secondary" onClick={() => setActive('Experiment history')}><BookOpenText size={16} />Experiments</button><button className="button primary" onClick={() => setActive('Ingestion')}><ArrowDownToLine size={16} />Explore dataset</button></div>}</div>
        {active === 'BBC Live Feed' ? <LiveFeed /> : active === 'Dataset explorer' || active === 'Ingestion' ? <DatasetExplorer /> : active === 'Preprocessing' ? <PreprocessingPage /> : active === 'Features & topics' ? <FeatureEngineeringPage /> : active === 'Model training' ? <TrainingPage /> : active === 'Experiment history' || active === 'Model comparison' ? <ExperimentHistory /> : active === 'Model registry' ? <ModelRegistry /> : active === 'Predictions' ? <PredictionsPage /> : active === 'Streaming' ? <StreamingPage /> : active === 'System health' ? <ServicesPage /> : <>
        <section className="metrics-grid">
          <Metric icon={Archive} label="Articles indexed" value={overview?.dataset?.article_count.toLocaleString() ?? '—'} note={overview?.dataset ? 'Read from the configured archive' : 'Archive unavailable'} />
          <Metric icon={ChartNoAxesCombined} label="News categories" value={overview?.dataset ? String(overview.dataset.category_count) : '—'} note={overview?.dataset ? 'Original archive labels' : 'Archive unavailable'} />
          <Metric icon={BrainCircuit} label="Best test macro F1" value={overview?.best_model_f1_macro == null ? '—' : overview.best_model_f1_macro.toFixed(4)} note="Best completed holdout result" />
          <Metric icon={ShieldCheck} label="Active model" value={overview?.active_model ? `${overview.active_model.name} v${overview.active_model.version}` : 'None'} note={overview?.active_model ? 'Ready for predictions' : 'Register and activate a run'} />
        </section>
        <section className="main-grid">
          <div className="panel pipeline-panel"><div className="panel-heading"><div><div className="panel-kicker">YOUR WORKFLOW</div><h2>From archive to insight</h2></div><button className="quiet-button"><ListFilter size={15} /> All stages</button></div><div className="pipeline-list">
            <PipelineStep number="01" icon={Database} title="Connect your dataset" detail="Inspect and validate the BBC News archive" state="Next step" active onClick={() => setActive('Ingestion')} />
            <PipelineStep number="02" icon={Workflow} title="Prepare & explore" detail="Clean text and review corpus statistics" state="Locked" />
            <PipelineStep number="03" icon={Boxes} title="Build representations" detail="Generate TF-IDF features and discover topics" state="Locked" />
            <PipelineStep number="04" icon={BrainCircuit} title="Train & compare models" detail="Evaluate classifiers with reproducible folds" state="Locked" />
          </div><div className="pipeline-footer"><span><span className="legend-dot active-dot" />Ready to configure</span><span><span className="legend-dot" />Needs previous step</span><button onClick={() => setActive('Ingestion')}>Start with ingestion <span>→</span></button></div></div>
          <div className="right-stack"><div className="panel system-panel"><div className="panel-heading"><div><div className="panel-kicker">SYSTEM HEALTH</div><h2>Services</h2></div><button className="more-button">···</button></div><div className="service-row"><div className="service-icon spark"><Sparkles size={17} /></div><div className="service-copy"><b>Spark engine</b><small>Version 4.2.0 detected</small></div><span className="service-state"><i className="state-warn" />Needs runtime check</span></div><div className="service-row"><div className="service-icon api"><Command size={17} /></div><div className="service-copy"><b>Django API</b><small>Local service</small></div><span className="service-state"><i className={health?.status === 'ok' ? '' : 'state-idle'} />{health?.status === 'ok' ? 'Operational' : 'Not connected'}</span></div><div className="service-row"><div className="service-icon kafka"><Cable size={17} /></div><div className="service-copy"><b>Event streaming</b><small>Kafka cluster</small></div><span className="service-state"><i className="state-idle" />Not configured</span></div><button className="panel-link" onClick={() => setActive('System health')}>View system details <span>→</span></button></div>
          <div className="tip-card"><div className="tip-icon"><FlaskConical size={17} /></div><div><b>Built for reproducible research</b><p>Every experiment will keep its dataset, feature settings, and evaluation folds together.</p></div></div></div>
        </section>
        <section className="bottom-grid"><div className="panel empty-panel"><div className="panel-heading"><div><div className="panel-kicker">DATASET SNAPSHOT</div><h2>Corpus distribution</h2></div><span className="muted-tag">{dataset ? `${dataset.category_count} categories` : 'No dataset'}</span></div>{dataset ? <div className="distribution-list">{Object.entries(dataset.categories).sort((a, b) => b[1] - a[1]).map(([category, count]) => <div className="distribution-row" key={category}><div><b>{category}</b><span>{count.toLocaleString()} articles</span></div><div className="distribution-track"><i style={{ width: `${Math.max(3, count / dataset.article_count * 100)}%` }} /></div><strong>{Math.round(count / dataset.article_count * 100)}%</strong></div>)}<div className="distribution-summary">Vocabulary <b>{dataset.vocabulary_size.toLocaleString()}</b><span>Median length <b>{dataset.word_count.median.toLocaleString()} words</b></span></div></div> : <div className="empty-state"><div className="empty-icon"><Database size={21} /></div><b>Your dataset story starts here</b><p>Configure the BBC archive path to see category balance, document counts, and text length at a glance.</p><button onClick={() => setActive('Ingestion')}>Go to ingestion <span>→</span></button></div>}</div><div className="panel activity-panel"><div className="panel-heading"><div><div className="panel-kicker">RECENT ACTIVITY</div><h2>Workspace activity</h2></div><button className="text-button" onClick={() => setActive('Experiment history')}>History</button></div><div className="activity-empty">{overview?.latest_experiment && <div className="activity-line"><div className="activity-node"><FlaskConical size={14} /></div><div><b>{overview.latest_experiment.name}</b><p>Latest run · {overview.latest_experiment.status}{overview.latest_experiment.metrics.f1_macro !== undefined ? ` · Macro F1 ${overview.latest_experiment.metrics.f1_macro.toFixed(4)}` : ''}</p></div><time>{new Date(overview.latest_experiment.created_at).toLocaleDateString()}</time></div>}<div className="activity-line faint"><div className="activity-node"><FileChartColumn size={14} /></div><div><b>{overview?.prediction_count ?? 0} predictions saved</b><p>{overview?.average_prediction_latency_ms == null ? 'No measured prediction latency yet' : `Mean latency ${overview.average_prediction_latency_ms.toFixed(1)} ms`}</p></div></div><div className="activity-line faint"><div className="activity-node"><Cable size={14} /></div><div><b>{overview?.live_news_items ?? 0} live BBC feed items</b><p>Saved from explicit API imports</p></div></div></div></div></section>
        <footer><span>SignalDesk <i>·</i> Local development</span><span>Dataset metrics populate only from your imported data.</span></footer>
        </>}
      </div>
    </main>
  </div>
}

function Metric({ icon: Icon, label, value, note, status }: { icon: typeof Gauge; label: string; value: string; note: string; status?: boolean }) {
  return <div className="metric-card"><div className="metric-top"><span>{label}</span><Icon size={17} /></div><div className={`metric-value ${value === 'None' ? 'value-none' : ''}`}>{value}</div><div className="metric-note">{status !== undefined && <i className={status ? 'state-ok' : 'state-idle'} />}{note}</div></div>
}
function PipelineStep({ number, icon: Icon, title, detail, state, active, onClick }: { number: string; icon: typeof Gauge; title: string; detail: string; state: string; active?: boolean; onClick?: () => void }) {
  return <button className={`pipeline-step ${active ? 'step-active' : ''}`} onClick={onClick} disabled={!active}><span className="step-number">{number}</span><span className={`step-icon ${active ? 'step-icon-active' : ''}`}><Icon size={17} /></span><span className="step-copy"><b>{title}</b><small>{detail}</small></span><span className={`step-state ${active ? 'next-state' : ''}`}>{state}</span><span className="step-arrow">→</span></button>
}
export default App
