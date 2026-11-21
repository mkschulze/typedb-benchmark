---
name: "Tax Context Benchmark"
description: "Provisional Deloitte-style visual system extracted from the shipped React interface."
colors:
  green: "#86bc25"
  green-dark: "#426714"
  ink: "#151713"
  body-ink: "#1b1d1a"
  muted: "#62665e"
  line: "#dce0d7"
  surface: "#f5f6f3"
  focus: "#537e14"
  canvas: "#fff"
  header: "#111"
  button-ink: "#182108"
  green-hover: "#9bce3d"
  green-active: "#76a51f"
  disabled-bg: "#e5e8df"
  disabled-ink: "#72776c"
  badge-neutral-bg: "#eaede5"
  badge-neutral-ink: "#5d6553"
  badge-green-bg: "#eaf3dd"
  badge-green-ink: "#426218"
  badge-amber-bg: "#f6edd7"
  badge-amber-ink: "#7b5b16"
  badge-red-bg: "#f9e5e0"
  badge-red-ink: "#9e3928"
typography:
  headline:
    fontFamily: "'Open Sans', sans-serif"
    fontSize: "2.15rem"
    fontWeight: 700
    lineHeight: 1.3
    letterSpacing: "-.035em"
  title:
    fontFamily: "'Open Sans', sans-serif"
    fontSize: "1.3rem"
    fontWeight: 700
    lineHeight: 1.4
    letterSpacing: "-.025em"
  subheading:
    fontFamily: "'Open Sans', sans-serif"
    fontSize: "1.06rem"
    fontWeight: 700
    lineHeight: 1.5
  body:
    fontFamily: "'Open Sans', sans-serif"
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: 1.7
  button:
    fontFamily: "'Open Sans', sans-serif"
    fontSize: ".9rem"
    fontWeight: 700
    lineHeight: 1.5
  badge:
    fontFamily: "'Open Sans', sans-serif"
    fontSize: ".69rem"
    fontWeight: 700
    lineHeight: 1.3
  code:
    fontFamily: "'SFMono-Regular', Consolas, monospace"
    fontSize: ".77rem"
    lineHeight: 1.7
rounded:
  control: "2px"
spacing:
  "8": "8px"
  "12": "12px"
  "16": "16px"
  "20": "20px"
  "22": "22px"
  "24": "24px"
  "28": "28px"
  "30": "30px"
  "32": "32px"
  "48": "48px"
components:
  button-primary:
    backgroundColor: "{colors.green}"
    textColor: "{colors.button-ink}"
    typography: "{typography.button}"
    rounded: "{rounded.control}"
    padding: "11px 20px"
  button-primary-hover:
    backgroundColor: "{colors.green-hover}"
    textColor: "#101906"
  button-primary-active:
    backgroundColor: "{colors.green-active}"
  button-primary-disabled:
    backgroundColor: "{colors.disabled-bg}"
    textColor: "{colors.disabled-ink}"
  button-secondary:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.ink}"
    typography: "{typography.button}"
    rounded: "{rounded.control}"
    padding: "11px 20px"
  button-text:
    textColor: "{colors.green-dark}"
    padding: "0"
  button-icon:
    rounded: "{rounded.control}"
    width: "36px"
    height: "36px"
  input-search:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    padding: "10px 32px 10px 12px"
  navigation:
    backgroundColor: "{colors.header}"
    textColor: "{colors.canvas}"
  badge-neutral:
    backgroundColor: "{colors.badge-neutral-bg}"
    textColor: "{colors.badge-neutral-ink}"
    typography: "{typography.badge}"
    rounded: "{rounded.control}"
    padding: "3px 8px"
  badge-green:
    backgroundColor: "{colors.badge-green-bg}"
    textColor: "{colors.badge-green-ink}"
  badge-amber:
    backgroundColor: "{colors.badge-amber-bg}"
    textColor: "{colors.badge-amber-ink}"
  badge-red:
    backgroundColor: "{colors.badge-red-bg}"
    textColor: "{colors.badge-red-ink}"
  case-region:
    backgroundColor: "{colors.surface}"
    padding: "28px 30px 20px"
  evidence-region:
    padding: "28px 32px 30px"
  run-checkpoint:
    padding: "18px 0 0"
  budget-strip:
    backgroundColor: "{colors.surface}"
    padding: "14px 18px"
