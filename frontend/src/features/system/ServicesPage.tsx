import { useCallback, useEffect, useState } from 'react'
import { Activity, CircleAlert, Database, RefreshCw, ServerCog } from 'lucide-react'
import { apiGet } from '../../api'

type Service = { name: string; status: string; detail: string; version?: string }
type Job = { id: string; kind: string; status: string; name: string; created_at: string }

export default function ServicesPage() {
  const [services, setServices] = useState<Service[]>([])
  const [jobs, setJobs] = useState<Job[]>([])
  const [error, setError] = useState('')
  const refresh = useCallback(async () => {
    try {
      const [serviceResult, jobResult] = await Promise.all([
        apiGet<{ services: Service[] }>('/api/v1/system/services/'),
        apiGet<{ items: Job[] }>('/api/v1/system/jobs/'),
      ])
      setServices(serviceResult.services); setJobs(jobResult.items); setError('')
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'Could not inspect system services.') }
  }, [])
  useEffect(() => { void refresh(); const timer = window.setInterval(() => void refresh(), 10000); return () => window.clearInterval(timer) }, [refresh])
  return <section className="system-page"><div className="panel service-status-panel"><div className="panel-heading"><div><div className="panel-kicker">LIVE SERVICE CHECKS</div><h2>Connected services</h2></div><button className="icon-button" onClick={() => void refresh()} title="Refresh"><RefreshCw size={16} /></button></div>{error && <div className="page-error"><CircleAlert size={14} />{error}</div>}<div className="service-status-grid">{services.map(service => <article className="service-status-card" key={service.name}><div className="service-status-top"><span className="status-symbol"><ServerCog size={18} /></span><span className={`service-badge status-${service.status}`}>{service.status.replace('_', ' ')}</span></div><h3>{service.name}</h3><p>{service.detail}</p>{service.version && <small>Version {service.version}</small>}</article>)}</div></div>
    <div className="panel jobs-panel"><div className="panel-heading"><div><div className="panel-kicker">BACKGROUND WORK</div><h2>Running jobs</h2></div><span className="muted-tag">{jobs.length}</span></div>{jobs.map(job => <div className="job-row" key={job.id}><span className="job-icon"><Activity size={15} /></span><div><b>{job.name}</b><small>{job.kind} · {new Date(job.created_at).toLocaleString()}</small></div><span className={`run-status status-${job.status}`}>{job.status}</span></div>)}{!jobs.length && <div className="empty-state compact-empty"><div className="empty-icon"><Database size={18} /></div><b>No queued or running jobs</b></div>}</div></section>
}
