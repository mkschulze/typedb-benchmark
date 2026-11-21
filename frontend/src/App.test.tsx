import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import App from './App';
import contentDe from './locales/content.de.json';
import type { Run } from './types';

const payment = { id: 'case-1', title: 'A valid exemption certificate', summary: 'A Dutch parent receives an ordinary dividend.', category: 'certificate', split: 'development', question: 'What must the payer withhold?', gross_amount_cents: 10000000, payment_date: '2026-06-30', knowledge_date: '2026-06-30', payer: { id: 'payer', name: 'Example GmbH', country: 'DE' }, recipient: { id: 'recipient', name: 'Example Holding BV', country: 'NL' }, facts: { direct_ownership_percent: 100, exemption_certificate: true, unknown_fact: null }, documents: [{ id: 'doc-1', title: 'Exemption certificate', text: 'A synthetic certificate, valid on the payment date.' }], source_ids: ['estg-50c'], review_status: 'provisional' };
const answer = { status: 'determined', relief_eligibility: 'eligible', relief_route: 'Parent-company relief', withholding_tax_cents: 0, solidarity_surcharge_cents: 0, total_withholding_cents: 0, net_payment_cents: 10000000, refund_status: 'not_required', refund_amount_cents: 0, missing_facts: [], source_ids: ['estg-50c'], evidence_ids: ['doc-1'], reasoning: 'The valid exemption certificate supports relief at payment.' };
const run = { id: 'run-1', status: 'completed', created_at: '2026-11-21T10:00:00Z', updated_at: '2026-11-21T10:00:00Z', completed_trials: 1, total_trials: 1, request: {}, manifest: { review_status: 'provisional' }, trials: [{ id: 'trial-1', case_id: 'case-1', model_id: 'local', configuration: 'rag', repetition: 1, status: 'completed', passed: true, answer, error: null, grading: {}, metrics: { input_tokens: 120, output_tokens: 80, wall_time_ms: 900 }, trace: [{ tool: 'read_source', result: { id: 'estg-50c' } }] }], summary: [] };
let configured = true;
let rejectRun = false;
let createdRun: Run = run;
let polledRun: Run = run;
let budgetSnapshot = { limit_eur: 30, spent_eur: 5, reserved_eur: 2, committed_eur: 7, remaining_eur: 23, blocked: false };
let budgetUnavailable = false;
let cancelledRun: Run = run;
let crewaiAvailable = true;
let schemaApproach = false;
let harnessesUnavailable = false;
let savedRuns: Run[] = [];
let caseSnapshot = payment;