---

# Design System: Tax Context Benchmark

## Overview

**Creative North Star: "The Evidence Workspace"**

The Evidence Workspace is a restrained, dense working interface: a black navigation band, a white canvas, muted fact regions, and green actions. Typography and fine dividers carry the hierarchy without decorative imagery or elevation.

The user requested Deloitte design. This record describes the provisional implementation evidenced by frontend/src/styles.css and frontend/src/App.tsx; exact conformance to design.deloitte.com remains unverified because that authority was inaccessible. Open Sans is intentionally retained for the requested brand direction.

**Key Characteristics:**

- Flat surfaces and fine structural dividers.
- Compact Open Sans hierarchy with prominent monetary figures.
- Green actions and explicitly labeled status tones.
- Inline evidence regions and responsive stacked workspaces.

## Colors

One green accent family sits against black, white, and slightly green neutral surfaces. Frontmatter values are normative; descriptive roles below explain their use.

### Primary

- **Action Green** (`green`): primary action fills, brand dot, and selected header underline.
- **Readable Green** (`green-dark`): links and text actions on light surfaces.
- **Focus Green** (`focus`): keyboard outlines. Hover and active action shades are separate state tokens.

### Neutral

- **Header Black / Canvas White** (`header`, `canvas`): the navigation band and working canvas.
- **Ink / Body Ink** (`ink`, `body-ink`): control text and default reading text.
- **Muted Text / Divider / Fact Surface** (`muted`, `line`, `surface`): secondary text, structural rules, and quiet fact/history regions.
- **Disabled Surface / Disabled Ink**: unavailable primary actions remain visible with subdued fill and labels.

The sidecar’s eight-step tonal ramps are synthesized in OKLCH for palette visualization; they are not additional implemented shades or verified Deloitte tokens.

Status badges use paired neutral, green, amber, and red background/text tokens. Amber marks provisional or incomplete states; red marks failures. These semantic colors supplement the single brand accent.

### Named Rules

**The Action Green Rule.** Use bright green for primary actions and selected navigation; use dark green for readable links on light surfaces.

## Typography

**Display Font / Body Font:** self-hosted Open Sans, with sans-serif fallback. The root is (14px), regular weight (400); headings and emphasized controls use (700). The supplied bold font face covers the declared (600–800) range. There is no separate ornamental display face.

**Label/Mono Font:** SFMono-Regular, Consolas, monospace for JSON and trace content only.

### Hierarchy

- **Headline:** page heading uses the frontmatter headline role; below (900px) it becomes (1.8rem), with phone line-height (1.35).
- **Title:** section heading uses the title role; at phone widths it becomes (1.18rem).
- **Subheading:** the standard third-level heading uses the subheading role, with smaller local variants for dense sections.
- **Body:** default paragraphs use the body role. Dense working text is typically (.82–.89rem), with line-height (1.7); answer justification uses (1.8). Intros and summaries are constrained to roughly (65–68ch).
- **Label:** control labels are bold (.83rem); captions are regular (.77rem). Small status badges use the badge role; their compact sizes are for short status labels, not body copy.
- **Monetary emphasis:** gross amount uses (2rem); answer outcome uses (2.4rem), bold, with tight tracking. Phone amounts use (1.9rem) and (2.1rem), respectively.

### Named Rules

**The Numeric Clarity Rule.** Use tabular numerals for money, result columns, and recorded usage.

## Layout

The header and main content share a centered maximum width (1440px) and desktop gutters (48px). The header minimum height is (80px). Spacing repeatedly uses (8–32px) internal intervals, with larger gutters rather than a rigid modular grid.

The case/answer region is a bordered split grid (.88fr / 1.12fr). Its fact side has a muted fill and a dividing rule; the answer side stays white. Comparison controls use (1.5fr / .95fr / .7fr / auto) columns for case, model, harness, and action, with (22px) gaps; at (1180px) these become (1.3fr / .9fr / .7fr / auto) with (16px) gaps. Benchmark settings/history use (1.1fr / .9fr); source entries use (.75fr / 1.25fr). Approach explanations use four columns; inline evidence uses two equal columns with a (60px) gap.

