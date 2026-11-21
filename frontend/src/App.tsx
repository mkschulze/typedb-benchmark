import { useEffect, useRef, useState } from 'react';
import type { DividendCase as Case, Configuration, Health, Model, Run, RunRequest, Source, TaxAnswer, Trial } from './types';

type Page = 'demonstration' | 'benchmark' | 'sources';
type Evidence = { answer: TaxAnswer; trial?: Trial; caseId: string; title: string };

const active = (run: Run | null) => !!run && ['queued', 'running'].includes(run.status);
const human = (value: string) => value.replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
const money = (cents: number | null | undefined) => cents == null ? 'Undetermined' : new Intl.NumberFormat('en-DE', { style: 'currency', currency: 'EUR', maximumFractionDigits: 2 }).format(cents / 100);
const count = (value: number | null | undefined) => value == null ? 'Unavailable' : new Intl.NumberFormat('en').format(Math.round(value));
const duration = (value: number | null | undefined) => value == null ? 'Unavailable' : `${(value / 1000).toFixed(2)} s`;
const date = (value: string) => { const parsed = new Date(value); return Number.isNaN(parsed.getTime()) ? value : new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' }).format(parsed); };
const totalTokens = (trial: Trial) => trial.metrics.input_tokens == null || trial.metrics.output_tokens == null ? null : trial.metrics.input_tokens + trial.metrics.output_tokens;

async function api<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, { ...options, headers: { 'Content-Type': 'application/json', ...options?.headers } });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(typeof body?.detail === 'string' ? body.detail : `Request failed (${response.status}). Please retry.`);
  }
  return response.json() as Promise<T>;
}

function Icon({ name, size = 18 }: { name: 'arrow' | 'external' | 'close' | 'check' | 'document' | 'chevron' | 'download' | 'database'; size?: number }) {
  const paths: Record<string, React.ReactNode> = {
    arrow: <><path d="M4 12h16M14 6l6 6-6 6" /></>,
    external: <><path d="M14 4h6v6M20 4l-9 9" /><path d="M10 5H5v14h14v-5" /></>,
    close: <path d="m6 6 12 12M18 6 6 18" />,
    check: <path d="m5 12 4 4L19 6" />,
    document: <><path d="M13 3H5v18h14V9l-6-6Z" /><path d="M13 3v6h6M8 13h8M8 17h6" /></>,
    chevron: <path d="m8 5 7 7-7 7" />,
    download: <><path d="M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5" /></>,
    database: <><ellipse cx="12" cy="5" rx="8" ry="3" /><path d="M4 5v14c0 4 16 4 16 0V5M4 12c0 4 16 4 16 0" /></>,
  };
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name]}</svg>;
}

function Badge({ children, tone = 'neutral' }: { children: React.ReactNode; tone?: 'neutral' | 'green' | 'amber' | 'red' }) {
  return <span className={`badge ${tone}`}>{children}</span>;
}

function Facts({ facts }: { facts: Record<string, unknown> }) {
  return <dl className="facts-list">{Object.entries(facts).map(([key, value]) => <div key={key}><dt>{human(key)}</dt><dd>{value == null ? <span className="unknown">Unknown</span> : typeof value === 'boolean' ? value ? 'Yes' : 'No' : typeof value === 'object' ? <pre className="fact-object">{JSON.stringify(value, null, 2)}</pre> : String(value)}</dd></div>)}</dl>;
}

function CasePanel({ payment }: { payment: Case }) {
  return <section className="case-panel" aria-labelledby="case-heading">
    <div className="section-heading"><h2 id="case-heading">The dividend case</h2><Badge>Synthetic</Badge></div>
    <h3 className="case-title">{payment.title}</h3>
    <p className="muted case-summary">{payment.summary}</p>
    <div className="payment-amount"><span>Gross dividend</span><strong>{money(payment.gross_amount_cents)}</strong></div>
    <div className="ownership-flow">
      <div className="party"><span className="country-code">{payment.payer.country}</span><div><span className="field-caption">German payer</span><strong>{payment.payer.name}</strong>{payment.payer.legal_form && <span>{payment.payer.legal_form}</span>}</div></div>
      <div className="flow-connector"><span /><span>Dividend payment</span><Icon name="arrow" size={16} /></div>
      <div className="party"><span className="country-code">{payment.recipient.country}</span><div><span className="field-caption">Corporate recipient</span><strong>{payment.recipient.name}</strong>{payment.recipient.legal_form && <span>{payment.recipient.legal_form}</span>}</div></div>
    </div>
    <dl className="date-facts"><div><dt>Payment date</dt><dd>{date(payment.payment_date)}</dd></div><div><dt>Information cutoff</dt><dd>{date(payment.knowledge_date)}</dd></div><div><dt>Dataset split</dt><dd>{human(payment.split)}</dd></div></dl>
    <div className="question"><h3>The question</h3><p>{payment.question}</p></div>
    <details className="case-details"><summary>View all case facts <span>{Object.keys(payment.facts).length}</span></summary><Facts facts={payment.facts} /></details>
    <details className="case-details"><summary>Supporting documents <span>{payment.documents.length}</span></summary>{payment.documents.map((document) => <article className="document-preview" key={document.id}><h4><Icon name="document" size={16} />{document.title}</h4><p>{document.text}</p></article>)}</details>
  </section>;
}

