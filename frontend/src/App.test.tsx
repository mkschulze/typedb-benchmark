import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import App from './App';
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

beforeEach(() => {
  configured = true;
  rejectRun = false;
  createdRun = run; polledRun = run; cancelledRun = run;
  budgetSnapshot = { limit_eur: 30, spent_eur: 5, reserved_eur: 2, committed_eur: 7, remaining_eur: 23, blocked: false };
  budgetUnavailable = false;
  vi.stubGlobal('fetch', vi.fn(async (path: string, options?: RequestInit) => {
    const url = String(path);
    if (url === '/api/budget') return new Response(JSON.stringify(budgetUnavailable ? { detail: 'Budget unavailable' } : budgetSnapshot), { status: budgetUnavailable ? 503 : 200 });
    if (url === '/api/runs' && options?.method === 'POST') {
      if (rejectRun) return new Response(JSON.stringify({ detail: 'TypeDB is unavailable. Start the database and retry.' }), { status: 503 });
      return new Response(JSON.stringify(createdRun), { status: 202 });
    }
    if (url === '/api/runs/run-1/cancel') return new Response(JSON.stringify(cancelledRun));
    const data: Record<string, unknown> = {
      '/api/health': { status: 'ok', typedb: { available: true }, legal_review: 'provisional' },
      '/api/cases': [payment],
      '/api/models': [{ id: 'local', name: 'Local model', configured, provider: 'OpenAI-compatible' }],
      '/api/configurations': [{ id: 'rag', name: 'Retrieval baseline', description: 'Source retrieval.' }, { id: 'sql', name: 'SQL control', description: 'Equivalent structured rules.' }],
      '/api/sources': [{ id: 'estg-50c', title: 'EStG §50c', locator: 'Section 50c', url: 'https://www.gesetze-im-internet.de/estg/__50c.html', text: 'A source summary about the exemption procedure.', retrieved_at: '2026-11-21', sha256: 'abc123' }],
      '/api/runs': [],
      '/api/cases/case-1/reference': { answer, kind: 'reference', review_status: 'provisional' },
      '/api/runs/run-1': polledRun,
    };
    if (!(url in data)) return new Response(JSON.stringify({ detail: 'Not found' }), { status: 404 });
    return new Response(JSON.stringify(data[url]));
  }));
});

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

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
    expect(JSON.parse(String(createCall?.[1]?.body))).toEqual({ case_ids: ['case-1'], model_ids: ['local'], configurations: ['rag', 'sql'], repetitions: 1, max_steps: 6 });
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