At (1180px), gutters reduce to (32px), the header status disappears, and panel padding tightens. At (900px), comparison controls form two columns (1.3fr / 1fr), approach explanations become two columns, and evidence gaps reduce. At (680px), gutters become (22px), the header becomes a two-column grid with minimum height (110px), wordmark left and language switch right, with navigation across the next row, controls and working regions stack, and the compare action spans the available width. Evidence, benchmark, and source regions also stack. Result tables preserve a (490px) minimum width inside a horizontally scrollable, keyboard-focusable container. The page supports a minimum viewport width (320px).

## Elevation & Depth

The shipped interface has no box shadows. Depth comes from white versus pale neutral regions, one-pixel dividers, and state fills. Evidence remains in document flow with a slightly stronger boundary; it does not use a backdrop or floating modal.

### Named Rules

**The Flat Workspace Rule.** Separate regions with tone, spacing, and fine borders rather than shadows.

## Shapes

Buttons, icon actions, fields, and status badges have barely softened corners using the control radius. Major panels and fact blocks remain rectangular. Borders are generally (1px); selected navigation uses a (3px) underline and evidence detail selection a (2px) underline. Tiny circular dots identify brand/connectivity. They do not imply a pill-shaped component system.

## Components

### Buttons

Compact, bold, and direct. Primary actions use green fill and dark text with (11px 20px) padding, (45px) minimum height, and (18px) icon gap. Hover lightens the fill; press darkens it; disabled actions use the disabled token pair. Secondary actions use white fill and a muted green-gray border. Text actions use readable green and gain an underline on hover. Icon actions occupy (36px) square controls and gain a pale green hover fill.

All buttons transition color, background, and border color over (160ms ease-out). Keyboard focus uses a (2px) focus outline offset by (4px). Reduced motion removes transitions and animations. Do not infer an extra transform or active animation.

### Chips

Status badges are compact rectangular labels with the control radius, (3px 8px) padding, and (23px) minimum height. Neutral, green, amber, and red variants identify states with explicit text. They are descriptive labels, not interactive filters.

### Cards / Containers

Fact and history containers use the muted surface; answers and evidence use white. The main fact region uses (28px 30px 20px) padding; answer regions use (28px 32px 26px); evidence uses (28px 32px 30px). At phone widths internal horizontal padding becomes (20px). Boundaries and tone supply separation without shadows.

### Inputs / Fields

Native selects and search fields use white fill, dark text, a muted green-gray (1px) border, the control radius, and (45px) minimum height. Padding is (10px 32px 10px 12px); search overrides its right padding to (14px). Hover darkens the border. Focus uses the global outline with a closer (1px) offset. Disabled selects use a paler fill and subdued border/text. Phone comparison selects have (46px) minimum height. Checkboxes remain native, (16px) square, with green accent color.

### Navigation

Header navigation uses subdued light labels on black; hover and selected labels become white. Selection adds the green bottom rule. Phone navigation remains visible beneath the wordmark. Inline evidence navigation uses understated buttons and a darker selected label with a green underline.

### Language Switch and Localized Content

The black header carries a compact DE/EN button group with an accessible language label. The barely rounded outer border and internal divider use the same muted gray-green stroke; each button has a (40px) minimum width and height, bold (.76rem) text, and an explicit `aria-pressed` state. Selected language uses the primary green/dark-text pair; hover uses a dark neutral fill and white text. Keyboard focus retains the global outline with a (3px) offset. At phone widths the switch stays beside the wordmark while navigation spans the next row.

German is the default; DE/EN persists through `tax-benchmark-language` when storage is available and updates `html.lang`. Dates, money, percentages, durations, and counts follow `de-DE` or `en-GB`. Visible controls, case titles/questions/summaries, fact labels and values, document titles, source titles/summaries, and curated reference reasoning change language without altering identifiers or stored evidence. Current German copy includes “Budgetlimit”, “Angerechnet”, and “Beispielauswertung”.

Model answer reasoning, original document bodies, raw JSON, traces, and manifests retain their recorded content, with visible original-answer/document/record labels; IDs and hashes remain intact. Original-content captions use muted bold (.72rem) text with (10px) top and (5px) bottom margins. Reference reasoning is translated separately from measured model answers. Unknown errors retain their message behind a localized original-message label. These boundaries preserve provenance while allowing the working interface to read naturally in either language.

### Agent Harness Selector