function AnswerSummary({ answer }: { answer: TaxAnswer }) {
  return <>
    <div className="answer-outcome"><div><span className="field-caption">Withholding at payment</span><strong>{money(answer.total_withholding_cents)}</strong></div><Badge tone={answer.status === 'determined' ? 'green' : 'amber'}>{human(answer.status)}</Badge></div>
    <dl className="answer-figures"><div><dt>Withholding tax</dt><dd>{money(answer.withholding_tax_cents)}</dd></div><div><dt>Solidarity surcharge</dt><dd>{money(answer.solidarity_surcharge_cents)}</dd></div><div className="net-payment"><dt>Net payment</dt><dd>{money(answer.net_payment_cents)}</dd></div></dl>
    <div className="relief-row"><div><span className="field-caption">Relief eligibility</span><strong>{human(answer.relief_eligibility)}</strong></div><div><span className="field-caption">Relief route</span><strong>{answer.relief_route ? answer.relief_route === 'section43b' ? 'EStG §43b · EU parent-company relief' : human(answer.relief_route) : 'Undetermined'}</strong></div></div>
    <p className="answer-reasoning">{answer.reasoning}</p>
    {answer.missing_facts.length > 0 && <div className="notice amber-notice"><strong>Information needed</strong><ul>{answer.missing_facts.map((fact) => <li key={fact}>{human(fact)}</li>)}</ul></div>}
    <dl className="refund-row"><div><dt>Refund route</dt><dd>{human(answer.refund_status)}</dd></div><div><dt>Possible refund</dt><dd>{money(answer.refund_amount_cents)}</dd></div></dl>
  </>;
}

function ReferencePanel({ answer, loading, error, onInspect }: { answer: TaxAnswer | null; loading: boolean; error: string; onInspect: () => void }) {
  return <section className="reference-panel" aria-labelledby="reference-heading">
    <div className="section-heading"><h2 id="reference-heading">Reference walkthrough</h2><Badge tone="amber">Provisional</Badge></div>
    <p className="panel-intro">Explore the expected decision before running a model. This deterministic walkthrough has no measured LLM results.</p>
    {loading ? <div className="skeleton-block" aria-label="Loading reference walkthrough"><div /><div /><div /></div> : error ? <div role="alert" className="notice error-notice">{error}</div> : answer && <>
      <AnswerSummary answer={answer} />
      <button className="text-button evidence-button" onClick={onInspect}>Inspect reference evidence <Icon name="arrow" /></button>
    </>}
    <div className="decision-note"><Icon name="document" size={20} /><p><strong>Eligibility and withholding are separate decisions.</strong> Relief may be available even when the payer must withhold at the payment date.</p></div>
  </section>;
}

function RunProgress({ run, onCancel }: { run: Run; onCancel: () => void }) {
  return <div className="run-progress"><div className="run-progress-copy"><Badge tone={active(run) ? 'green' : run.status === 'failed' ? 'red' : 'neutral'}>{human(run.status)}</Badge><span>{run.completed_trials} of {run.total_trials} trials complete</span>{active(run) && <button className="text-button cancel-button" onClick={onCancel}>Cancel run</button>}</div><progress aria-label="Run progress" value={run.completed_trials} max={Math.max(run.total_trials, 1)} /></div>;
}