beforeEach(() => {
  const preferences = new Map<string, string>();
  vi.stubGlobal('localStorage', {
    getItem: (key: string) => preferences.get(key) ?? null,
    setItem: (key: string, value: string) => preferences.set(key, String(value)),
    removeItem: (key: string) => preferences.delete(key),
    clear: () => preferences.clear(),
  });
  window.localStorage.setItem('tax-benchmark-language', 'en');
  configured = true;
  rejectRun = false;
  createdRun = run; polledRun = run; cancelledRun = run;
  budgetSnapshot = { limit_eur: 30, spent_eur: 5, reserved_eur: 2, committed_eur: 7, remaining_eur: 23, blocked: false };
  budgetUnavailable = false;
  crewaiAvailable = true; schemaApproach = false; harnessesUnavailable = false; savedRuns = [];
  caseSnapshot = payment;
  vi.stubGlobal('fetch', vi.fn(async (path: string, options?: RequestInit) => {
    const url = String(path);
    if (url === '/api/budget') return new Response(JSON.stringify(budgetUnavailable ? { detail: 'Budget unavailable' } : budgetSnapshot), { status: budgetUnavailable ? 503 : 200 });
    if (url === '/api/harnesses') return new Response(JSON.stringify(harnessesUnavailable ? { detail: 'Not found' } : [{ id: 'direct', name: 'Direct agent', available: true, description: 'Direct tool-calling agent.' }, { id: 'crewai', name: 'CrewAI', available: crewaiAvailable, description: 'Single agent; memory/delegation/planning disabled' }]), { status: harnessesUnavailable ? 404 : 200 });
    if (url === '/api/runs' && options?.method === 'POST') {
      if (rejectRun) return new Response(JSON.stringify({ detail: 'TypeDB is unavailable. Start the database and retry.' }), { status: 503 });
      return new Response(JSON.stringify(createdRun), { status: 202 });
    }
    if (url === '/api/runs/run-1/cancel') return new Response(JSON.stringify(cancelledRun));
    const data: Record<string, unknown> = {
      '/api/health': { status: 'ok', typedb: { available: true }, legal_review: 'provisional' },
      '/api/cases': [caseSnapshot],
      '/api/models': [{ id: 'local', name: 'Local model', configured, provider: 'OpenAI-compatible' }],
      '/api/configurations': [{ id: 'rag', name: 'Retrieval baseline', description: 'Source retrieval.' }, { id: 'sql', name: 'SQL control', description: 'Equivalent structured rules.' }, ...(schemaApproach ? [{ id: 'typedb_schema', name: 'TypeDB + schema', description: 'Schema in the model context, without decision functions.' }] : [])],
      '/api/sources': [{ id: 'estg-50c', title: 'EStG §50c', locator: 'Section 50c', url: 'https://www.gesetze-im-internet.de/estg/__50c.html', text: 'A source summary about the exemption procedure.', retrieved_at: '2026-11-21', sha256: 'abc123' }],
      '/api/runs': savedRuns,
      [`/api/cases/${caseSnapshot.id}/reference`]: { answer, kind: 'reference', review_status: 'provisional' },
      '/api/runs/run-1': polledRun,
    };
    if (!(url in data)) return new Response(JSON.stringify({ detail: 'Not found' }), { status: 404 });
    return new Response(JSON.stringify(data[url]));
  }));
});

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe('language selection', () => {
  it('shows the separate schema approach in both languages and submits its exact ID', async () => {
    schemaApproach = true;
    window.localStorage.setItem('tax-benchmark-language', 'de');
    const user = userEvent.setup();
    render(<App />);
    expect(await screen.findByRole('checkbox', { name: 'TypeDB + Schema' })).toBeTruthy();
    expect(screen.getByText('Dieselben Fakten und Quellen mit dem strukturellen TypeDB-Schema im Modellkontext; ohne Entscheidungsfunktionen.')).toBeTruthy();
    await user.click(screen.getByRole('button', { name: 'English' }));
    expect(screen.getByRole('checkbox', { name: 'TypeDB + schema' })).toBeTruthy();
    await user.click(screen.getByRole('button', { name: 'Compare approaches' }));
    const post = vi.mocked(fetch).mock.calls.find(([, options]) => options?.method === 'POST');
    expect(JSON.parse(String(post?.[1]?.body)).configurations).toEqual(['rag', 'sql', 'typedb_schema']);
  });

  it('defaults to German and presents translated cases, reference reasoning and source summaries', async () => {
    window.localStorage.removeItem('tax-benchmark-language');
    caseSnapshot = { ...payment, id: 'dev-01' };
    const user = userEvent.setup();
    render(<App />);
    expect(await screen.findByRole('heading', { name: 'Deutscher Steuerabzug auf Dividenden' })).toBeTruthy();
    expect(await screen.findByRole('heading', { name: contentDe.cases['dev-01'].title })).toBeTruthy();
    expect(await screen.findByText(contentDe.cases['dev-01'].reference_reasoning)).toBeTruthy();
    expect(screen.getAllByText('100.000,00 €')).toHaveLength(2);
    expect(screen.getAllByText('30. Juni 2026')).toHaveLength(2);
    expect(screen.getByRole('button', { name: 'Deutsch' }).getAttribute('aria-pressed')).toBe('true');
    expect(document.documentElement.lang).toBe('de');
    expect(window.localStorage.getItem('tax-benchmark-language')).toBe('de');
    await user.click(screen.getByRole('button', { name: 'Referenzbelege prüfen' }));
    const evidence = screen.getByRole('dialog', { name: 'Belege und Antwort' });
    expect(within(evidence).getByText(contentDe.sources['estg-50c'].text)).toBeTruthy();
    expect(within(evidence).getByText('Originalbeleg')).toBeTruthy();
    expect(within(evidence).getByText(payment.documents[0].text)).toBeTruthy();
    const source = within(evidence).getByRole('link', { name: contentDe.sources['estg-50c'].title });
    expect(source.getAttribute('href')).toBe('https://www.gesetze-im-internet.de/estg/__50c.html');
    expect(vi.mocked(fetch).mock.calls.some(([, options]) => options?.method === 'POST')).toBe(false);
  });

  it('switches in place and restores the persisted language after remounting', async () => {
    window.localStorage.removeItem('tax-benchmark-language');
    const user = userEvent.setup();
    const mounted = render(<App />);
    await screen.findByRole('heading', { name: 'Beispielauswertung' });
    await user.selectOptions(screen.getByRole('combobox', { name: 'Agenten-Framework' }), 'crewai');
    await user.click(screen.getByRole('button', { name: 'English' }));
    expect(screen.getByRole('heading', { name: 'German dividend withholding tax' })).toBeTruthy();
    expect((screen.getByRole('combobox', { name: 'Agent harness' }) as HTMLSelectElement).value).toBe('crewai');
    expect(window.localStorage.getItem('tax-benchmark-language')).toBe('en');
    expect(document.documentElement.lang).toBe('en');
    mounted.unmount();
    render(<App />);
    expect(await screen.findByRole('heading', { name: 'Reference walkthrough' })).toBeTruthy();
    expect(screen.getByRole('button', { name: 'English' }).getAttribute('aria-pressed')).toBe('true');
    await user.click(screen.getByRole('button', { name: 'Deutsch' }));
    expect(screen.getByRole('heading', { name: 'Beispielauswertung' })).toBeTruthy();
    expect(window.localStorage.getItem('tax-benchmark-language')).toBe('de');
  });

  it.each(['Demonstration', 'Benchmark'])('keeps the %s harness payload unchanged in German', async (page) => {
    window.localStorage.removeItem('tax-benchmark-language');
    createdRun = { ...run, request: { harness: 'crewai' } };
    const user = userEvent.setup();
    render(<App />);
    await screen.findByText('Example GmbH');
    if (page === 'Benchmark') {
      await user.click(screen.getByRole('button', { name: 'Benchmark' }));
      await user.selectOptions(screen.getByRole('combobox', { name: 'Datensatzaufteilung filtern' }), 'development');
      await user.click(screen.getByRole('button', { name: 'Angezeigte auswählen' }));
    }
    await user.selectOptions(screen.getByRole('combobox', { name: 'Agenten-Framework' }), 'crewai');
    await user.click(screen.getByRole('button', { name: page === 'Benchmark' ? 'Benchmark starten' : 'Ansätze vergleichen' }));
    await screen.findByRole('heading', { name: page === 'Benchmark' ? 'Laufergebnisse' : 'Gemessener Vergleich' });
    const post = vi.mocked(fetch).mock.calls.find(([, options]) => options?.method === 'POST');
    expect(JSON.parse(String(post?.[1]?.body))).toEqual({ case_ids: ['case-1'], model_ids: ['local'], configurations: ['rag', 'sql'], repetitions: 1, max_steps: 6, harness: 'crewai' });
    await user.click(screen.getByRole('button', { name: 'Antwort für Quellenrecherche prüfen' }));
    const evidence = screen.getByRole('dialog', { name: 'Belege und Antwort' });
    expect(within(evidence).getByRole('heading', { name: 'Originalantwort' })).toBeTruthy();
    expect(within(evidence).getByText(answer.reasoning)).toBeTruthy();
    await user.click(within(evidence).getByRole('button', { name: 'Werkzeugprotokoll' }));
    expect(within(evidence).getByText(/read_source/)).toBeTruthy();
  });

  it('keeps German controls usable when saved preferences cannot be read or written', async () => {
    vi.stubGlobal('localStorage', { getItem: () => { throw new Error('blocked'); }, setItem: () => { throw new Error('blocked'); } });
    const user = userEvent.setup();
    render(<App />);
    await screen.findByRole('heading', { name: 'Beispielauswertung' });
    await user.click(screen.getByRole('button', { name: 'English' }));
    expect(screen.getByRole('heading', { name: 'Reference walkthrough' })).toBeTruthy();
  });

  it('formats recorded German metrics and preserves structured embedding usage as an original record', async () => {
    window.localStorage.removeItem('tax-benchmark-language');
    createdRun = { ...run, trials: [{ ...run.trials[0], metrics: { ...run.trials[0].metrics, cached_tokens: 1000, estimated_cost_usd: 0.012345, provider_reported_cost_usd: 0.02, embedding_usage: [{ model: 'embed-1', tokens: 12 }] } }] } as unknown as Run;
    const user = userEvent.setup();
    render(<App />);
    await screen.findByText('Example GmbH');
    await user.click(screen.getByRole('button', { name: 'Ansätze vergleichen' }));
    await user.click(await screen.findByRole('button', { name: 'Antwort für Quellenrecherche prüfen' }));
    await user.click(screen.getByRole('button', { name: 'Strukturierte Antwort' }));
    expect(screen.getByText('Tokens aus dem Cache')).toBeTruthy();
    expect(screen.getByText('1.000')).toBeTruthy();
    expect(screen.getByText('Geschätzte Kosten (USD)')).toBeTruthy();
    expect(screen.getByText('0,012345 $')).toBeTruthy();
    expect(screen.getByText('0,020000 $')).toBeTruthy();
    const usage = screen.getByText('Embedding-Verbrauch').closest('div')!;
    expect(within(usage).getByText('Originalaufzeichnung')).toBeTruthy();
    await user.click(within(usage).getByText('Originalaufzeichnung'));
    expect(within(usage).getByText(/embed-1/)).toBeTruthy();
    expect(within(usage).queryByText('NaN')).toBeNull();
  });
});

