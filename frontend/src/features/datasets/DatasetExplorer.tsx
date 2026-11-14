import { useEffect, useState } from 'react'
import { Database, Search, SlidersHorizontal } from 'lucide-react'
import { apiGet } from '../../api'

type DatasetSummary = { article_count: number; category_count: number; categories: Record<string, number>; vocabulary_size: number; word_count: { min: number; median: number; max: number } }
type Article = { document_id: string; title: string; category: string; content_preview: string; word_count: number }
type ArticleResponse = { total: number; categories: string[]; items: Article[] }

export default function DatasetExplorer() {
  const [summary, setSummary] = useState<DatasetSummary | null>(null)
  const [data, setData] = useState<ArticleResponse | null>(null)
  const [category, setCategory] = useState('')
  const [query, setQuery] = useState('')
  const [appliedQuery, setAppliedQuery] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    apiGet<{ status: string } & DatasetSummary>('/api/v1/datasets/summary/')
      .then(setSummary).catch(reason => setError(reason instanceof Error ? reason.message : 'Dataset inspection failed.'))
  }, [])
  useEffect(() => {
    setLoading(true)
    const params = new URLSearchParams({ limit: '50' })
    if (category) params.set('category', category)
    if (appliedQuery) params.set('q', appliedQuery)
    apiGet<ArticleResponse>(`/api/v1/datasets/articles/?${params}`)
      .then(setData).catch(reason => setError(reason instanceof Error ? reason.message : 'Article search failed.'))
      .finally(() => setLoading(false))
  }, [category, appliedQuery])

  return <section className="data-explorer">
    <div className="metrics-grid explorer-metrics">
      <div className="metric-card"><div className="metric-top"><span>Articles in archive</span><Database size={17} /></div><div className="metric-value">{summary?.article_count.toLocaleString() ?? '—'}</div><div className="metric-note">Read from the configured local archive</div></div>
      <div className="metric-card"><div className="metric-top"><span>Source categories</span><SlidersHorizontal size={17} /></div><div className="metric-value">{summary?.category_count ?? '—'}</div><div className="metric-note">Original folder labels preserved</div></div>
      <div className="metric-card"><div className="metric-top"><span>Vocabulary</span><Search size={17} /></div><div className="metric-value">{summary?.vocabulary_size.toLocaleString() ?? '—'}</div><div className="metric-note">Unique whitespace-tokenized words</div></div>
    </div>
    <div className="panel explorer-panel"><div className="panel-heading"><div><div className="panel-kicker">ARCHIVE BROWSER</div><h2>Search real BBC documents</h2></div><span className="muted-tag">{data ? `${data.total.toLocaleString()} matches` : 'Waiting for dataset'}</span></div>
      <form className="explorer-controls" onSubmit={event => { event.preventDefault(); setAppliedQuery(query.trim()) }}><label><Search size={15} /><input value={query} onChange={event => setQuery(event.target.value)} placeholder="Search titles and article text" /></label><select value={category} onChange={event => setCategory(event.target.value)}><option value="">All categories</option>{data?.categories.map(item => <option key={item} value={item}>{item}</option>)}</select><button className="button primary" type="submit">Search archive</button></form>
      {error && <div className="page-error">{error}</div>}
      <div className="article-list">{loading ? <div className="empty-state">Loading documents…</div> : data?.items.length ? data.items.map(article => <article key={article.document_id} className="article-row"><div className="article-meta"><span className={`category-badge badge-${article.category.toLowerCase()}`}>{article.category}</span><span>{article.word_count.toLocaleString()} words</span></div><h3>{article.title}</h3><p>{article.content_preview}{article.content_preview.length >= 900 ? '…' : ''}</p><code>{article.document_id.slice(0, 16)}</code></article>) : <div className="empty-state"><div className="empty-icon"><Database size={20} /></div><b>No matching articles</b><span>Check the archive path or adjust the search.</span></div>}</div>
    </div>
  </section>
}
