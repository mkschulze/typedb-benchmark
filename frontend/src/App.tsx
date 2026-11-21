import { useEffect, useRef, useState } from 'react';
import { LanguageProvider, useLanguage } from './i18n';
import type { Budget, DividendCase as Case, Configuration, Harness, HarnessId, Health, Model, Run, RunRequest, Source, Summary, TaxAnswer, Trial } from './types';

type Page = 'demonstration' | 'benchmark' | 'sources';
type Evidence = { answer: TaxAnswer | null; trial?: Trial; caseId: string; title: string };

const active = (run: Run | null) => !!run && ['queued', 'running'].includes(run.status);
const totalTokens = (trial: Trial) => trial.metrics.input_tokens == null || trial.metrics.output_tokens == null ? null : trial.metrics.input_tokens + trial.metrics.output_tokens;
const defaultHarnesses: Harness[] = [
  { id: 'direct', name: 'Direct agent', available: true, description: 'Direct tool-calling agent.' },
  { id: 'crewai', name: 'CrewAI', available: false, description: 'Single agent; memory/delegation/planning disabled' },
];

function HarnessSelect({ harnesses, value, onChange, disabled }: { harnesses: Harness[]; value: HarnessId; onChange: (id: HarnessId) => void; disabled: boolean }) {
  const { t } = useLanguage();
  return <div className="harness-select"><label htmlFor="harness-select">{t("Agent harness")}</label><select id="harness-select" aria-describedby="harness-description" value={value} disabled={disabled} onChange={(event) => onChange(event.target.value as HarnessId)}>{harnesses.map((harness) => <option key={harness.id} value={harness.id} disabled={!harness.available}>{harness.name}{!harness.available ? t(" — unavailable") : ''}</option>)}</select></div>;
}

function BudgetStrip({ budget }: { budget: Budget | null | undefined }) {
  const { t, euro } = useLanguage();
  return <section className="budget-strip" aria-label={t("Shared experiment budget")} aria-busy={budget === undefined}>
    {budget ? <><div className="budget-heading"><h2>{euro(budget.limit_eur, true)} {t("experiment limit")}</h2>{budget.blocked && <Badge tone="amber">{t("New calls paused")}</Badge>}</div><dl className="budget-values"><div><dt>{t("Remaining")}</dt><dd>{euro(budget.remaining_eur)}</dd></div><div><dt>{t("Allocated")}</dt><dd>{euro(budget.spent_eur)}</dd></div><div><dt>{t("Reserved")}</dt><dd>{euro(budget.reserved_eur)}</dd></div></dl><p className="budget-note">{t("Shared across all providers. USD→EUR estimates include a safety buffer; unknown charges stay reserved.")}</p></> : <p className="budget-note">{budget === undefined ? t("Loading experiment budget…") : t("Budget status unavailable. The server still checks the limit before model calls.")}</p>}
  </section>;
}

function summaryBreakdown(row: Summary, trials: Trial[]) {
  const matching = trials.filter((trial) => trial.model_id === row.model_id && trial.configuration === row.configuration);
  return {
    errors: row.errors ?? matching.filter((trial) => trial.status === 'failed').length,
    incorrect: row.incorrect ?? matching.filter((trial) => trial.status === 'completed' && !trial.passed).length,
    cancelled: row.cancelled ?? matching.filter((trial) => trial.status === 'cancelled').length,
  };
}

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
  const { t, human, valueLabel, date, number } = useLanguage();
  return <dl className="facts-list">{Object.entries(facts).map(([key, value]) => <div key={key}><dt>{human(key)}</dt><dd>{value == null ? <span className="unknown">{t("Unknown")}</span> : typeof value === 'boolean' ? value ? t("Yes") : t("No") : typeof value === 'object' ? <Facts facts={value as Record<string, unknown>} /> : typeof value === 'number' ? number(value, Number.isInteger(value) ? 0 : 2) : typeof value === 'string' && /^\d{4}-\d{2}-\d{2}/.test(value) ? date(value) : valueLabel(String(value))}</dd></div>)}</dl>;
}

function CasePanel({ payment }: { payment: Case }) {
  const { t, human, money, date } = useLanguage();
  return <section className="case-panel" aria-labelledby="case-heading">
    <div className="section-heading"><h2 id="case-heading">{t("The dividend case")}</h2><Badge>{t("Synthetic")}</Badge></div>
    <h3 className="case-title">{payment.title}</h3>
    <p className="muted case-summary">{payment.summary}</p>
    <div className="payment-amount"><span>{t("Gross dividend")}</span><strong>{money(payment.gross_amount_cents)}</strong></div>
    <div className="ownership-flow">
      <div className="party"><span className="country-code">{payment.payer.country}</span><div><span className="field-caption">{t("German payer")}</span><strong>{payment.payer.name}</strong>{payment.payer.legal_form && <span>{payment.payer.legal_form}</span>}</div></div>
      <div className="flow-connector"><span /><span>{t("Dividend payment")}</span><Icon name="arrow" size={16} /></div>
      <div className="party"><span className="country-code">{payment.recipient.country}</span><div><span className="field-caption">{t("Corporate recipient")}</span><strong>{payment.recipient.name}</strong>{payment.recipient.legal_form && <span>{payment.recipient.legal_form}</span>}</div></div>
    </div>
    <dl className="date-facts"><div><dt>{t("Payment date")}</dt><dd>{date(payment.payment_date)}</dd></div><div><dt>{t("Information cutoff")}</dt><dd>{date(payment.knowledge_date)}</dd></div><div><dt>{t("Dataset split")}</dt><dd>{human(payment.split)}</dd></div></dl>
    <div className="question"><h3>{t("The question")}</h3><p>{payment.question}</p></div>
    <details className="case-details"><summary>{t("View all case facts")} <span>{Object.keys(payment.facts).length}</span></summary><Facts facts={payment.facts} /></details>
    <details className="case-details"><summary>{t("Supporting documents")} <span>{payment.documents.length}</span></summary>{payment.documents.map((document) => <article className="document-preview" key={document.id}><h4><Icon name="document" size={16} />{document.title}</h4><span className="original-caption">{t("Original document")}</span><p>{document.text}</p></article>)}</details>
  </section>;
}