describe('the demonstration', () => {
  it('shows one provider-shared budget and refreshes it during active polling and terminal interruption', async () => {
    createdRun = { ...run, status: 'running', completed_trials: 0, trials: [] };
    polledRun = createdRun;
    const user = userEvent.setup();
    render(<App />);
    expect(await screen.findByText('€30 experiment limit')).toBeTruthy();
    const budget = screen.getByRole('region', { name: 'Shared experiment budget' });
    expect(within(budget).getByText('€23.00')).toBeTruthy();
    expect(within(budget).getByText('Allocated')).toBeTruthy();
    expect(within(budget).getByText(/Shared across all providers/)).toBeTruthy();
    expect(within(budget).getByText(/estimates include a safety buffer/)).toBeTruthy();
    expect(within(budget).getByText(/unknown charges stay reserved/)).toBeTruthy();
    await screen.findByText('Example GmbH');
    await user.click(screen.getByRole('button', { name: 'Compare approaches' }));
    await screen.findByRole('heading', { name: 'Measured comparison' });
    budgetSnapshot = { ...budgetSnapshot, spent_eur: 6, reserved_eur: 4, committed_eur: 10, remaining_eur: 20 };
    await waitFor(() => expect(within(budget).getByText('€20.00')).toBeTruthy(), { timeout: 3500 });
    budgetSnapshot = { ...budgetSnapshot, spent_eur: 7, reserved_eur: 23, committed_eur: 30, remaining_eur: 0, blocked: true };
    polledRun = { ...createdRun, status: 'interrupted', error: 'Experiment budget stopped this run: limit reached.' };
    expect(await screen.findByText('Experiment budget stopped this run: limit reached.', {}, { timeout: 3500 })).toBeTruthy();
    await waitFor(() => expect(within(budget).getByText('€0.00')).toBeTruthy());
    expect(within(budget).getByText('New calls paused')).toBeTruthy();
    expect((screen.getByRole('button', { name: 'Compare approaches' }) as HTMLButtonElement).disabled).toBe(true);
  }, 8000);

  it('keeps the reference workspace available when the budget endpoint fails', async () => {
    budgetUnavailable = true;
    render(<App />);
    expect(await screen.findByRole('heading', { name: 'Reference walkthrough' })).toBeTruthy();
    expect(await screen.findByText('Budget status unavailable. The server still checks the limit before model calls.')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Inspect reference evidence' })).toBeTruthy();
  });

  it('shows a labeled reference with its payment amounts and legal evidence', async () => {
    const user = userEvent.setup();
    render(<App />);
    expect(await screen.findByText('Example GmbH')).toBeTruthy();
    expect(await screen.findByRole('heading', { name: 'Reference walkthrough' })).toBeTruthy();
    expect(screen.getByText('The valid exemption certificate supports relief at payment.')).toBeTruthy();
    await user.click(screen.getByRole('button', { name: /Inspect reference evidence/i }));
    const evidence = screen.getByRole('dialog', { name: /Evidence and answer/i });
    const explainer = screen.getByRole('heading', { name: 'What changes between approaches?' });
    expect(evidence.compareDocumentPosition(explainer) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(within(evidence).getByText('A source summary about the exemption procedure.')).toBeTruthy();
    expect(within(evidence).getByText('A synthetic certificate, valid on the payment date.')).toBeTruthy();
  });

  it('runs the chosen model and opens the resulting answer and tool trace', async () => {
    const user = userEvent.setup();
    render(<App />);
    await screen.findByText('Example GmbH');
    await user.click(screen.getByRole('button', { name: 'Compare approaches' }));
    expect(await screen.findByRole('heading', { name: 'Measured comparison' })).toBeTruthy();
    await user.click(screen.getByRole('button', { name: /Inspect Retrieval baseline answer/i }));
    const evidence = screen.getByRole('dialog', { name: /Evidence and answer/i });
    const explainer = screen.getByRole('heading', { name: 'What changes between approaches?' });
    expect(evidence.compareDocumentPosition(explainer) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    await user.click(within(evidence).getByRole('button', { name: 'Tool trace' }));
    expect(within(evidence).getByText(/read_source/)).toBeTruthy();
    const createCall = vi.mocked(fetch).mock.calls.find(([, options]) => options?.method === 'POST');
    expect(JSON.parse(String(createCall?.[1]?.body))).toEqual({ case_ids: ['case-1'], model_ids: ['local'], configurations: ['rag', 'sql'], repetitions: 1, max_steps: 6, harness: 'direct' });
  });

  it.each(['Demonstration', 'Benchmark'])('starts a %s run with the selected harness and the same approaches', async (page) => {
    createdRun = { ...run, request: { harness: 'crewai' } };
    const user = userEvent.setup();
    render(<App />);
    await screen.findByText('Example GmbH');
    if (page === 'Benchmark') {
      await user.click(screen.getByRole('button', { name: 'Benchmark' }));
      await user.selectOptions(screen.getByRole('combobox', { name: 'Filter dataset split' }), 'development');
      await user.click(screen.getByRole('button', { name: 'Select shown' }));
    }
    const harness = screen.getByRole('combobox', { name: 'Agent harness' });
    expect((harness as HTMLSelectElement).value).toBe('direct');
    await user.selectOptions(harness, 'crewai');
    expect(screen.getByText('Single agent; memory/delegation/planning disabled')).toBeTruthy();
    await user.click(screen.getByRole('button', { name: page === 'Benchmark' ? 'Start benchmark' : 'Compare approaches' }));
    await screen.findByRole('heading', { name: page === 'Benchmark' ? 'Run results' : 'Measured comparison' });
    const createCall = vi.mocked(fetch).mock.calls.find(([, options]) => options?.method === 'POST');
    expect(JSON.parse(String(createCall?.[1]?.body))).toEqual({ case_ids: ['case-1'], model_ids: ['local'], configurations: ['rag', 'sql'], repetitions: 1, max_steps: 6, harness: 'crewai' });
    if (page === 'Demonstration') await user.click(screen.getByRole('button', { name: 'Benchmark' }));
    expect(screen.getByRole('button', { name: /run-1.*CrewAI/ }).textContent).toContain('CrewAI');
    expect(screen.getByText('run-1 · CrewAI · Provisional evaluation')).toBeTruthy();
  });

  it.each(['unavailable CrewAI', 'missing harness endpoint'])('keeps direct runs available with %s', async (state) => {
    crewaiAvailable = false;
    harnessesUnavailable = state === 'missing harness endpoint';
    const user = userEvent.setup();
    render(<App />);
    await screen.findByText('Example GmbH');
    expect((screen.getByRole('combobox', { name: 'Agent harness' }) as HTMLSelectElement).value).toBe('direct');
    expect((screen.getByRole('option', { name: /CrewAI/ }) as HTMLOptionElement).disabled).toBe(true);
    await user.click(screen.getByRole('button', { name: 'Benchmark' }));
    expect((screen.getByRole('option', { name: /CrewAI/ }) as HTMLOptionElement).disabled).toBe(true);
    await user.click(screen.getByRole('button', { name: 'Demonstration' }));
    await user.click(screen.getByRole('button', { name: 'Compare approaches' }));
    await screen.findByRole('heading', { name: 'Measured comparison' });
    const createCall = vi.mocked(fetch).mock.calls.find(([, options]) => options?.method === 'POST');
    expect(JSON.parse(String(createCall?.[1]?.body)).harness).toBe('direct');
    expect(screen.queryByRole('alert')).toBeNull();
  });

  it('identifies older saved runs as direct in history and both result views', async () => {
    savedRuns = [run];
    const user = userEvent.setup();
    render(<App />);
    await screen.findByText('Example GmbH');
    await user.click(screen.getByRole('button', { name: 'Benchmark' }));
    const savedRun = screen.getByRole('button', { name: /run-1.*Direct agent/ });
    await user.click(savedRun);
    expect(await screen.findByText('run-1 · Direct agent · Provisional evaluation')).toBeTruthy();
    await user.click(screen.getByRole('button', { name: 'Demonstration' }));
    const results = screen.getByRole('heading', { name: 'Measured comparison' }).closest('section')!;
    expect(within(results).getByText(/Direct agent · Same case/)).toBeTruthy();
  });

  it('keeps the reference accessible when no model is configured', async () => {
    configured = false;
    render(<App />);
    await screen.findByText('Example GmbH');
    expect((screen.getByRole('button', { name: 'Compare approaches' }) as HTMLButtonElement).disabled).toBe(true);
    expect(await screen.findByRole('heading', { name: 'Reference walkthrough' })).toBeTruthy();
    expect(screen.getByText(/Configure a model endpoint/)).toBeTruthy();
  });

  it('shows an actionable server error without losing the selected case', async () => {
    rejectRun = true;
    const user = userEvent.setup();
    render(<App />);
    await screen.findByText('Example GmbH');
    await user.click(screen.getByRole('button', { name: 'Compare approaches' }));
    await waitFor(() => expect(screen.getByRole('alert').textContent).toContain('Start the database and retry.'));
    expect(screen.getByText('Example GmbH')).toBeTruthy();
  });

  it('distinguishes incorrect answers from execution errors in older saved summaries', async () => {
    createdRun = {
      ...run,
      completed_trials: 2, total_trials: 2,
      trials: [{ ...run.trials[0], passed: false }, { ...run.trials[0], id: 'trial-2', status: 'failed', passed: false, answer: null, error: 'The provider call failed.' }],
      summary: [{ model_id: 'local', configuration: 'rag', trials: 2, passed: 0, failed: 2, pass_rate: 0, avg_wall_time_ms: null, avg_input_tokens: null, avg_output_tokens: null, avg_total_tokens: null }],
    };
    const user = userEvent.setup();
    render(<App />);
    await screen.findByText('Example GmbH');
    await user.click(screen.getByRole('button', { name: 'Compare approaches' }));
    await user.click(screen.getByRole('button', { name: 'Benchmark' }));
    const aggregate = screen.getByLabelText('Aggregate results');
    const headings = within(aggregate).getAllByRole('columnheader').map((cell) => cell.textContent);
    expect(headings).toContain('Execution errors');
    expect(headings).toContain('Incorrect answers');
    const cells = within(aggregate).getAllByRole('row')[1].querySelectorAll('td');
    expect(cells[headings.indexOf('Execution errors')].textContent).toBe('1');
    expect(cells[headings.indexOf('Incorrect answers')].textContent).toBe('1');
  });

  it.each(['failed', 'cancelled', 'interrupted'])('shows a %s run error with no trials in both result views', async (status) => {
    createdRun = { ...run, status, completed_trials: 0, trials: [], error: 'The run stopped before a trial could be recorded.' } as Run;
    const user = userEvent.setup();
    render(<App />);
    await screen.findByText('Example GmbH');
    await user.click(screen.getByRole('button', { name: 'Compare approaches' }));
    expect(await screen.findByText('The run stopped before a trial could be recorded.')).toBeTruthy();
    expect(screen.queryByText(/Waiting for the first trial/)).toBeNull();
    await user.click(screen.getByRole('button', { name: 'Benchmark' }));
    expect(screen.getByText('The run stopped before a trial could be recorded.')).toBeTruthy();
    expect(screen.queryByText(/Trials will appear as the runner starts/)).toBeNull();
  });

  it('exposes an interrupted trial checkpoint without treating partial usage as final', async () => {
    createdRun = { ...run, status: 'interrupted', completed_trials: 0, trials: [], active_trial: { case_id: 'case-1', model_id: 'local', configuration: 'rag', repetition: 1, status: 'running', usage_complete: false, metrics: { input_tokens: null }, trace: [{ tool: 'read_source', result: { id: 'estg-50c' } }] } } as Run;
    const user = userEvent.setup();
    render(<App />);
    await screen.findByText('Example GmbH');
    await user.click(screen.getByRole('button', { name: 'Compare approaches' }));
    expect(await screen.findByRole('heading', { name: 'Interrupted trial checkpoint' })).toBeTruthy();
    expect(screen.getByText(/Usage may be incomplete/)).toBeTruthy();
    await user.click(screen.getByText('Recorded checkpoint trace'));
    expect(screen.getByText(/read_source/)).toBeTruthy();
  });

  it('keeps cancellation pending until the worker records the late call and final status', async () => {
    createdRun = { ...run, status: 'running', completed_trials: 0, trials: [] };
    cancelledRun = { ...createdRun, cancellation_requested: true } as Run;
    polledRun = { ...run, status: 'cancelled', cancellation_requested: true, trials: [{ ...run.trials[0], status: 'cancelled', passed: false, answer: null, error: 'Cancelled after recording the in-flight model response; no following tool was started' }] } as Run;
    const user = userEvent.setup();
    render(<App />);
    await screen.findByText('Example GmbH');
    await user.click(screen.getByRole('button', { name: 'Compare approaches' }));
    await user.click(await screen.findByRole('button', { name: 'Cancel run' }));
    const cancelling = await screen.findByRole('button', { name: 'Cancelling after current call' });
    expect((cancelling as HTMLButtonElement).disabled).toBe(true);
    expect(await screen.findByRole('button', { name: /Inspect Retrieval baseline answer/i }, { timeout: 3500 })).toBeTruthy();
    expect(screen.getByText('1 of 1 trials complete')).toBeTruthy();
    expect(screen.getAllByText('Cancelled')).toHaveLength(2);
    expect(screen.getByText('200')).toBeTruthy();
    expect(screen.getByText('0.90 s')).toBeTruthy();
    await user.click(screen.getByRole('button', { name: /Inspect Retrieval baseline answer/i }));
    expect(screen.getByText(/Cancelled after recording the in-flight model response/)).toBeTruthy();
    await user.click(screen.getByRole('button', { name: 'Tool trace' }));
    expect(screen.getByText(/read_source/)).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Cancelling after current call' })).toBeNull();
    expect(vi.mocked(fetch).mock.calls.filter(([path, options]) => path === '/api/runs/run-1/cancel' && options?.method === 'POST')).toHaveLength(1);
  });
});