function TrialTable({ trials, configurations, models, cases, inspect, includeCase = false }: { trials: Trial[]; configurations: Configuration[]; models: Model[]; cases: Case[]; inspect: (trial: Trial) => void; includeCase?: boolean }) {
  return <div className="table-scroll" tabIndex={0} aria-label="Comparison results"><table className="results-table"><thead><tr>{includeCase && <th>Case / model</th>}<th>Approach</th><th>Withholding</th><th>Tokens</th><th>Elapsed</th><th>Result</th><th><span className="sr-only">Inspect answer</span></th></tr></thead><tbody>{trials.map((trial) => {
    const name = configurations.find((config) => config.id === trial.configuration)?.name ?? human(trial.configuration);
    return <tr key={trial.id}>{includeCase && <td className="case-cell"><strong>{cases.find((payment) => payment.id === trial.case_id)?.title ?? trial.case_id}</strong><span>{models.find((model) => model.id === trial.model_id)?.name ?? trial.model_id} · repetition {trial.repetition}</span></td>}<td><strong>{name}</strong></td><td className="numeric">{trial.answer ? money(trial.answer.total_withholding_cents) : '—'}</td><td className="numeric">{trial.status === 'completed' ? count(totalTokens(trial)) : '—'}</td><td className="numeric">{trial.status === 'completed' ? duration(trial.metrics.wall_time_ms) : '—'}</td><td><Badge tone={trial.status === 'completed' ? trial.passed ? 'green' : 'amber' : trial.status === 'failed' ? 'red' : 'neutral'}>{trial.status === 'completed' ? trial.passed ? 'Pass' : 'Mismatch' : human(trial.status)}</Badge></td><td><button className="icon-button" aria-label={`Inspect ${name} answer`} onClick={() => inspect(trial)} disabled={!trial.answer && !trial.error}><Icon name="chevron" /></button></td></tr>;
  })}</tbody></table></div>;
}

function EvidencePanel({ evidence, payment, sources, close }: { evidence: Evidence; payment?: Case; sources: Source[]; close: () => void }) {
  const [tab, setTab] = useState<'evidence' | 'answer' | 'trace'>('evidence');
  const section = useRef<HTMLElement>(null);
  useEffect(() => { section.current?.focus({ preventScroll: true }); section.current?.scrollIntoView?.({ block: 'nearest' }); }, []);
  const citedSources = sources.filter((source) => evidence.answer.source_ids.includes(source.id));
  const citedDocuments = payment?.documents.filter((document) => evidence.answer.evidence_ids.includes(document.id)) ?? [];
  const missingSources = evidence.answer.source_ids.filter((id) => !sources.some((source) => source.id === id));
  return <section ref={section} tabIndex={-1} className="evidence-panel" role="dialog" aria-modal="false" aria-labelledby="evidence-heading">
    <div className="section-heading"><div><h2 id="evidence-heading">Evidence and answer</h2><p className="muted">{evidence.title}{payment ? ` · ${payment.title}` : ''}</p></div><button className="icon-button" onClick={close} aria-label="Close evidence"><Icon name="close" /></button></div>
    <div className="panel-tabs" role="group" aria-label="Answer details">{(['evidence', 'answer', 'trace'] as const).filter((name) => name !== 'trace' || evidence.trial).map((name) => <button key={name} id={`detail-tab-${name}`} aria-controls={`detail-${name}`} aria-pressed={tab === name} onClick={() => setTab(name)}>{name === 'evidence' ? 'Sources and facts' : name === 'answer' ? 'Structured answer' : 'Tool trace'}</button>)}</div>
    <div role="region" id={`detail-${tab}`} aria-labelledby={`detail-tab-${tab}`}>
      {tab === 'evidence' && <div className="evidence-columns"><div><h3>Legal sources</h3>{citedSources.length === 0 && <p className="muted">No legal sources were cited in this answer.</p>}{citedSources.map((source) => <article className="source-excerpt" key={source.id}><a href={source.url} target="_blank" rel="noreferrer">{source.title}<Icon name="external" size={15} /></a><span className="source-locator">{source.locator} · Source summary</span><p>{source.text}</p><span className="source-date">Retrieved {date(source.retrieved_at)}</span></article>)}{missingSources.map((id) => <p className="notice amber-notice" key={id}>Cited source “{id}” is not in this source snapshot.</p>)}</div><div><h3>Case evidence</h3>{citedDocuments.length === 0 && <p className="muted">No supporting documents were cited. The case facts remain available in the dividend panel.</p>}{citedDocuments.map((document) => <article className="source-excerpt" key={document.id}><h4><Icon name="document" size={16} />{document.title}</h4><p>{document.text}</p></article>)}<div className="evidence-reasoning"><h3>Answer justification</h3><p>{evidence.answer.reasoning}</p></div></div></div>}
      {tab === 'answer' && <div className="structured-answer"><AnswerSummary answer={evidence.answer} /><details><summary>View answer JSON</summary><pre>{JSON.stringify(evidence.answer, null, 2)}</pre></details>{evidence.trial && <><h3>Recorded usage</h3><dl className="metrics-list">{Object.entries(evidence.trial.metrics).map(([key, value]) => <div key={key}><dt>{human(key)}</dt><dd>{value == null ? 'Unavailable' : key.endsWith('_ms') ? duration(value) : key === 'cost_usd' ? `$${value.toFixed(6)}` : count(value)}</dd></div>)}</dl><h3>Provisional grading</h3><pre>{JSON.stringify(evidence.trial.grading, null, 2)}</pre></>}</div>}
      {tab === 'trace' && <div className="trace-panel"><p className="muted">Recorded tool requests and returned evidence. This view does not expose hidden model reasoning.</p>{evidence.trial?.trace.length ? evidence.trial.trace.map((entry, index) => <details key={index} open={index === 0}><summary>Trace event {index + 1}</summary><pre>{JSON.stringify(entry, null, 2)}</pre></details>) : <p className="notice">No tool events were recorded for this trial.</p>}</div>}
    </div>
  </section>;
}

