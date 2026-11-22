import { createContext, useContext, useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import contentDe from './locales/content.de.json';
import type { Configuration, DividendCase, Harness, HarnessId, Source } from './types';

type Language = 'de' | 'en';
// renamed when the default became English, so the previously auto-saved 'de' is ignored
const storageKey = 'tax-benchmark-lang';
const german: Record<string, string> = {
  'Agent harness': 'Agenten-Framework',
  'Direct agent': 'Direkter Agent',
  'Direct tool-calling agent.': 'Direkter Agent mit Werkzeugaufrufen.',
  'Single agent; memory/delegation/planning disabled': 'Ein Agent; Gedächtnis, Delegation und Planung deaktiviert',
  'Shared JSON-action agent loop; fresh state per trial.': 'Gemeinsame Agentenschleife mit JSON-Aktionen; neuer Zustand für jeden Einzelversuch.',
  'Single agent; memory, delegation, caching and planning disabled.': 'Ein Agent; Gedächtnis, Delegation, Cache und Planung deaktiviert.',
  ' — unavailable': ' — nicht verfügbar',
  'Experiment costs': 'Versuchskosten',
  'Allocated': 'Angerechnet',
  'Reserved': 'Reserviert',
  'Shared across all providers. USD→EUR estimates include a safety buffer; unknown charges stay reserved.': 'Gilt für alle Anbieter. USD→EUR-Schätzungen enthalten einen Sicherheitspuffer; unbekannte Kosten bleiben reserviert.',
  'Loading experiment costs…': 'Versuchskosten werden geladen…',
  'Cost status unavailable.': 'Kostenstatus nicht verfügbar.',
  'Unknown': 'Unbekannt',
  'Yes': 'Ja',
  'No': 'Nein',
  'The dividend case': 'Der Dividendenfall',
  'Synthetic': 'Synthetisch',
  'Gross dividend': 'Bruttodividende',
  'German payer': 'Deutsche Zahlstelle',
  'Dividend payment': 'Dividendenzahlung',
  'Corporate recipient': 'Empfangende Gesellschaft',
  'Payment date': 'Zahlungsdatum',
  'Information cutoff': 'Informationsstand',
  'Dataset split': 'Datensatzaufteilung',
  'The question': 'Die Fragestellung',
  'View all case facts': 'Alle Fallangaben anzeigen',
  'Supporting documents': 'Belege',
  'Withholding at payment': 'Steuerabzug bei Zahlung',
  'Withholding tax': 'Kapitalertragsteuer',
  'Solidarity surcharge': 'Solidaritätszuschlag',
  'Net payment': 'Nettozahlung',
  'Relief eligibility': 'Entlastungsberechtigung',
  'Relief route': 'Entlastungsweg',
  'EStG §43b · EU parent-company relief': 'EStG §43b · Entlastung für EU-Muttergesellschaften',
  'Undetermined': 'Nicht bestimmbar',
  'Information needed': 'Benötigte Angaben',
  'Refund route': 'Erstattungsverfahren',
  'Possible refund': 'Mögliche Erstattung',
  'Reference walkthrough': 'Beispielauswertung',
  'Provisional': 'Vorläufig',
  'Explore the expected decision before running a model. This deterministic walkthrough has no measured LLM results.': 'Prüfen Sie die erwartete Entscheidung vor einem Modellaufruf. Diese deterministische Referenz enthält keine gemessenen LLM-Ergebnisse.',
  'Loading reference walkthrough': 'Beispielauswertung wird geladen',
  'Inspect reference evidence': 'Referenzbelege prüfen',
  'Eligibility and withholding are separate decisions.': 'Berechtigung und Steuerabzug sind getrennte Entscheidungen.',
  'Relief may be available even when the payer must withhold at the payment date.': 'Eine Entlastung kann möglich sein, auch wenn die Zahlstelle am Zahlungstag Steuern einbehalten muss.',
  'of': 'von',
  'trials complete': 'Einzelversuchen abgeschlossen',
  'Cancelling after current call': 'Abbruch nach aktuellem Aufruf',
  'Requesting cancellation…': 'Abbruch wird angefordert…',
  'Cancel run': 'Lauf abbrechen',
  'Run progress': 'Lauffortschritt',
  'Run error': 'Fehler im Lauf',
  'The current call is finishing. Its recorded usage and trace will appear before cancellation is final.': 'Der aktuelle Aufruf wird beendet. Verbrauch und Ablaufprotokoll werden vor dem endgültigen Abbruch gespeichert.',
  'Waiting for the first trial. Results appear as each approach completes.': 'Warten auf den ersten Einzelversuch. Ergebnisse erscheinen, sobald ein Ansatz abgeschlossen ist.',
  'No trials were recorded. This run is {status}.': 'Es wurden keine Einzelversuche gespeichert. Status dieses Laufs: {status}.',
  'Interrupted trial checkpoint': 'Zwischenstand des unterbrochenen Einzelversuchs',
  'Case:': 'Fall:',
  '· Model:': '· Modell:',
  '· Approach:': '· Ansatz:',
  '· Repetition': '· Wiederholung',
  'Usage may be incomplete. This checkpoint is a partial record, not a completed answer.': 'Der Verbrauch kann unvollständig sein. Dieser Zwischenstand enthält eine Teilaufzeichnung, keine fertige Antwort.',
  'Recorded checkpoint trace': 'Gespeichertes Ablaufprotokoll',
  'No tool trace was saved before the interruption.': 'Vor der Unterbrechung wurde kein Werkzeugprotokoll gespeichert.',
  'Recorded checkpoint usage': 'Gespeicherter Verbrauch',
  'The worker stopped before the active trial completed. No active-trial checkpoint was saved; any completed trials remain available below.': 'Der Prozess wurde vor Abschluss des aktiven Einzelversuchs beendet. Ein Zwischenstand wurde nicht gespeichert; abgeschlossene Einzelversuche bleiben unten verfügbar.',
  'Comparison results': 'Vergleichsergebnisse',
  'Case / model': 'Fall / Modell',
  'Approach': 'Ansatz',
  'Withholding': 'Steuerabzug',
  'Tokens': 'Tokens',
  'Elapsed': 'Dauer',
  'Result': 'Ergebnis',
  'Inspect answer': 'Antwort prüfen',
  'Inspect {name} answer': 'Antwort für {name} prüfen',
  '· repetition': '· Wiederholung',
  'Pass': 'Bestanden',
  'Mismatch': 'Abweichung',
  'Evidence and answer': 'Belege und Antwort',
  'Close evidence': 'Belegansicht schließen',
  'Answer details': 'Antwortdetails',
  'Sources and facts': 'Quellen und Fakten',
  'Structured answer': 'Strukturierte Antwort',
  'Recorded usage': 'Erfasster Verbrauch',
  'Tool trace': 'Werkzeugprotokoll',
  'No final answer was recorded for this attempt. Recorded trace and usage remain available.': 'Für diesen Versuch wurde keine abschließende Antwort gespeichert. Protokoll und Verbrauch bleiben verfügbar.',
  'Legal sources': 'Rechtsquellen',
  'No legal sources were cited in this answer.': 'In dieser Antwort wurden keine Rechtsquellen zitiert.',
  '· Source summary': '· Quellenzusammenfassung',
  'Retrieved': 'Abgerufen am',
  'Cited source “': 'Die zitierte Quelle „',
  '” is not in this source snapshot.': '“ ist in diesem Quellenstand nicht enthalten.',
  'Case evidence': 'Fallbelege',
  'No supporting documents were cited. The case facts remain available in the dividend panel.': 'Es wurden keine Belege zitiert. Die Fallangaben stehen weiterhin im Dividendenfall.',
  'Answer justification': 'Begründung der Antwort',
  'No final answer was recorded.': 'Es wurde keine abschließende Antwort gespeichert.',
  'View answer JSON': 'Antwort als JSON anzeigen',
  'Unavailable': 'Nicht verfügbar',
  'Provisional grading': 'Vorläufige Bewertung',
  'Recorded tool requests and returned evidence. This view does not expose hidden model reasoning.': 'Gespeicherte Werkzeugaufrufe und zurückgegebene Belege im Original. Verborgene Modellüberlegungen werden nicht angezeigt.',
  'Trace event': 'Protokollereignis',
  'No tool events were recorded for this trial.': 'Für diesen Einzelversuch wurden keine Werkzeugereignisse gespeichert.',
  'Skip to workspace': 'Zum Arbeitsbereich springen',
  'Tax Context Benchmark home': 'Tax Context Benchmark Startseite',
  'Main navigation': 'Hauptnavigation',
  'Research preview': 'Forschungsvorschau',
  'German dividend withholding tax': 'Deutscher Steuerabzug auf Dividenden',
  'Benchmark workspace': 'Benchmark-Arbeitsbereich',
  'Source register': 'Quellenverzeichnis',
  'One dividend. Five approaches. Follow the facts behind the answer.': 'Eine Dividende. Fünf Ansätze. Verfolgen Sie die Fakten hinter der Antwort.',
  'Run reproducible comparisons across cases, models and approaches.': 'Vergleichen Sie Fälle, Modelle und Ansätze in reproduzierbaren Läufen.',
  'The official legal material behind every approach, preserved in a shared source snapshot.': 'Die amtlichen Rechtsquellen aller Ansätze, in einem gemeinsamen Quellenstand festgehalten.',
  'connected': 'verbunden',
  'not connected': 'nicht verbunden',
  'Connection problem': 'Verbindungsproblem',
  'Action could not complete': 'Aktion konnte nicht abgeschlossen werden',
  'Retry': 'Erneut versuchen',
  'Loading workspace': 'Arbeitsbereich wird geladen',
  'No dividend cases are available': 'Keine Dividendenfälle verfügbar',
  'Load the synthetic dataset on the server, then refresh the workspace.': 'Laden Sie den synthetischen Datensatz auf dem Server und aktualisieren Sie den Arbeitsbereich.',
  'Refresh workspace': 'Arbeitsbereich aktualisieren',
  'Comparison settings': 'Vergleichseinstellungen',
  'Dividend case': 'Dividendenfall',
  'Language model': 'Sprachmodell',
  'No model configured': 'Kein Modell konfiguriert',
  ' — setup required': ' — Einrichtung erforderlich',
  'Starting comparison…': 'Vergleich wird gestartet…',
  'Comparison running…': 'Vergleich läuft…',
  'Compare approaches': 'Ansätze vergleichen',
  'Your reference walkthrough is ready.': 'Ihre Beispielauswertung ist bereit.',
  'Configure a model endpoint on the server to measure answers, tokens and elapsed time.': 'Konfigurieren Sie einen Modellendpunkt auf dem Server, um Antworten, Tokens und Laufzeit zu messen.',
  'Model setup': 'Modelleinrichtung',
  'Set': 'Setzen Sie',
  'in the server environment with your model identifier, endpoint and API-key variable, then restart the server. Local endpoints can run without an API key. No live model calls run by default.': 'in der Serverumgebung mit Modellkennung, Endpunkt und API-Schlüsselvariable und starten Sie den Server neu. Lokale Endpunkte können ohne API-Schlüssel laufen. Standardmäßig werden keine Live-Modellaufrufe gestartet.',
  'Measured comparison': 'Gemessener Vergleich',
  'Provisional scores': 'Vorläufige Bewertung',
  '· Same case, source snapshot and trial budget.': '· Gleicher Fall, Quellenstand und Versuchsrahmen.',
  'Pass means the answer met the provisional rubric. Invalid answers and execution failures remain in the denominator. Budget-stopped incomplete trials are excluded. Missing token usage is unavailable.': '„Bestanden“ bedeutet, dass die Antwort das vorläufige Bewertungsschema erfüllt. Ungültige Antworten und Ausführungsfehler zählen zum Nenner. Wegen des Budgets unvollständige Einzelversuche sind ausgeschlossen. Fehlende Tokenangaben sind nicht verfügbar.',
  'Export run JSON': 'Lauf als JSON exportieren',
  'Return to reference walkthrough': 'Zurück zur Beispielauswertung',
  'Provisional reference walkthrough': 'Vorläufige Beispielauswertung',
  'What changes between approaches?': 'Was unterscheidet die Ansätze?',
  'The model and question stay the same. The available context changes.': 'Modell und Fragestellung bleiben gleich. Der verfügbare Kontext ändert sich.',
  'Shared legal corpus': 'Gemeinsamer Rechtsquellenbestand',
  'The same material is available to all four approaches.': 'Allen vier Ansätzen steht dasselbe Material zur Verfügung.',
  'Find a source': 'Quelle suchen',
  'Search title, statute or passage': 'Titel, Gesetz oder Passage suchen',
  'Passages below are concise source summaries. Open the official source to read its full wording. The legal review and expected answers remain provisional.': 'Die folgenden Passagen sind kurze Quellenzusammenfassungen. Den vollständigen Wortlaut finden Sie in der amtlichen Quelle. Die rechtliche Prüfung und die erwarteten Antworten bleiben vorläufig.',
  'Snapshot and provenance': 'Quellenstand und Herkunft',
  'Source ID': 'Quellen-ID',
  'No sources match “': 'Keine Quellen für „',
  'Try a statute name or a shorter search term.': 'Versuchen Sie einen Gesetzesnamen oder einen kürzeren Suchbegriff.',
  'Clear search': 'Suche zurücksetzen',
  'Synthetic cases · Provisional legal review · No improvement assumed': 'Synthetische Fälle · Vorläufige rechtliche Prüfung · Keine Verbesserung unterstellt',
  'Explore the sources': 'Quellen erkunden',
  'Configure a run': 'Lauf konfigurieren',
  'Evaluation cases are held out. Use development cases for setup and smoke tests; each trial starts a fresh conversation.': 'Evaluationsfälle bleiben für die Auswertung zurückgehalten. Verwenden Sie Entwicklungsfälle zur Einrichtung und für Kurztests; jeder Einzelversuch beginnt ein neues Gespräch.',
  'Cases': 'Fälle',
  'selected': 'ausgewählt',
  'Filter dataset split': 'Datensatzaufteilung filtern',
  'Development cases': 'Entwicklungsfälle',
  'Evaluation cases': 'Evaluationsfälle',
  'All cases': 'Alle Fälle',
  'Select shown': 'Angezeigte auswählen',
  'Clear': 'Zurücksetzen',
  'Selected scope:': 'Auswahlumfang:',
  'No cases selected': 'Keine Fälle ausgewählt',
  'Models': 'Modelle',
  'Server configuration required': 'Serverkonfiguration erforderlich',
  'Approaches': 'Ansätze',
  'Repetitions': 'Wiederholungen',
  'Max model steps': 'Max. Modellschritte',
  'trials': 'Einzelversuche',
  'Provider calls may incur costs.': 'Anbieteraufrufe können Kosten verursachen.',
  'Starting…': 'Wird gestartet…',
  'Start benchmark': 'Benchmark starten',
  'Reduce the selection to 1,800 trials or fewer.': 'Reduzieren Sie die Auswahl auf höchstens 1.800 Einzelversuche.',
  'Configure a model on the server before starting a benchmark.': 'Konfigurieren Sie vor dem Benchmark-Start ein Modell auf dem Server.',
  'Run history': 'Laufhistorie',
  'Your first comparison starts here': 'Hier beginnt Ihr erster Vergleich',
  'Completed answers, usage, errors and the reproducibility manifest will be saved for each run.': 'Für jeden Lauf werden fertige Antworten, Verbrauch, Fehler und das Reproduzierbarkeitsmanifest gespeichert.',
  'No measured benchmark results yet.': 'Noch keine gemessenen Benchmark-Ergebnisse.',
  'A controlled comparison': 'Ein kontrollierter Vergleich',
  'All approaches share the question, model, source corpus and step budget. Results are graded against an independently specified provisional rubric.': 'Alle Ansätze verwenden dieselbe Fragestellung, dasselbe Modell, denselben Quellenbestand und dieselbe Schrittgrenze. Bewertet wird nach einem unabhängig festgelegten, vorläufigen Schema.',
  'Scores include failed trials. No accuracy or efficiency improvement is assumed.': 'Fehlgeschlagene Einzelversuche fließen in die Bewertung ein. Eine Verbesserung der Genauigkeit oder Effizienz wird nicht unterstellt.',
  'Run results': 'Laufergebnisse',
  '· Provisional evaluation': '· Vorläufige Auswertung',
  'Export JSON': 'JSON exportieren',
  'Aggregate results': 'Aggregierte Ergebnisse',
  'Model / approach': 'Modell / Ansatz',
  'Strict pass': 'Streng bestanden',
  'Incorrect answers': 'Falsche Antworten',
  'Execution errors': 'Ausführungsfehler',
  'Cancelled': 'Abgebrochen',
  'Avg. tokens': 'Ø Tokens',
  'Avg. elapsed': 'Ø Dauer',
  'Individual trials': 'Einzelversuche',
  'Reproducibility manifest': 'Reproduzierbarkeitsmanifest',
  'Frozen inputs, model settings, source hashes and execution limits for this run.': 'Festgeschriebene Eingaben, Modelleinstellungen, Quellen-Hashes und Ausführungsgrenzen dieses Laufs.',
  'Language': 'Sprache',
  'Original answer': 'Originalantwort',
  'Original document': 'Originalbeleg',
  'Original record': 'Originalaufzeichnung',
  'Original message': 'Originalmeldung',
  'The workspace could not load.': 'Der Arbeitsbereich konnte nicht geladen werden.',
  'Could not refresh this run.': 'Dieser Lauf konnte nicht aktualisiert werden.',
  'Request failed ({status}). Please retry.': 'Anfrage fehlgeschlagen ({status}). Bitte versuchen Sie es erneut.',
  'TypeDB is unavailable. Start the database and retry.': 'TypeDB ist nicht verfügbar. Starten Sie die Datenbank und versuchen Sie es erneut.',
  'Failed to fetch': 'Verbindung fehlgeschlagen. Bitte versuchen Sie es erneut.',
  'NetworkError when attempting to fetch resource.': 'Verbindung fehlgeschlagen. Bitte versuchen Sie es erneut.',
  'Retrieval baseline': 'Retrieval-Basislinie',
  'SQL control': 'SQL-Kontrolle',
  'Source retrieval.': 'Abruf von Rechtsquellen.',
  'Equivalent structured rules.': 'Gleichwertige strukturierte Regeln.',
  '§43a(1) no.1 and (2)': '§43a Abs. 1 Nr. 1 und Abs. 2',
  '§43b(1), (2)': '§43b Abs. 1 und 2',
  'Annex 2 nos.1(t), 2, 3 and German GmbH entry 1(f)': 'Anlage 2 Nr. 1 Buchst. t, Nr. 2 und 3 sowie deutsche GmbH nach Nr. 1 Buchst. f',
  '§44(1), especially sentences 2, 3 and 6': '§44 Abs. 1, insbesondere Sätze 2, 3 und 6',
  '§50c(1), (2) no.1, (3)': '§50c Abs. 1, Abs. 2 Nr. 1 und Abs. 3',
  '§50d(3)': '§50d Abs. 3',
  '§44a(9)': '§44a Abs. 9',
  '§32, especially (5) and (6)': '§32, insbesondere Abs. 5 und 6',
  '§3(1) no.5': '§3 Abs. 1 Nr. 5',
  'Exemption from capital-income withholding': 'Freistellung vom Kapitalertragsteuerabzug',
  'Refund service description': 'Beschreibung des Erstattungsverfahrens',
  'BGBl. 2026 II no.102; Articles 2(3), 10(2),(4), 26': 'BGBl. 2026 II Nr. 102; Art. 2 Abs. 3, Art. 10 Abs. 2 und 4 sowie Art. 26',
  'Protocol 14 April 2025 and consolidated text 2026': 'Protokoll vom 14. April 2025 und konsolidierte Fassung 2026',
  'Local implementation scope; linked primary law, not an official legal text': 'Lokaler Umsetzungsumfang; verknüpftes Primärrecht, kein amtlicher Gesetzestext',
  'Retrieved current official text; application to 2026 fixtures provisional pending independent legal review. No inferred historical version changes.': 'Aktueller amtlicher Text abgerufen; die Anwendung auf die Fälle von 2026 bleibt bis zu einer unabhängigen rechtlichen Prüfung vorläufig. Historische Fassungsänderungen werden nicht unterstellt.',
  'Run setup failed. Check the configured services; completed trials are preserved.': 'Der Lauf konnte nicht eingerichtet werden. Prüfen Sie die konfigurierten Dienste; abgeschlossene Einzelversuche bleiben erhalten.',
  'The local run queue is full; wait for a run to finish': 'Die lokale Warteschlange ist voll. Warten Sie, bis ein Lauf beendet ist.',
  'Answer cites an unknown source ID': 'Die Antwort zitiert eine unbekannte Quellen-ID.',
  'Answer cites unknown case evidence': 'Die Antwort zitiert unbekannte Fallbelege.',
  'Net payment and withholding do not equal the gross amount': 'Nettozahlung und Steuerabzug ergeben zusammen nicht den Bruttobetrag.',
  'Unknown agent harness': 'Unbekanntes Agenten-Framework.',
  'The requested tool is unavailable in this configuration': 'Das angeforderte Werkzeug ist in dieser Konfiguration nicht verfügbar.',
  'Cancelled after recording the in-flight model response; no following tool was started': 'Nach Speicherung der laufenden Modellantwort abgebrochen; kein weiteres Werkzeug wurde gestartet.',
};

const configurationCopy: Record<string, { name: string; description: string }> = {
  rag: { name: 'Quellenrecherche', description: 'Das Modell durchsucht dieselben Dokumente und Fallunterlagen.' },
  typedb_context: { name: 'TypeDB-Kontext', description: 'Strukturierte Beziehungen und Belege ohne Entscheidungsfunktionen.' },
  typedb_schema: { name: 'TypeDB + Schema', description: 'Dieselben Fakten und Quellen mit dem strukturellen TypeDB-Schema im Modellkontext; ohne Entscheidungsfunktionen.' },
  typedb_functions: { name: 'TypeDB + Funktionen', description: 'Strukturierter Kontext mit ausführbarer Entscheidungslogik.' },
  sql: { name: 'SQL-Kontrolle', description: 'Gleichwertige kuratierte Fakten und Entscheidungslogik über SQL.' },
};

const extraLabels: Record<string, string> = {
  demonstration: 'Demonstration', benchmark: 'Benchmark', sources: 'Quellen',
  direct: 'Direkter Agent', development: 'Entwicklung', evaluation: 'Evaluation',
  queued: 'In Warteschlange', running: 'Läuft', completed: 'Abgeschlossen', failed: 'Fehlgeschlagen', cancelled: 'Abgebrochen', interrupted: 'Unterbrochen',
  input_tokens: 'Eingabe-Tokens', output_tokens: 'Ausgabe-Tokens', wall_time_ms: 'Gesamtdauer', cost_usd: 'Kosten (USD)',
  cached_tokens: 'Tokens aus dem Cache', reasoning_tokens: 'Reasoning-Tokens', cache_write_tokens: 'In den Cache geschriebene Tokens',
  provider_time_ms: 'Anbieterdauer', tool_calls: 'Werkzeugaufrufe', model_calls: 'Modellaufrufe',
  estimated_cost_usd: 'Geschätzte Kosten (USD)', provider_reported_cost_usd: 'Vom Anbieter gemeldete Kosten (USD)', embedding_usage: 'Embedding-Verbrauch',
  time_to_first_token_ms: 'Zeit bis zum ersten Token', tool_time_ms: 'Werkzeugdauer', model_time_ms: 'Modelldauer',
  direct_ownership_percent: 'Direkter Beteiligungsanteil (%)', exemption_certificate: 'Freistellungsbescheinigung',
  not_required: 'Nicht erforderlich',
};

function storedLanguage(): Language {
  try { return window.localStorage.getItem(storageKey) === 'de' ? 'de' : 'en'; } catch { return 'en'; }
}

function useLanguageValue() {
  const [language, setLanguage] = useState<Language>(storedLanguage);
  const locale = language === 'de' ? 'de-DE' : 'en-GB';
  useEffect(() => {
    document.documentElement.lang = language;
    try { window.localStorage.setItem(storageKey, language); } catch { /* The switch still works when storage is unavailable. */ }
  }, [language]);
  const t = (text: string, values: Record<string, string | number> = {}) => {
    const translation = language === 'de' ? german[text] ?? text : text;
    return translation.replace(/\{(\w+)\}/g, (match, key: string) => String(values[key] ?? match));
  };
  const human = (value: string) => language === 'de'
    ? (contentDe.fact_labels as Record<string, string>)[value] ?? (contentDe.value_labels as Record<string, string>)[value] ?? extraLabels[value] ?? t(value.replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase()))
    : value.replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
  const valueLabel = (value: string) => language === 'de' ? (contentDe.value_labels as Record<string, string>)[value] ?? german[value] ?? value : value;
  const number = (value: number, digits = 0) => new Intl.NumberFormat(locale, { minimumFractionDigits: digits, maximumFractionDigits: digits }).format(value);
  const euro = (value: number, limit = false) => new Intl.NumberFormat(locale, { style: 'currency', currency: 'EUR', minimumFractionDigits: limit ? 0 : 2, maximumFractionDigits: limit ? 2 : 4 }).format(value);
  const money = (cents: number | null | undefined) => cents == null ? t('Undetermined') : euro(cents / 100, false);
  const count = (value: number | null | undefined) => value == null ? t('Unavailable') : number(Math.round(value));
  const duration = (value: number | null | undefined) => value == null ? t('Unavailable') : `${number(value / 1000, 2)} s`;
  const percent = (value: number) => new Intl.NumberFormat(locale, { style: 'percent', minimumFractionDigits: 1, maximumFractionDigits: 1 }).format(value);
  const usd = (value: number) => new Intl.NumberFormat(locale, { style: 'currency', currency: 'USD', minimumFractionDigits: 6, maximumFractionDigits: 6 }).format(value);
  const date = (value: string) => { const parsed = new Date(value); return Number.isNaN(parsed.getTime()) ? value : new Intl.DateTimeFormat(locale, { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' }).format(parsed); };
  const harnessName = (id: HarnessId = 'direct') => id === 'crewai' ? 'CrewAI' : t('Direct agent');
  const localizeCase = (payment: DividendCase): DividendCase => {
    if (language !== 'de') return payment;
    const copy = (contentDe.cases as Record<string, { title: string; summary: string; question: string }>)[payment.id];
    const prose = (value: string) => value.replace(/\b\d{4}-\d{2}-\d{2}\b/g, date);
    return { ...payment, ...(copy ? { title: copy.title, summary: prose(copy.summary), question: prose(copy.question) } : {}), documents: payment.documents.map((document) => ({ ...document, title: (contentDe.document_titles as Record<string, string>)[document.title] ?? document.title })) };
  };
  const localizeSource = (source: Source): Source => {
    if (language !== 'de') return source;
    const copy = (contentDe.sources as Record<string, { title: string; text: string }>)[source.id];
    return { ...source, ...copy, locator: t(source.locator).replace(/^Section\s+/, '§ '), ...(typeof source.version_note === 'string' ? { version_note: t(source.version_note) } : {}) };
  };
  const localizeConfiguration = (configuration: Configuration): Configuration => language === 'de' ? { ...configuration, ...(configurationCopy[configuration.id] ?? { name: t(configuration.name), description: t(configuration.description) }) } : configuration;
  const localizeHarness = (harness: Harness): Harness => ({ ...harness, name: harnessName(harness.id), description: t(harness.description) });
  const referenceReasoning = (caseId: string, original: string) => language === 'de' ? (contentDe.cases as Record<string, { reference_reasoning: string }>)[caseId]?.reference_reasoning ?? original : original;
  const errorText = (message: string): string => {
    if (language === 'en' || !message) return message;
    if (german[message]) return german[message];
    for (const prefix of ['The workspace could not load.', 'Could not refresh this run.']) if (message.startsWith(`${prefix} `)) return `${t(prefix)} ${errorText(message.slice(prefix.length + 1))}`;
    if (message.startsWith('Experiment budget stopped this run: ')) return `Das Versuchsbudget hat diesen Lauf gestoppt: ${errorText(message.slice('Experiment budget stopped this run: '.length))}`;
    const stepLimit = message.match(/^No valid final answer within the (\d+)-turn budget$/);
    if (stepLimit) return `Keine gültige abschließende Antwort innerhalb von ${stepLimit[1]} Modellschritten.`;
    const toolLimit = message.match(/^The (\d+)-call tool budget was exhausted$/);
    if (toolLimit) return `Die Grenze von ${toolLimit[1]} Werkzeugaufrufen wurde erreicht.`;
    const failure = message.match(/^Request failed \((\d+)\)\. Please retry\.$/);
    if (failure) return t('Request failed ({status}). Please retry.', { status: failure[1] });
    return german[message] ?? `${t('Original message')}: ${message}`;
  };
  return { language, setLanguage, t, human, valueLabel, money, count, duration, date, euro, harnessName, number, percent, usd, localizeCase, localizeSource, localizeConfiguration, localizeHarness, referenceReasoning, errorText };
}

const LanguageContext = createContext<ReturnType<typeof useLanguageValue> | null>(null);
export function LanguageProvider({ children }: { children: ReactNode }) {
  return <LanguageContext.Provider value={useLanguageValue()}>{children}</LanguageContext.Provider>;
}
export function useLanguage() {
  const context = useContext(LanguageContext);
  if (!context) throw new Error('LanguageProvider is required');
  return context;
}