A native labeled select chooses the run-level harness independently of the five context approaches. “Direkter Agent” / “Direct agent” and “CrewAI” use the existing field shape, typography, hover, focus, and disabled treatments. Capability data controls availability; an unavailable option stays visible with a translated suffix and is disabled. A missing capability endpoint falls back to the direct harness, with CrewAI unavailable. The selected description is linked through `aria-describedby` and uses muted (.76rem) text with (9px) top margin. Benchmark settings place this field above the selection groups with (26px) bottom margin.

The selector is disabled while a run is being submitted or remains active; launch actions also require an available harness. Both demonstration and benchmark requests carry the selected stable harness ID, independently of locale. Run history and results identify the recorded harness; legacy records without a harness display Direct agent. The five approach checkboxes remain a separate comparison axis: Quellenrecherche / RAG, TypeDB context, TypeDB + schema, TypeDB + functions, and SQL control. This is an execution control, not another approach or navigation tab.

### Inline Evidence

Evidence opens next to the answer in document order, before the approach explainer in the demonstration. The non-modal labeled region receives programmatic focus and scrolls into view; its close action is an icon button. Sources and case evidence use divided article lists, readable green links with inline SVG external-link indicators, muted locators, and retrieval dates. Structured answer and tool trace views use wrapped monospace blocks. Empty citations and missing sources receive explicit text states.

### Shared Budget Strip

A quiet, flat surface region displays the shared experiment limit with Remaining, Allocated, and Reserved values. The current €30 limit is runtime data, not a visual token. The strip uses the existing fact-surface color, (14px 18px) padding, (28px) bottom margin, and wrapping flex rows with (8px 28px) gaps. Its compact heading is (.88rem), bold, without tracking; values use (.8rem) text with bold tabular numerals. A full-width muted note (.74rem) explains the shared provider budget, USD→EUR estimate safety buffer, and continued reservation of unknown charges.

Blocked budgets add the existing amber badge labeled “New calls paused”. Loading uses “Loading experiment budget…” and marks the labeled region busy. An unavailable budget replaces values with explicit status text explaining that the server still checks the limit before model calls. These states use existing typography and semantic treatments rather than new colors or decorative indicators.

At the existing phone breakpoint (680px), padding becomes (14px 16px), bottom margin (24px), and strip gap (12px). The values row occupies full width with no automatic left margin, (8px 18px) gaps, and (.75rem) text; the note becomes (.71rem). Values and heading content wrap naturally.

### Feedback and Data

Run feedback is shared between demonstration and benchmark views. Progress labels and controls wrap at all widths, with (11px) gaps and (.8rem) text; phones use (7px) gaps and (.73rem) text. Cancellation switches the action to “Requesting cancellation…” and then “Cancelling after current call”, with the action disabled while pending. Failed runs use red badges; interrupted and cancelled runs retain explicit neutral status labels. Run errors appear in an alert, and empty terminal runs state that no trials were recorded.

Interrupted runs can show a flat checkpoint section with a top divider, (20px) vertical margin, and (18px) top padding. Its heading uses (.95rem); metadata and the partial-record warning use (.8rem), with long identifiers wrapping. Trace and usage disclosures use the existing summary and wrapped monospace patterns. Missing checkpoints receive an explicit text explanation. Partial usage is presented as incomplete, not as a completed answer. Aggregate tables keep incorrect answers, execution errors, and cancelled trials in separate labeled numeric columns.

Loading uses static pale skeleton regions. Errors use a warm light fill, border, and readable red-brown text; incomplete information uses amber notices. Run progress is a thin (3px) green bar with (200ms ease-out) width feedback. Empty states use quiet surface regions and text. Tables use thin row rules, a pale hover background, and tabular numerals; unavailable measurements remain textual placeholders rather than invented values.

## Do's and Don'ts

### Do:

- **Do** retain the black header, white canvas, and muted fact-region hierarchy.
- **Do** pair status colors with readable labels.
- **Do** retain visible keyboard focus and reduced-motion behavior.
- **Do** stack regions at phone widths and let wide result tables scroll within their container.

### Don't:

- **Don't** claim exact Deloitte design-system compliance from these provisional tokens.
- **Don't** use green status alone to communicate an outcome.
- **Don't** introduce decorative shadows into the flat workspace.
