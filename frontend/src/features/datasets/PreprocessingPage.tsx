import { FormEvent, useState } from 'react'
import { CircleAlert, Sparkles } from 'lucide-react'
import { apiPost } from '../../api'

type Result = { original_text: string; cleaned_text: string; tokens: string[]; stopwords_removed: string[]; processed_tokens: string[]; processed_text: string; token_count: number; processed_token_count: number; method: string; lemmatized: boolean }

export default function PreprocessingPage() {
  const [text, setText] = useState('')
  const [result, setResult] = useState<Result | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const submit = async (event: FormEvent) => {
    event.preventDefault(); setBusy(true); setError(''); setResult(null)
    try { setResult(await apiPost<Result>('/api/v1/pipelines/preprocess/', { text })) }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'Preprocessing failed.') }
    finally { setBusy(false) }
  }
  return <section className="preprocess-layout"><form className="panel preprocess-input" onSubmit={submit}><div className="panel-kicker">TEXT PREPARATION</div><h2>Inspect preprocessing</h2><p>Preview the same cleanup decisions used by the classifier, with the active spaCy capability reported explicitly.</p><label className="field-label">Article text<textarea required maxLength={50000} rows={12} value={text} onChange={event => setText(event.target.value)} placeholder="Paste text or an excerpt from a dataset article…" /></label><div className="form-footer"><span>{text.length.toLocaleString()} / 50,000 characters</span><button className="button primary" disabled={busy || !text.trim()}><Sparkles size={15} />{busy ? 'Processing…' : 'Process text'}</button></div>{error && <div className="page-error"><CircleAlert size={14} />{error}</div>}</form>
    {result ? <div className="preprocess-results"><div className="metrics-grid explorer-metrics"><div className="metric-card"><div className="metric-top"><span>Input tokens</span><Sparkles size={16} /></div><div className="metric-value">{result.token_count}</div><div className="metric-note">After punctuation and URL cleanup</div></div><div className="metric-card"><div className="metric-top"><span>Processed tokens</span><Sparkles size={16} /></div><div className="metric-value">{result.processed_token_count}</div><div className="metric-note">Stopwords removed</div></div></div><div className="panel preprocess-output"><div className="panel-kicker">CLEANED TEXT</div><p className="preprocess-text">{result.cleaned_text || 'No text remained after cleanup.'}</p><div className="panel-kicker tokens-kicker">PROCESSED TOKENS</div><div className="token-cloud">{result.processed_tokens.slice(0, 180).map((token, index) => <span key={`${token}-${index}`}>{token}</span>)}</div><div className={`lemmatizer-note ${result.lemmatized ? 'note-ready' : 'note-limited'}`}>{result.method}</div></div><div className="panel removed-words"><div className="panel-kicker">STOPWORDS REMOVED · {result.stopwords_removed.length}</div><p>{result.stopwords_removed.slice(0, 80).join(' · ') || 'No English stopwords found.'}</p></div></div> : <div className="panel preprocess-placeholder"><div className="empty-icon"><Sparkles size={20} /></div><b>Preview each text transformation</b><span>Original text stays separate from the processed output.</span></div>}
  </section>
}