function AnswerSummary({ answer, reasoning, original = true }: { answer: TaxAnswer; reasoning?: string; original?: boolean }) {
  const { t, human, money } = useLanguage();
  return <>
    <div className="answer-outcome"><div><span className="field-caption">{t("Withholding at payment")}</span><strong>{money(answer.total_withholding_cents)}</strong></div><Badge tone={answer.status === 'determined' ? 'green' : 'amber'}>{human(answer.status)}</Badge></div>
    <dl className="answer-figures"><div><dt>{t("Withholding tax")}</dt><dd>{money(answer.withholding_tax_cents)}</dd></div><div><dt>{t("Solidarity surcharge")}</dt><dd>{money(answer.solidarity_surcharge_cents)}</dd></div><div className="net-payment"><dt>{t("Net payment")}</dt><dd>{money(answer.net_payment_cents)}</dd></div></dl>
    <div className="relief-row"><div><span className="field-caption">{t("Relief eligibility")}</span><strong>{human(answer.relief_eligibility)}</strong></div><div><span className="field-caption">{t("Relief route")}</span><strong>{answer.relief_route ? answer.relief_route === 'section43b' ? t("EStG §43b · EU parent-company relief") : human(answer.relief_route) : t("Undetermined")}</strong></div></div>
    <div className="answer-reasoning">{original && <span className="original-caption">{t("Original answer")}</span>}<p>{reasoning ?? answer.reasoning}</p></div>
    {answer.missing_facts.length > 0 && <div className="notice amber-notice"><strong>{t("Information needed")}</strong><ul>{answer.missing_facts.map((fact) => <li key={fact}>{human(fact)}</li>)}</ul></div>}
    <dl className="refund-row"><div><dt>{t("Refund route")}</dt><dd>{human(answer.refund_status)}</dd></div><div><dt>{t("Possible refund")}</dt><dd>{money(answer.refund_amount_cents)}</dd></div></dl>
  </>;
}

function ReferencePanel({ answer, caseId, loading, error, onInspect }: { answer: TaxAnswer | null; caseId: string; loading: boolean; error: string; onInspect: () => void }) {
  const { t, referenceReasoning, errorText } = useLanguage();
  return <section className="reference-panel" aria-labelledby="reference-heading">
    <div className="section-heading"><h2 id="reference-heading">{t("Reference walkthrough")}</h2><Badge tone="amber">{t("Provisional")}</Badge></div>
    <p className="panel-intro">{t("Explore the expected decision before running a model. This deterministic walkthrough has no measured LLM results.")}</p>
    {loading ? <div className="skeleton-block" aria-label={t("Loading reference walkthrough")}><div /><div /><div /></div> : error ? <div role="alert" className="notice error-notice">{errorText(error)}</div> : answer && <>
      <AnswerSummary answer={answer} reasoning={referenceReasoning(caseId, answer.reasoning)} original={false} />
      <button className="text-button evidence-button" onClick={onInspect}>{t("Inspect reference evidence")} <Icon name="arrow" /></button>
    </>}
    <div className="decision-note"><Icon name="document" size={20} /><p><strong>{t("Eligibility and withholding are separate decisions.")}</strong> {t("Relief may be available even when the payer must withhold at the payment date.")}</p></div>
  </section>;
}

function RunProgress({ run, onCancel }: { run: Run; onCancel: () => void | Promise<void> }) {
  const { t, human } = useLanguage();
  const [requestingCancel, setRequestingCancel] = useState(false);
  return <div className="run-progress"><div className="run-progress-copy"><Badge tone={active(run) ? 'green' : run.status === 'failed' ? 'red' : 'neutral'}>{human(run.status)}</Badge><span>{run.completed_trials} {t("of")} {run.total_trials} {t("trials complete")}</span>{active(run) && <button className="text-button cancel-button" disabled={requestingCancel || run.cancellation_requested} onClick={async () => { setRequestingCancel(true); try { await onCancel(); } finally { setRequestingCancel(false); } }}>{run.cancellation_requested ? t("Cancelling after current call") : requestingCancel ? t("Requesting cancellation…") : t("Cancel run")}</button>}</div><progress aria-label={t("Run progress")} value={run.completed_trials} max={Math.max(run.total_trials, 1)} /></div>;
}

