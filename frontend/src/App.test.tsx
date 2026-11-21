import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import App from './App';

const payment = { id: 'case-1', title: 'A valid exemption certificate', summary: 'A Dutch parent receives an ordinary dividend.', category: 'certificate', split: 'development', question: 'What must the payer withhold?', gross_amount_cents: 10000000, payment_date: '2026-06-30', knowledge_date: '2026-06-30', payer: { id: 'payer', name: 'Example GmbH', country: 'DE' }, recipient: { id: 'recipient', name: 'Example Holding BV', country: 'NL' }, facts: { direct_ownership_percent: 100, exemption_certificate: true, unknown_fact: null }, documents: [{ id: 'doc-1', title: 'Exemption certificate', text: 'A synthetic certificate, valid on the payment date.' }], source_ids: ['estg-50c'], review_status: 'provisional' };
const answer = { status: 'determined', relief_eligibility: 'eligible', relief_route: 'Parent-company relief', withholding_tax_cents: 0, solidarity_surcharge_cents: 0, total_withholding_cents: 0, net_payment_cents: 10000000, refund_status: 'not_required', refund_amount_cents: 0, missing_facts: [], source_ids: ['estg-50c'], evidence_ids: ['doc-1'], reasoning: 'The valid exemption certificate supports relief at payment.' };
const run = { id: 'run-1', status: 'completed', created_at: '2026-11-21T10:00:00Z', updated_at: '2026-11-21T10:00:00Z', completed_trials: 1, total_trials: 1, request: {}, manifest: { review_status: 'provisional' }, trials: [{ id: 'trial-1', case_id: 'case-1', model_id: 'local', configuration: 'rag', repetition: 1, status: 'completed', passed: true, answer, error: null, grading: {}, metrics: { input_tokens: 120, output_tokens: 80, wall_time_ms: 900 }, trace: [{ tool: 'read_source', result: { id: 'estg-50c' } }] }], summary: [] };
let configured = true;
let rejectRun = false;

beforeEach(() => {
  configured = true;
  rejectRun = false;
  vi.stubGlobal('fetch', vi.fn(async (path: string, options?: RequestInit) => {
    const url = String(path);
    if (url === '/api/runs' && options?.method === 'POST') {
      if (rejectRun) return new Response(JSON.stringify({ detail: 'TypeDB is unavailable. Start the database and retry.' }), { status: 503 });
      return new Response(JSON.stringify(run), { status: 202 });
    }
    const data: Record<string, unknown> = {
      '/api/health': { status: 'ok', typedb: { available: true }, legal_review: 'provisional' },
      '/api/cases': [payment],
      '/api/models': [{ id: 'local', name: 'Local model', configured, provider: 'OpenAI-compatible' }],
      '/api/configurations': [{ id: 'rag', name: 'Retrieval baseline', description: 'Source retrieval.' }, { id: 'sql', name: 'SQL control', description: 'Equivalent structured rules.' }],
      '/api/sources': [{ id: 'estg-50c', title: 'EStG §50c', locator: 'Section 50c', url: 'https://www.gesetze-im-internet.de/estg/__50c.html', text: 'A source summary about the exemption procedure.', retrieved_at: '2026-11-21', sha256: 'abc123' }],
      '/api/runs': [],
      '/api/cases/case-1/reference': { answer, kind: 'reference', review_status: 'provisional' },
      '/api/runs/run-1': run,
    };
    if (!(url in data)) return new Response(JSON.stringify({ detail: 'Not found' }), { status: 404 });
    return new Response(JSON.stringify(data[url]));
  }));
});

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe('the demonstration', () => {
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
});