function App() {
  const [page, setPage] = useState<Page>('demonstration');
  const [cases, setCases] = useState<Case[]>([]);
  const [sources, setSources] = useState<Source[]>([]);
  const [models, setModels] = useState<Model[]>([]);
  const [configurations, setConfigurations] = useState<Configuration[]>([]);
  const [health, setHealth] = useState<Health | null>(null);
  const [runs, setRuns] = useState<Run[]>([]);
  const [caseId, setCaseId] = useState('');
  const [modelId, setModelId] = useState('');
  const [selectedConfigurations, setSelectedConfigurations] = useState<string[]>([]);
  const [reference, setReference] = useState<TaxAnswer | null>(null);
  const [referenceLoading, setReferenceLoading] = useState(false);
  const [referenceError, setReferenceError] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [run, setRun] = useState<Run | null>(null);
  const [evidence, setEvidence] = useState<Evidence | null>(null);
  const [sourceQuery, setSourceQuery] = useState('');
  const [reload, setReload] = useState(0);
  const payment = cases.find((item) => item.id === caseId);
  const configuredModels = models.filter((model) => model.configured);
  const typedbAvailable = health?.typedb.available === true || health?.typedb.status === 'ok' || health?.typedb.status === 'available';

  useEffect(() => {
    let current = true;
    setLoading(true); setError('');
    Promise.all([api<Case[]>('/cases'), api<Source[]>('/sources'), api<Model[]>('/models'), api<Configuration[]>('/configurations'), api<Run[]>('/runs'), api<Health>('/health').catch(() => null)])
      .then(([nextCases, nextSources, nextModels, nextConfigurations, nextRuns, nextHealth]) => {
        if (!current) return;
        setCases(nextCases); setSources(nextSources); setModels(nextModels); setConfigurations(nextConfigurations); setRuns(nextRuns); setHealth(nextHealth);
        setCaseId((id) => nextCases.some((item) => item.id === id) ? id : nextCases[0]?.id ?? '');
        setModelId((id) => nextModels.some((item) => item.id === id && item.configured) ? id : nextModels.find((item) => item.configured)?.id ?? '');
        setSelectedConfigurations(nextConfigurations.map((item) => item.id));
      }).catch((reason: Error) => { if (current) setError(`The workspace could not load. ${reason.message}`); }).finally(() => { if (current) setLoading(false); });
    return () => { current = false; };
  }, [reload]);

  useEffect(() => {
    if (!caseId) return;
    let current = true;
    setReference(null); setReferenceLoading(true); setReferenceError('');
    api<{ answer: TaxAnswer }>(`/cases/${encodeURIComponent(caseId)}/reference`).then((result) => { if (current) setReference(result.answer); }).catch((reason: Error) => { if (current) setReferenceError(reason.message); }).finally(() => { if (current) setReferenceLoading(false); });
    return () => { current = false; };
  }, [caseId, reload]);

  useEffect(() => {
    if (!active(run)) return;
    let current = true;
    const timer = window.setInterval(() => {
      api<Run>(`/runs/${encodeURIComponent(run!.id)}`).then((updated) => { if (current) { setRun(updated); setRuns((previous) => [updated, ...previous.filter((item) => item.id !== updated.id)]); } }).catch((reason: Error) => { if (current) setError(`Could not refresh this run. ${reason.message}`); });
    }, 1500);
    return () => { current = false; window.clearInterval(timer); };
  }, [run?.id, run?.status]);

  function navigate(next: Page) { setPage(next); setEvidence(null); setError(''); if (next === 'demonstration' && run) { if (run.request.case_ids?.[0]) setCaseId(run.request.case_ids[0]); if (run.request.model_ids?.[0]) setModelId(run.request.model_ids[0]); } }
  function selectCase(id: string) { setCaseId(id); setRun(null); setEvidence(null); setError(''); }
  function toggleConfiguration(id: string) { setSelectedConfigurations((previous) => previous.includes(id) ? previous.filter((item) => item !== id) : [...previous, id]); }
  async function startRun(request: RunRequest) {
    setSubmitting(true); setError(''); setEvidence(null);
    try { const created = await api<Run>('/runs', { method: 'POST', body: JSON.stringify(request) }); setRun(created); setRuns((previous) => [created, ...previous]); }
    catch (reason) { setError((reason as Error).message); }
    finally { setSubmitting(false); }
  }
  async function cancelRun() {
    if (!run) return;
    try { const updated = await api<Run>(`/runs/${encodeURIComponent(run.id)}/cancel`, { method: 'POST' }); setRun(updated); setRuns((previous) => previous.map((item) => item.id === updated.id ? updated : item)); }
    catch (reason) { setError((reason as Error).message); }
  }
  async function openRun(id: string) {
    try { setRun(await api<Run>(`/runs/${encodeURIComponent(id)}`)); setEvidence(null); setError(''); }
    catch (reason) { setError((reason as Error).message); }
  }
  function inspect(trial: Trial) {
    if (trial.answer) setEvidence({ answer: trial.answer, trial, caseId: trial.case_id, title: configurations.find((config) => config.id === trial.configuration)?.name ?? trial.configuration });
    else if (trial.error) setError(trial.error);
  }

  const evidencePanel = evidence && <EvidencePanel key={`${evidence.trial?.id ?? 'reference'}-${evidence.caseId}`} evidence={evidence} payment={cases.find((item) => item.id === evidence.caseId)} sources={sources} close={() => setEvidence(null)} />;

  return <div className="app-shell">
    <a className="skip-link" href="#main-content">Skip to workspace</a>
    <header className="app-header"><div className="header-inner"><button className="wordmark" onClick={() => navigate('demonstration')} aria-label="Tax Context Benchmark home">Tax Context<span className="brand-dot" /> <span className="wordmark-suffix">Benchmark</span></button><nav aria-label="Main navigation">{(['demonstration', 'benchmark', 'sources'] as const).map((item) => <button key={item} className={page === item ? 'nav-link selected' : 'nav-link'} aria-current={page === item ? 'page' : undefined} onClick={() => navigate(item)}>{human(item)}</button>)}</nav><span className="header-status"><span />Research preview</span></div></header>
    <main id="main-content" className="main-content">
      <div className="page-heading"><div><h1>{page === 'demonstration' ? 'German dividend withholding tax' : page === 'benchmark' ? 'Benchmark workspace' : 'Source register'}</h1><p>{page === 'demonstration' ? 'One dividend. Four approaches. Follow the facts behind the answer.' : page === 'benchmark' ? 'Run reproducible comparisons across cases, models and approaches.' : 'The official legal material behind every approach, preserved in a shared source snapshot.'}</p></div><div className="workspace-status"><span className={typedbAvailable ? 'status-dot available' : 'status-dot'} /><span>TypeDB {typedbAvailable ? 'connected' : 'not connected'}</span></div></div>
      {error && <div className="notice error-notice" role="alert"><div><strong>{loading ? 'Connection problem' : 'Action could not complete'}</strong><p>{error}</p></div><button className="text-button" onClick={() => setReload((value) => value + 1)}>Retry</button></div>}
      {loading ? <div className="workspace-skeleton" aria-label="Loading workspace"><div /><div /><div /></div> : cases.length === 0 ? <div className="empty-state"><h2>No dividend cases are available</h2><p>Load the synthetic dataset on the server, then refresh the workspace.</p><button className="button secondary" onClick={() => setReload((value) => value + 1)}>Refresh workspace</button></div> : <>
        {page === 'demonstration' && payment && <>
          <section className="comparison-controls" aria-label="Comparison settings"><div className="case-select"><label htmlFor="case-select">Dividend case</label><select id="case-select" disabled={submitting || active(run)} value={caseId} onChange={(event) => selectCase(event.target.value)}>{cases.map((item) => <option key={item.id} value={item.id}>{item.title}</option>)}</select></div><div className="model-select"><label htmlFor="model-select">Language model</label><select id="model-select" value={modelId} onChange={(event) => { setModelId(event.target.value); setRun(null); setEvidence(null); }} disabled={!configuredModels.length || submitting || active(run)}>{!configuredModels.length && <option value="">No model configured</option>}{models.map((model) => <option key={model.id} value={model.id} disabled={!model.configured}>{model.name}{!model.configured ? ' — setup required' : ''}</option>)}</select></div><button className="button primary compare-button" disabled={!modelId || !selectedConfigurations.length || submitting || active(run)} onClick={() => startRun({ case_ids: [caseId], model_ids: [modelId], configurations: selectedConfigurations, repetitions: 1, max_steps: 6 })}>{submitting ? 'Starting comparison…' : active(run) ? 'Comparison running…' : 'Compare approaches'}<Icon name="arrow" /></button></section>
          {!configuredModels.length && <div className="setup-notice"><span><strong>Your reference walkthrough is ready.</strong> Configure a model endpoint on the server to measure answers, tokens and elapsed time.</span><details><summary>Model setup</summary><p>Set <code>MODELS_JSON</code> in the server environment with your model identifier, endpoint and API-key variable, then restart the server. Local endpoints can run without an API key. No live model calls run by default.</p></details></div>}
          <fieldset className="approach-options"><legend>Compare approaches</legend>{configurations.map((config) => <label key={config.id} title={config.description}><input type="checkbox" checked={selectedConfigurations.includes(config.id)} disabled={submitting || active(run)} onChange={() => toggleConfiguration(config.id)} /><span>{config.name}</span></label>)}</fieldset>
          <div className="workspace-grid"><CasePanel payment={payment} /><div className="decision-panel">{run ? <section className="measured-panel"><div className="section-heading"><h2>Measured comparison</h2><Badge tone="amber">Provisional scores</Badge></div><p className="panel-intro">{models.find((model) => model.id === modelId)?.name ?? modelId} · Same case, source snapshot and trial budget.</p><RunProgress run={run} onCancel={cancelRun} />{run.trials.length > 0 ? <TrialTable trials={run.trials.filter((trial) => trial.case_id === caseId && trial.model_id === modelId)} configurations={configurations} models={models} cases={cases} inspect={inspect} /> : <p className="run-waiting">Waiting for the first trial. Results appear as each approach completes.</p>}<p className="result-footnote">Pass means the answer met the provisional rubric. Failed and incomplete trials remain in the denominator. Missing token usage is unavailable.</p><a className="text-button" href={`/api/runs/${encodeURIComponent(run.id)}/export`} download><Icon name="download" size={16} />Export run JSON</a><button className="text-button reference-toggle" disabled={active(run)} onClick={() => { setRun(null); setEvidence(null); }}>Return to reference walkthrough</button></section> : <ReferencePanel answer={reference} loading={referenceLoading} error={referenceError} onInspect={() => reference && setEvidence({ answer: reference, caseId, title: 'Provisional reference walkthrough' })} />}</div></div>
          {evidencePanel}
          <section className="approach-explainer" aria-labelledby="approaches-heading"><h2 id="approaches-heading">What changes between approaches?</h2><p>The model and question stay the same. The available context changes.</p><div className="approach-list">{configurations.map((config) => <div key={config.id}><span className={`approach-mark ${config.id}`} /><h3>{config.name}</h3><p>{config.description}</p></div>)}</div></section>
        </>}
        {page === 'benchmark' && <Benchmark cases={cases} models={models} configurations={configurations} runs={runs} run={run} submitting={submitting} startRun={startRun} openRun={openRun} cancelRun={cancelRun} inspect={inspect} />}
        {page === 'sources' && <section className="sources-page"><div className="source-toolbar"><div><h2>Shared legal corpus <span>{sources.length}</span></h2><p className="muted">The same material is available to all four approaches.</p></div><div className="search-field"><label htmlFor="source-search">Find a source</label><input id="source-search" type="search" value={sourceQuery} onChange={(event) => setSourceQuery(event.target.value)} placeholder="Search title, statute or passage" /></div></div><div className="notice source-notice">Passages below are concise source summaries. Open the official source to read its full wording. The legal review and expected answers remain provisional.</div>{sources.filter((source) => `${source.title} ${source.locator} ${source.text}`.toLowerCase().includes(sourceQuery.toLowerCase())).map((source) => <article className="source-register-entry" key={source.id}><div><h3><a href={source.url} target="_blank" rel="noreferrer">{source.title}<Icon name="external" size={17} /></a></h3><span className="source-locator">{source.locator}</span></div><div><p>{source.text}</p><details><summary>Snapshot and provenance</summary><dl className="source-metadata"><div><dt>Retrieved</dt><dd>{date(source.retrieved_at)}</dd></div><div><dt>Source ID</dt><dd>{source.id}</dd></div>{Object.entries(source).filter(([key]) => /date|effective|version|application/.test(key) && key !== 'retrieved_at').map(([key, value]) => <div key={key}><dt>{human(key)}</dt><dd>{String(value)}</dd></div>)}<div><dt>SHA-256</dt><dd><code>{source.sha256}</code></dd></div></dl></details></div></article>)}{!sources.some((source) => `${source.title} ${source.locator} ${source.text}`.toLowerCase().includes(sourceQuery.toLowerCase())) && <div className="empty-state"><h3>No sources match “{sourceQuery}”</h3><p>Try a statute name or a shorter search term.</p><button className="text-button" onClick={() => setSourceQuery('')}>Clear search</button></div>}</section>}
        {page === 'benchmark' && evidencePanel}
      </>}
      <footer className="app-footer"><span>Tax Context Benchmark</span><p>Synthetic cases · Provisional legal review · No improvement assumed</p><button className="text-button" onClick={() => navigate('sources')}>Explore the sources<Icon name="arrow" size={15} /></button></footer>
    </main>
  </div>;
}