function RunState({ run }: { run: Run }) {
  const { t, human, errorText } = useLanguage();
  const checkpoint = run.active_trial;
  return <>
    {run.error && <div className="notice error-notice" role="alert"><div><strong>{t("Run error")}</strong><p>{errorText(run.error)}</p></div></div>}
    {run.trials.length === 0 && <p className="run-waiting">{active(run) ? run.cancellation_requested ? t("The current call is finishing. Its recorded usage and trace will appear before cancellation is final.") : t("Waiting for the first trial. Results appear as each approach completes.") : t("No trials were recorded. This run is {status}.", { status: human(run.status) })}</p>}
    {run.status === 'interrupted' && (checkpoint ? <section className="checkpoint"><h3>{t("Interrupted trial checkpoint")}</h3><p className="muted">{t("Case:")} {checkpoint.case_id} {t("· Model:")} {checkpoint.model_id} {t("· Approach:")} {human(checkpoint.configuration)} {t("· Repetition")} {checkpoint.repetition}</p><p className="muted">{t("Usage may be incomplete. This checkpoint is a partial record, not a completed answer.")}</p><details><summary>{t("Recorded checkpoint trace")}</summary>{checkpoint.trace?.length ? <><span className="original-caption">{t("Original record")}</span><pre>{JSON.stringify(checkpoint.trace, null, 2)}</pre></> : <p className="muted">{t("No tool trace was saved before the interruption.")}</p>}</details>{checkpoint.metrics && <details><summary>{t("Recorded checkpoint usage")}</summary><><span className="original-caption">{t("Original record")}</span><pre>{JSON.stringify(checkpoint.metrics, null, 2)}</pre></></details>}</section> : <p className="result-footnote">{t("The worker stopped before the active trial completed. No active-trial checkpoint was saved; any completed trials remain available below.")}</p>)}
  </>;
}

function TrialTable({ trials, configurations, models, cases, inspect, includeCase = false }: { trials: Trial[]; configurations: Configuration[]; models: Model[]; cases: Case[]; inspect: (trial: Trial) => void; includeCase?: boolean }) {
  const { t, human, money, count, duration } = useLanguage();
  return <div className="table-scroll" tabIndex={0} aria-label={t("Comparison results")}><table className="results-table"><thead><tr>{includeCase && <th>{t("Case / model")}</th>}<th>{t("Approach")}</th><th>{t("Withholding")}</th><th>{t("Tokens")}</th><th>{t("Elapsed")}</th><th>{t("Result")}</th><th aria-label={t("Inspect answer")} /></tr></thead><tbody>{trials.map((trial) => {
    const name = configurations.find((config) => config.id === trial.configuration)?.name ?? human(trial.configuration);
    return <tr key={trial.id}>{includeCase && <td className="case-cell"><strong>{cases.find((payment) => payment.id === trial.case_id)?.title ?? trial.case_id}</strong><span>{models.find((model) => model.id === trial.model_id)?.name ?? trial.model_id} {t("· repetition")} {trial.repetition}</span></td>}<td><strong>{name}</strong></td><td className="numeric">{trial.answer ? money(trial.answer.total_withholding_cents) : '—'}</td><td className="numeric">{totalTokens(trial) == null ? '—' : count(totalTokens(trial))}</td><td className="numeric">{trial.metrics.wall_time_ms == null ? '—' : duration(trial.metrics.wall_time_ms)}</td><td><Badge tone={trial.status === 'completed' ? trial.passed ? 'green' : 'amber' : trial.status === 'failed' ? 'red' : 'neutral'}>{trial.status === 'completed' ? trial.passed ? t("Pass") : t("Mismatch") : human(trial.status)}</Badge></td><td><button className="icon-button" aria-label={t("Inspect {name} answer", { name })} onClick={() => inspect(trial)} disabled={!trial.answer && !trial.error && !trial.trace.length && !Object.values(trial.metrics).some((value) => value != null)}><Icon name="chevron" /></button></td></tr>;
  })}</tbody></table></div>;
}

function EvidencePanel({ evidence, payment, sources, close }: { evidence: Evidence; payment?: Case; sources: Source[]; close: () => void }) {
  const { t, human, count, duration, date, usd, referenceReasoning, errorText } = useLanguage();
  const [tab, setTab] = useState<'evidence' | 'answer' | 'trace'>(evidence.answer ? 'evidence' : 'trace');
  const section = useRef<HTMLElement>(null);
  useEffect(() => { section.current?.focus({ preventScroll: true }); section.current?.scrollIntoView?.({ block: 'nearest' }); }, []);
  const citedSources = sources.filter((source) => evidence.answer?.source_ids.includes(source.id));
  const citedDocuments = payment?.documents.filter((document) => evidence.answer?.evidence_ids.includes(document.id)) ?? [];
  const missingSources = evidence.answer?.source_ids.filter((id) => !sources.some((source) => source.id === id)) ?? [];
  return <section ref={section} tabIndex={-1} className="evidence-panel" role="dialog" aria-modal="false" aria-labelledby="evidence-heading">
    <div className="section-heading"><div><h2 id="evidence-heading">{t("Evidence and answer")}</h2><p className="muted">{t(evidence.title)}{payment ? ` · ${payment.title}` : ''}</p></div><button className="icon-button" onClick={close} aria-label={t("Close evidence")}><Icon name="close" /></button></div>
    <div className="panel-tabs" role="group" aria-label={t("Answer details")}>{(['evidence', 'answer', 'trace'] as const).filter((name) => name !== 'trace' || evidence.trial).map((name) => <button key={name} id={`detail-tab-${name}`} aria-controls={`detail-${name}`} aria-pressed={tab === name} onClick={() => setTab(name)}>{name === 'evidence' ? t("Sources and facts") : name === 'answer' ? evidence.answer ? t("Structured answer") : t("Recorded usage") : t("Tool trace")}</button>)}</div>
    {evidence.trial?.error && <div className="notice error-notice" role="alert">{errorText(evidence.trial.error)}</div>}
    {!evidence.answer && <p className="result-footnote">{t("No final answer was recorded for this attempt. Recorded trace and usage remain available.")}</p>}
    <div role="region" id={`detail-${tab}`} aria-labelledby={`detail-tab-${tab}`}>
      {tab === 'evidence' && <div className="evidence-columns"><div><h3>{t("Legal sources")}</h3>{citedSources.length === 0 && <p className="muted">{t("No legal sources were cited in this answer.")}</p>}{citedSources.map((source) => <article className="source-excerpt" key={source.id}><a href={source.url} target="_blank" rel="noreferrer">{source.title}<Icon name="external" size={15} /></a><span className="source-locator">{source.locator} {t("· Source summary")}</span><p>{source.text}</p><span className="source-date">{t("Retrieved")} {date(source.retrieved_at)}</span></article>)}{missingSources.map((id) => <p className="notice amber-notice" key={id}>{t("Cited source “")}{id}{t("” is not in this source snapshot.")}</p>)}</div><div><h3>{t("Case evidence")}</h3>{citedDocuments.length === 0 && <p className="muted">{t("No supporting documents were cited. The case facts remain available in the dividend panel.")}</p>}{citedDocuments.map((document) => <article className="source-excerpt" key={document.id}><h4><Icon name="document" size={16} />{document.title}</h4><span className="original-caption">{t("Original document")}</span><p>{document.text}</p></article>)}<div className="evidence-reasoning"><h3>{evidence.trial ? t("Original answer") : t("Answer justification")}</h3><p>{evidence.answer ? evidence.trial ? evidence.answer.reasoning : referenceReasoning(evidence.caseId, evidence.answer.reasoning) : t("No final answer was recorded.")}</p></div></div></div>}
      {tab === 'answer' && <div className="structured-answer">{evidence.answer && <><AnswerSummary answer={evidence.answer} reasoning={evidence.trial ? undefined : referenceReasoning(evidence.caseId, evidence.answer.reasoning)} original={!!evidence.trial} /><details><summary>{t("View answer JSON")}</summary><><span className="original-caption">{t("Original record")}</span><pre>{JSON.stringify(evidence.answer, null, 2)}</pre></></details></>}{evidence.trial && <><h3>{t("Recorded usage")}</h3><dl className="metrics-list">{Object.entries(evidence.trial.metrics).map(([key, value]) => <div key={key}><dt>{human(key)}</dt><dd>{value == null ? t("Unavailable") : typeof value !== "number" ? <details><summary>{t("Original record")}</summary><pre>{JSON.stringify(value, null, 2)}</pre></details> : key.endsWith('_ms') ? duration(value) : key.endsWith('_usd') ? usd(value) : count(value)}</dd></div>)}</dl><h3>{t("Provisional grading")}</h3><><span className="original-caption">{t("Original record")}</span><pre>{JSON.stringify(evidence.trial.grading, null, 2)}</pre></></>}</div>}
      {tab === 'trace' && <div className="trace-panel"><p className="muted">{t("Recorded tool requests and returned evidence. This view does not expose hidden model reasoning.")}</p>{evidence.trial?.trace.length ? evidence.trial.trace.map((entry, index) => <details key={index} open={index === 0}><summary>{t("Trace event")} {index + 1}</summary><><span className="original-caption">{t("Original record")}</span><pre>{JSON.stringify(entry, null, 2)}</pre></></details>) : <p className="notice">{t("No tool events were recorded for this trial.")}</p>}</div>}
    </div>
  </section>;
}