function Benchmark({ cases, models, configurations, runs, run, submitting, startRun, openRun, cancelRun, inspect }: { cases: Case[]; models: Model[]; configurations: Configuration[]; runs: Run[]; run: Run | null; submitting: boolean; startRun: (request: RunRequest) => Promise<void>; openRun: (id: string) => Promise<void>; cancelRun: () => void; inspect: (trial: Trial) => void }) {
  const [selectedCases, setSelectedCases] = useState<string[]>(cases.filter((payment) => payment.split === 'evaluation').map((payment) => payment.id));
  const [selectedModels, setSelectedModels] = useState<string[]>(models.filter((model) => model.configured).slice(0, 1).map((model) => model.id));
  const [selectedConfigs, setSelectedConfigs] = useState(configurations.map((config) => config.id));
  const [repetitions, setRepetitions] = useState(1);
  const [steps, setSteps] = useState(6);
  const [split, setSplit] = useState('evaluation');
  const trialCount = selectedCases.length * selectedModels.length * selectedConfigs.length * repetitions;
  const toggle = (values: string[], id: string) => values.includes(id) ? values.filter((item) => item !== id) : [...values, id];
  const visibleCases = cases.filter((payment) => split === 'all' || payment.split === split);
  const disabled = submitting || active(run);
  return <>
    <div className="benchmark-grid"><section className="batch-settings"><h2>Configure a run</h2><p className="muted">Evaluation cases are held out. Use development cases for setup and smoke tests; each trial starts a fresh conversation.</p><fieldset disabled={disabled}><legend>Cases <span>{selectedCases.length} selected</span></legend><div className="batch-case-toolbar"><select aria-label="Filter dataset split" value={split} onChange={(event) => setSplit(event.target.value)}><option value="development">Development cases</option><option value="evaluation">Evaluation cases</option><option value="all">All cases</option></select><button className="text-button" type="button" onClick={() => setSelectedCases([...new Set([...selectedCases, ...visibleCases.map((payment) => payment.id)])])}>Select shown</button><button className="text-button" type="button" onClick={() => setSelectedCases([])}>Clear</button></div><div className="case-checklist">{visibleCases.map((payment) => <label key={payment.id}><input type="checkbox" checked={selectedCases.includes(payment.id)} onChange={() => setSelectedCases(toggle(selectedCases, payment.id))} /><span>{payment.title}<small>{human(payment.category)} · {human(payment.split)}</small></span></label>)}</div><p className="selection-scope">Selected scope: {(['development', 'evaluation'] as const).map((kind) => ({ kind, count: cases.filter((payment) => selectedCases.includes(payment.id) && payment.split === kind).length })).filter((scope) => scope.count > 0).map((scope) => `${scope.count} ${scope.kind}`).join(' · ') || 'No cases selected'}</p></fieldset><fieldset disabled={disabled}><legend>Models</legend>{models.map((model) => <label className={!model.configured ? 'disabled-option' : ''} key={model.id}><input type="checkbox" disabled={!model.configured} checked={selectedModels.includes(model.id)} onChange={() => setSelectedModels(toggle(selectedModels, model.id))} /><span>{model.name}<small>{model.configured ? model.provider : 'Server configuration required'}</small></span></label>)}</fieldset><fieldset disabled={disabled}><legend>Approaches</legend>{configurations.map((config) => <label key={config.id}><input type="checkbox" checked={selectedConfigs.includes(config.id)} onChange={() => setSelectedConfigs(toggle(selectedConfigs, config.id))} /><span>{config.name}</span></label>)}</fieldset><div className="batch-number-controls"><label>Repetitions<select value={repetitions} disabled={disabled} onChange={(event) => setRepetitions(Number(event.target.value))}>{[1, 2, 3, 4, 5].map((value) => <option key={value}>{value}</option>)}</select></label><label>Max model steps<select value={steps} disabled={disabled} onChange={(event) => setSteps(Number(event.target.value))}>{Array.from({ length: 12 }, (_, index) => index + 1).map((value) => <option key={value}>{value}</option>)}</select></label></div><div className="batch-submit"><div><strong>{count(trialCount)} trials</strong><span>Provider calls may incur costs.</span></div><button className="button primary" disabled={disabled || trialCount === 0 || trialCount > 1800} onClick={() => startRun({ case_ids: selectedCases, model_ids: selectedModels, configurations: selectedConfigs, repetitions, max_steps: steps })}>{submitting ? 'Starting…' : 'Start benchmark'}<Icon name="arrow" /></button></div>{trialCount > 1800 && <p role="alert" className="validation-message">Reduce the selection to 1,800 trials or fewer.</p>}{!models.some((model) => model.configured) && <p className="validation-message">Configure a model on the server before starting a benchmark.</p>}</section><section className="run-history"><div className="section-heading"><h2>Run history</h2><Badge>{runs.length}</Badge></div>{runs.length === 0 ? <div className="history-empty"><Icon name="database" size={32} /><h3>Your first comparison starts here</h3><p>Completed answers, usage, errors and the reproducibility manifest will be saved for each run.</p><span>No measured benchmark results yet.</span></div> : <div className="history-list">{runs.map((item) => <button className={run?.id === item.id ? 'history-item chosen' : 'history-item'} key={item.id} onClick={() => openRun(item.id)}><span><strong>{date(item.created_at)}</strong><small>{item.id}</small></span><span><Badge tone={item.status === 'completed' ? 'green' : item.status === 'failed' ? 'red' : 'neutral'}>{human(item.status)}</Badge><small>{item.completed_trials}/{item.total_trials} trials</small></span><Icon name="chevron" size={16} /></button>)}</div>}<div className="benchmark-note"><h3>A controlled comparison</h3><p>All approaches share the question, model, source corpus and step budget. Results are graded against an independently specified provisional rubric.</p><p>Scores include failed trials. No accuracy or efficiency improvement is assumed.</p></div></section></div>
    {run && <section className="batch-results"><div className="section-heading"><div><h2>Run results</h2><p className="muted">{run.id} · Provisional evaluation</p></div><a className="button secondary" href={`/api/runs/${encodeURIComponent(run.id)}/export`} download><Icon name="download" size={16} />Export JSON</a></div><RunProgress run={run} onCancel={cancelRun} />{run.summary.length > 0 && <div className="table-scroll" tabIndex={0} aria-label="Aggregate results"><table className="results-table aggregate-table"><thead><tr><th>Model / approach</th><th>Strict pass</th><th>Errors</th><th>Avg. tokens</th><th>Avg. elapsed</th></tr></thead><tbody>{run.summary.map((row) => <tr key={`${row.model_id}-${row.configuration}`}><td><strong>{models.find((model) => model.id === row.model_id)?.name ?? row.model_id}</strong><span>{configurations.find((config) => config.id === row.configuration)?.name ?? row.configuration}</span></td><td className="numeric">{(row.pass_rate * 100).toFixed(1)}% <span className="muted">({row.passed}/{row.trials})</span></td><td className="numeric">{row.failed}</td><td className="numeric">{count(row.avg_total_tokens)}</td><td className="numeric">{duration(row.avg_wall_time_ms)}</td></tr>)}</tbody></table></div>}<h3 className="trial-heading">Individual trials</h3>{run.trials.length ? <TrialTable trials={run.trials} configurations={configurations} models={models} cases={cases} inspect={inspect} includeCase /> : <p className="muted">Trials will appear as the runner starts.</p>}<details className="manifest"><summary>Reproducibility manifest</summary><p className="muted">Frozen inputs, model settings, source hashes and execution limits for this run.</p><pre>{JSON.stringify(run.manifest, null, 2)}</pre></details></section>}
  </>;
}

export default App;