function AppContent() {
  const { t, human, date, harnessName, number, valueLabel, localizeCase, localizeSource, localizeConfiguration, localizeHarness, language, setLanguage, errorText } = useLanguage();
  const [page, setPage] = useState<Page>('demonstration');
  const [originalCases, setCases] = useState<Case[]>([]);
  const [originalSources, setSources] = useState<Source[]>([]);
  const [models, setModels] = useState<Model[]>([]);
  const [originalHarnesses, setHarnesses] = useState<Harness[]>(defaultHarnesses);
  const [harnessId, setHarnessId] = useState<HarnessId>('direct');
  const [originalConfigurations, setConfigurations] = useState<Configuration[]>([]);
  const [health, setHealth] = useState<Health | null>(null);
  const [budget, setBudget] = useState<Budget | null | undefined>(undefined);
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
  const cases = originalCases.map(localizeCase);
  const sources = originalSources.map(localizeSource);
  const configurations = originalConfigurations.map(localizeConfiguration);
  const harnesses = originalHarnesses.map(localizeHarness);
  const payment = cases.find((item) => item.id === caseId);
  const configuredModels = models.filter((model) => model.configured);
  const harnessAvailable = harnesses.some((harness) => harness.id === harnessId && harness.available);
  const typedbAvailable = health?.typedb.available === true || health?.typedb.status === 'ok' || health?.typedb.status === 'available';

  useEffect(() => {
    let current = true;
    setLoading(true); setError('');
    Promise.all([api<Case[]>('/cases'), api<Source[]>('/sources'), api<Model[]>('/models'), api<Configuration[]>('/configurations'), api<Run[]>('/runs'), api<Health>('/health').catch(() => null), api<Harness[]>('/harnesses').catch(() => defaultHarnesses)])
      .then(([nextCases, nextSources, nextModels, nextConfigurations, nextRuns, nextHealth, nextHarnesses]) => {
        if (!current) return;
        setCases(nextCases); setSources(nextSources); setModels(nextModels); setConfigurations(nextConfigurations); setRuns(nextRuns); setHealth(nextHealth);
        setHarnesses(nextHarnesses); setHarnessId((id) => nextHarnesses.some((harness) => harness.id === id && harness.available) ? id : 'direct');
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
    let current = true;
    api<Budget>('/budget').then((snapshot) => { if (current) setBudget(snapshot); }).catch(() => { if (current) setBudget(null); });
    return () => { current = false; };
  }, [reload, run?.id, run?.status]);

  useEffect(() => {
    if (!active(run)) return;
    let current = true;
    const timer = window.setInterval(() => {
      api<Run>(`/runs/${encodeURIComponent(run!.id)}`).then((updated) => { if (current) { setRun(updated); setRuns((previous) => [updated, ...previous.filter((item) => item.id !== updated.id)]); } }).catch((reason: Error) => { if (current) setError(`Could not refresh this run. ${reason.message}`); });
      api<Budget>('/budget').then((snapshot) => { if (current) setBudget(snapshot); }).catch(() => { if (current) setBudget(null); });
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
    setEvidence({ answer: trial.answer, trial, caseId: trial.case_id, title: configurations.find((config) => config.id === trial.configuration)?.name ?? trial.configuration });
  }

  const evidencePanel = evidence && <EvidencePanel key={`${evidence.trial?.id ?? 'reference'}-${evidence.caseId}`} evidence={{ ...evidence, title: evidence.trial ? configurations.find((config) => config.id === evidence.trial!.configuration)?.name ?? evidence.title : t("Provisional reference walkthrough") }} payment={cases.find((item) => item.id === evidence.caseId)} sources={sources} close={() => setEvidence(null)} />;

  return <div className="app-shell">
    <a className="skip-link" href="#main-content">{t("Skip to workspace")}</a>
    <header className="app-header"><div className="header-inner"><button className="wordmark" onClick={() => navigate('demonstration')} aria-label={t("Tax Context Benchmark home")}>Tax Context<span className="brand-dot" /> <span className="wordmark-suffix">Benchmark</span></button><nav aria-label={t("Main navigation")}>{(['demonstration', 'benchmark', 'sources'] as const).map((item) => <button key={item} className={page === item ? 'nav-link selected' : 'nav-link'} aria-current={page === item ? 'page' : undefined} onClick={() => navigate(item)}>{human(item)}</button>)}</nav><span className="header-status"><span />{t("Research preview")}</span><div className="language-switch" role="group" aria-label={t("Language")}><button lang="de" aria-label="Deutsch" aria-pressed={language === "de"} onClick={() => setLanguage("de")}>DE</button><button lang="en" aria-label="English" aria-pressed={language === "en"} onClick={() => setLanguage("en")}>EN</button></div></div></header>
    <main id="main-content" className="main-content">
      <div className="page-heading"><div><h1>{page === 'demonstration' ? t("German dividend withholding tax") : page === 'benchmark' ? t("Benchmark workspace") : t("Source register")}</h1><p>{page === 'demonstration' ? t("One dividend. Four approaches. Follow the facts behind the answer.") : page === 'benchmark' ? t("Run reproducible comparisons across cases, models and approaches.") : t("The official legal material behind every approach, preserved in a shared source snapshot.")}</p></div><div className="workspace-status"><span className={typedbAvailable ? 'status-dot available' : 'status-dot'} /><span>TypeDB {typedbAvailable ? t("connected") : t("not connected")}</span></div></div>
      <BudgetStrip budget={budget} />
      {error && <div className="notice error-notice" role="alert"><div><strong>{loading ? t("Connection problem") : t("Action could not complete")}</strong><p>{errorText(error)}</p></div><button className="text-button" onClick={() => setReload((value) => value + 1)}>{t("Retry")}</button></div>}
      {loading ? <div className="workspace-skeleton" aria-label={t("Loading workspace")}><div /><div /><div /></div> : cases.length === 0 ? <div className="empty-state"><h2>{t("No dividend cases are available")}</h2><p>{t("Load the synthetic dataset on the server, then refresh the workspace.")}</p><button className="button secondary" onClick={() => setReload((value) => value + 1)}>{t("Refresh workspace")}</button></div> : <>
        {page === 'demonstration' && payment && <>
          <section className="comparison-controls" aria-label={t("Comparison settings")}><div className="case-select"><label htmlFor="case-select">{t("Dividend case")}</label><select id="case-select" disabled={submitting || active(run)} value={caseId} onChange={(event) => selectCase(event.target.value)}>{cases.map((item) => <option key={item.id} value={item.id}>{item.title}</option>)}</select></div><div className="model-select"><label htmlFor="model-select">{t("Language model")}</label><select id="model-select" value={modelId} onChange={(event) => { setModelId(event.target.value); setRun(null); setEvidence(null); }} disabled={!configuredModels.length || submitting || active(run)}>{!configuredModels.length && <option value="">{t("No model configured")}</option>}{models.map((model) => <option key={model.id} value={model.id} disabled={!model.configured}>{model.name}{!model.configured ? t(" — setup required") : ''}</option>)}</select></div><HarnessSelect harnesses={harnesses} value={harnessId} onChange={(id) => { setHarnessId(id); setRun(null); setEvidence(null); }} disabled={submitting || active(run)} /><button className="button primary compare-button" disabled={!modelId || !harnessAvailable || !selectedConfigurations.length || submitting || active(run) || budget?.blocked} onClick={() => startRun({ case_ids: [caseId], model_ids: [modelId], configurations: selectedConfigurations, repetitions: 1, max_steps: 6, harness: harnessId })}>{submitting ? t("Starting comparison…") : active(run) ? t("Comparison running…") : t("Compare approaches")}<Icon name="arrow" /></button></section>
          <p className="harness-description" id="harness-description">{harnesses.find((harness) => harness.id === harnessId)?.description}</p>
          {!configuredModels.length && <div className="setup-notice"><span><strong>{t("Your reference walkthrough is ready.")}</strong> {t("Configure a model endpoint on the server to measure answers, tokens and elapsed time.")}</span><details><summary>{t("Model setup")}</summary><p>{t("Set")} <code>MODELS_JSON</code> {t("in the server environment with your model identifier, endpoint and API-key variable, then restart the server. Local endpoints can run without an API key. No live model calls run by default.")}</p></details></div>}
          <fieldset className="approach-options"><legend>{t("Compare approaches")}</legend>{configurations.map((config) => <label key={config.id} title={config.description}><input type="checkbox" checked={selectedConfigurations.includes(config.id)} disabled={submitting || active(run)} onChange={() => toggleConfiguration(config.id)} /><span>{config.name}</span></label>)}</fieldset>
          <div className="workspace-grid"><CasePanel payment={payment} /><div className="decision-panel">{run ? <section className="measured-panel"><div className="section-heading"><h2>{t("Measured comparison")}</h2><Badge tone="amber">{t("Provisional scores")}</Badge></div><p className="panel-intro">{models.find((model) => model.id === modelId)?.name ?? modelId} · {harnessName(run.request.harness)} {t("· Same case, source snapshot and trial budget.")}</p><RunProgress run={run} onCancel={cancelRun} /><RunState run={run} />{run.trials.length > 0 && <TrialTable trials={run.trials.filter((trial) => trial.case_id === caseId && trial.model_id === modelId)} configurations={configurations} models={models} cases={cases} inspect={inspect} />}<p className="result-footnote">{t("Pass means the answer met the provisional rubric. Invalid answers and execution failures remain in the denominator. Budget-stopped incomplete trials are excluded. Missing token usage is unavailable.")}</p><a className="text-button" href={`/api/runs/${encodeURIComponent(run.id)}/export`} download><Icon name="download" size={16} />{t("Export run JSON")}</a><button className="text-button reference-toggle" disabled={active(run)} onClick={() => { setRun(null); setEvidence(null); }}>{t("Return to reference walkthrough")}</button></section> : <ReferencePanel answer={reference} caseId={caseId} loading={referenceLoading} error={referenceError} onInspect={() => reference && setEvidence({ answer: reference, caseId, title: t("Provisional reference walkthrough") })} />}</div></div>
          {evidencePanel}
          <section className="approach-explainer" aria-labelledby="approaches-heading"><h2 id="approaches-heading">{t("What changes between approaches?")}</h2><p>{t("The model and question stay the same. The available context changes.")}</p><div className="approach-list">{configurations.map((config) => <div key={config.id}><span className={`approach-mark ${config.id}`} /><h3>{config.name}</h3><p>{config.description}</p></div>)}</div></section>
        </>}
        {page === 'benchmark' && <Benchmark budgetBlocked={budget?.blocked ?? false} cases={cases} models={models} configurations={configurations} harnesses={harnesses} harnessId={harnessId} setHarnessId={setHarnessId} runs={runs} run={run} submitting={submitting} startRun={startRun} openRun={openRun} cancelRun={cancelRun} inspect={inspect} />}
        {page === 'sources' && <section className="sources-page"><div className="source-toolbar"><div><h2>{t("Shared legal corpus")} <span>{sources.length}</span></h2><p className="muted">{t("The same material is available to all four approaches.")}</p></div><div className="search-field"><label htmlFor="source-search">{t("Find a source")}</label><input id="source-search" type="search" value={sourceQuery} onChange={(event) => setSourceQuery(event.target.value)} placeholder={t("Search title, statute or passage")} /></div></div><div className="notice source-notice">{t("Passages below are concise source summaries. Open the official source to read its full wording. The legal review and expected answers remain provisional.")}</div>{sources.filter((source) => `${source.title} ${source.locator} ${source.text}`.toLowerCase().includes(sourceQuery.toLowerCase())).map((source) => <article className="source-register-entry" key={source.id}><div><h3><a href={source.url} target="_blank" rel="noreferrer">{source.title}<Icon name="external" size={17} /></a></h3><span className="source-locator">{source.locator}</span></div><div><p>{source.text}</p><details><summary>{t("Snapshot and provenance")}</summary><dl className="source-metadata"><div><dt>{t("Retrieved")}</dt><dd>{date(source.retrieved_at)}</dd></div><div><dt>{t("Source ID")}</dt><dd>{source.id}</dd></div>{Object.entries(source).filter(([key]) => /date|effective|version|application/.test(key) && key !== 'retrieved_at').map(([key, value]) => <div key={key}><dt>{human(key)}</dt><dd>{typeof value === 'number' ? number(value, Number.isInteger(value) ? 0 : 2) : typeof value === 'string' && /^\d{4}-\d{2}-\d{2}/.test(value) ? date(value) : valueLabel(String(value))}</dd></div>)}<div><dt>SHA-256</dt><dd><code>{source.sha256}</code></dd></div></dl></details></div></article>)}{!sources.some((source) => `${source.title} ${source.locator} ${source.text}`.toLowerCase().includes(sourceQuery.toLowerCase())) && <div className="empty-state"><h3>{t("No sources match “")}{sourceQuery}{language === "de" ? "“" : "”"}</h3><p>{t("Try a statute name or a shorter search term.")}</p><button className="text-button" onClick={() => setSourceQuery('')}>{t("Clear search")}</button></div>}</section>}
        {page === 'benchmark' && evidencePanel}
      </>}
      <footer className="app-footer"><span>Tax Context Benchmark</span><p>{t("Synthetic cases · Provisional legal review · No improvement assumed")}</p><button className="text-button" onClick={() => navigate('sources')}>{t("Explore the sources")}<Icon name="arrow" size={15} /></button></footer>
    </main>
  </div>;
}

function Benchmark({ budgetBlocked, cases, models, configurations, harnesses, harnessId, setHarnessId, runs, run, submitting, startRun, openRun, cancelRun, inspect }: { budgetBlocked: boolean; cases: Case[]; models: Model[]; configurations: Configuration[]; harnesses: Harness[]; harnessId: HarnessId; setHarnessId: (id: HarnessId) => void; runs: Run[]; run: Run | null; submitting: boolean; startRun: (request: RunRequest) => Promise<void>; openRun: (id: string) => Promise<void>; cancelRun: () => void; inspect: (trial: Trial) => void }) {
  const { t, human, count, duration, date, harnessName, percent } = useLanguage();
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
  const harnessAvailable = harnesses.some((harness) => harness.id === harnessId && harness.available);
  return <>
    <div className="benchmark-grid"><section className="batch-settings"><h2>{t("Configure a run")}</h2><p className="muted">{t("Evaluation cases are held out. Use development cases for setup and smoke tests; each trial starts a fresh conversation.")}</p><div className="batch-harness-controls"><HarnessSelect harnesses={harnesses} value={harnessId} onChange={setHarnessId} disabled={disabled} /><p className="harness-description" id="harness-description">{harnesses.find((harness) => harness.id === harnessId)?.description}</p></div><fieldset disabled={disabled}><legend>{t("Cases")} <span>{selectedCases.length} {t("selected")}</span></legend><div className="batch-case-toolbar"><select aria-label={t("Filter dataset split")} value={split} onChange={(event) => setSplit(event.target.value)}><option value="development">{t("Development cases")}</option><option value="evaluation">{t("Evaluation cases")}</option><option value="all">{t("All cases")}</option></select><button className="text-button" type="button" onClick={() => setSelectedCases([...new Set([...selectedCases, ...visibleCases.map((payment) => payment.id)])])}>{t("Select shown")}</button><button className="text-button" type="button" onClick={() => setSelectedCases([])}>{t("Clear")}</button></div><div className="case-checklist">{visibleCases.map((payment) => <label key={payment.id}><input type="checkbox" checked={selectedCases.includes(payment.id)} onChange={() => setSelectedCases(toggle(selectedCases, payment.id))} /><span>{payment.title}<small>{human(payment.category)} · {human(payment.split)}</small></span></label>)}</div><p className="selection-scope">{t("Selected scope:")} {(['development', 'evaluation'] as const).map((kind) => ({ kind, count: cases.filter((payment) => selectedCases.includes(payment.id) && payment.split === kind).length })).filter((scope) => scope.count > 0).map((scope) => `${count(scope.count)} ${human(scope.kind)}`).join(' · ') || t("No cases selected")}</p></fieldset><fieldset disabled={disabled}><legend>{t("Models")}</legend>{models.map((model) => <label className={!model.configured ? 'disabled-option' : ''} key={model.id}><input type="checkbox" disabled={!model.configured} checked={selectedModels.includes(model.id)} onChange={() => setSelectedModels(toggle(selectedModels, model.id))} /><span>{model.name}<small>{model.configured ? model.provider : t("Server configuration required")}</small></span></label>)}</fieldset><fieldset disabled={disabled}><legend>{t("Approaches")}</legend>{configurations.map((config) => <label key={config.id}><input type="checkbox" checked={selectedConfigs.includes(config.id)} onChange={() => setSelectedConfigs(toggle(selectedConfigs, config.id))} /><span>{config.name}</span></label>)}</fieldset><div className="batch-number-controls"><label>{t("Repetitions")}<select value={repetitions} disabled={disabled} onChange={(event) => setRepetitions(Number(event.target.value))}>{[1, 2, 3, 4, 5].map((value) => <option key={value}>{value}</option>)}</select></label><label>{t("Max model steps")}<select value={steps} disabled={disabled} onChange={(event) => setSteps(Number(event.target.value))}>{Array.from({ length: 12 }, (_, index) => index + 1).map((value) => <option key={value}>{value}</option>)}</select></label></div><div className="batch-submit"><div><strong>{count(trialCount)} {t("trials")}</strong><span>{t("Provider calls may incur costs.")}</span></div><button className="button primary" disabled={disabled || budgetBlocked || !harnessAvailable || trialCount === 0 || trialCount > 1800} onClick={() => startRun({ case_ids: selectedCases, model_ids: selectedModels, configurations: selectedConfigs, repetitions, max_steps: steps, harness: harnessId })}>{submitting ? t("Starting…") : t("Start benchmark")}<Icon name="arrow" /></button></div>{trialCount > 1800 && <p role="alert" className="validation-message">{t("Reduce the selection to 1,800 trials or fewer.")}</p>}{!models.some((model) => model.configured) && <p className="validation-message">{t("Configure a model on the server before starting a benchmark.")}</p>}</section><section className="run-history"><div className="section-heading"><h2>{t("Run history")}</h2><Badge>{runs.length}</Badge></div>{runs.length === 0 ? <div className="history-empty"><Icon name="database" size={32} /><h3>{t("Your first comparison starts here")}</h3><p>{t("Completed answers, usage, errors and the reproducibility manifest will be saved for each run.")}</p><span>{t("No measured benchmark results yet.")}</span></div> : <div className="history-list">{runs.map((item) => <button className={run?.id === item.id ? 'history-item chosen' : 'history-item'} key={item.id} onClick={() => openRun(item.id)}><span><strong>{date(item.created_at)}</strong><small>{item.id} · {harnessName(item.request.harness)}</small></span><span><Badge tone={item.status === 'completed' ? 'green' : item.status === 'failed' ? 'red' : 'neutral'}>{human(item.status)}</Badge><small>{item.completed_trials}/{item.total_trials} {t("trials")}</small></span><Icon name="chevron" size={16} /></button>)}</div>}<div className="benchmark-note"><h3>{t("A controlled comparison")}</h3><p>{t("All approaches share the question, model, source corpus and step budget. Results are graded against an independently specified provisional rubric.")}</p><p>{t("Scores include failed trials. No accuracy or efficiency improvement is assumed.")}</p></div></section></div>
    {run && <section className="batch-results"><div className="section-heading"><div><h2>{t("Run results")}</h2><p className="muted">{run.id} · {harnessName(run.request.harness)} {t("· Provisional evaluation")}</p></div><a className="button secondary" href={`/api/runs/${encodeURIComponent(run.id)}/export`} download><Icon name="download" size={16} />{t("Export JSON")}</a></div><RunProgress run={run} onCancel={cancelRun} /><RunState run={run} />{run.summary.length > 0 && <div className="table-scroll" tabIndex={0} aria-label={t("Aggregate results")}><table className="results-table aggregate-table"><thead><tr><th>{t("Model / approach")}</th><th>{t("Strict pass")}</th><th>{t("Incorrect answers")}</th><th>{t("Execution errors")}</th><th>{t("Cancelled")}</th><th>{t("Avg. tokens")}</th><th>{t("Avg. elapsed")}</th></tr></thead><tbody>{run.summary.map((row) => { const breakdown = summaryBreakdown(row, run.trials); return <tr key={`${row.model_id}-${row.configuration}`}><td><strong>{models.find((model) => model.id === row.model_id)?.name ?? row.model_id}</strong><span>{configurations.find((config) => config.id === row.configuration)?.name ?? row.configuration}</span></td><td className="numeric">{percent(row.pass_rate)} <span className="muted">({row.passed}/{row.trials})</span></td><td className="numeric">{breakdown.incorrect}</td><td className="numeric">{breakdown.errors}</td><td className="numeric">{breakdown.cancelled}</td><td className="numeric">{count(row.avg_total_tokens)}</td><td className="numeric">{duration(row.avg_wall_time_ms)}</td></tr>; })}</tbody></table></div>}<h3 className="trial-heading">{t("Individual trials")}</h3>{run.trials.length > 0 && <TrialTable trials={run.trials} configurations={configurations} models={models} cases={cases} inspect={inspect} includeCase />}<details className="manifest"><summary>{t("Reproducibility manifest")}</summary><p className="muted">{t("Frozen inputs, model settings, source hashes and execution limits for this run.")}</p><><span className="original-caption">{t("Original record")}</span><pre>{JSON.stringify(run.manifest, null, 2)}</pre></></details></section>}
  </>;
}

function App() { return <LanguageProvider><AppContent /></LanguageProvider>; }

export default App;
