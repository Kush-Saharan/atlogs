# atlogs — Design System & UI/UX Specification

> Design language: **ATLOGS // TACTICAL TELEMETRY** (approved design; tokens
> unchanged).
>
> **Code status:** the tokens below are the approved target. `frontend/src/index.css`
> still carries the earlier shadcn theme (e.g. `--radius: 0.875rem`) and
> `AppShell.tsx` still renders `ShaderBackground`. Applying the re-skin is a
> not-started task (see [`tasks.md`](tasks.md)).

---

## 1. Design Philosophy

atlogs is a **maintenance decision workspace**: an industrial, command-center
look that communicates precision and trust. Dark substrates, monospaced
typography, zero-radius geometry and data-dense layouts where every element
communicates the state of a log, record or recommendation.

### Core Principles

1. **Data density over decoration** — every visual element communicates
   operational state; no ornamental chrome.
2. **Evidence beside every claim** — source spans, similar cases, risk factors
   and the *uncalibrated* label are first-class UI elements. A human decision
   is always one explicit action, never implied.
3. **Industrial legibility** — monospaced type, high-contrast status ramps, and
   structured grid layouts ensure scannability at a glance.
4. **Motion with purpose** — animations serve orientation (reveal-on-scroll,
   count-up stats) or feedback (loading, streaming), never spectacle.

---

## 2. Design Tokens

### 2.1 Color Palette

| Token | Value | Usage |
|-------|-------|-------|
| `--bg` | `#0A0A0A` | Page background |
| `--bg-2` | `#0F0F0F` | Card surfaces |
| `--bg-3` | `#141414` | Raised surfaces, modals |
| `--fg` | `#EAEAEA` | Primary text |
| `--dim` | 58% of `--fg` | Secondary / descriptive text |
| `--faint` | 34% of `--fg` | Tertiary / label text |
| `--line` | `#242424` | Hairline borders |
| `--line-strong` | `#3D3D3D` | Structural borders |
| `--accent` | `#FF2A2A` | **One accent** — primary actions, selection, focus, hazard |
| `--green` | `#4AF626` | "Online" / verified status only |

### 2.2 Semantic Status Ramp

| Status | Color | Usage |
|--------|-------|-------|
| Verified / Approved | `--green` (`#4AF626`) | Confirmed identity, reviewed record, approved decision |
| Review / Warning | Amber | `needs_review` fields, pending review, schedule conflict |
| Linked / Related | Violet | Similar cases, cross-references |
| Minor / Notice | Gold | Informational, low priority, insufficient evidence |
| Critical / High risk | `--accent` (`#FF2A2A`) | Failures, high-priority recommendations |

### 2.3 Typography

| Token | Font | Usage |
|-------|------|-------|
| `--macro` | **Archivo Black** | Display headings, stat numerals, hero text |
| `--mono` | **JetBrains Mono** | Body text, labels, data values, code — *everything else* |
| `--serif` | **Playfair Display** (italic) | Manifesto / quote voice (landing page only) |

**Micro-typography rules:**
- Labels: 9–11px, `letter-spacing: 0.14–0.22em`, `text-transform: uppercase`
- Stat numerals: tabular figures, Archivo Black
- Body text: JetBrains Mono, 14px base, 1.6 line-height

### 2.4 Geometry

| Property | Value | Rationale |
|----------|-------|-----------|
| Border radius | **0 everywhere** | Square geometry — industrial, no softness |
| Shadows | **None** | Borders carry structure, not depth illusion |
| Grid gap | 1px (hairline) | The "gridlines" pattern — 1px-gap cells |
| Card borders | 1px `--line` | Minimal containment |

### 2.5 Texture & Atmosphere

- **CRT scanlines**: `body::after` pseudo-element, horizontal lines at ~2px
  pitch, low opacity (~5%)
- **Fractal noise overlay**: 5.5% opacity noise texture for analog feel
- **No WebGPU shaders**: `ShaderBackground` (Swirl/ChromaFlow/FlutedGlass/
  FilmGrain) is to be retired by the re-skin — the CRT substrate replaces it at
  a fraction of the GPU cost (still rendered in code today)

---

## 3. Motion & Animation

### 3.1 Easing

```css
--ease: cubic-bezier(.16, 1, .3, 1);
```

### 3.2 Animation Vocabulary

| Pattern | Implementation | Usage |
|---------|---------------|-------|
| Reveal-on-scroll | `IntersectionObserver` | Section entries on landing |
| Count-up stats | `requestAnimationFrame` counter | Dashboard metrics, hero stats |
| Marquee | CSS infinite scroll | Capability strip |
| JIT telemetry jitter | Random interval text swaps | Live status indicators |
| Typing terminal | Character-by-character append | Document log, status feeds |
| Streaming tokens | SSE append | Chat answers, thinking traces |

**All animations respect `prefers-reduced-motion`** — reduced motion disables
spin, jitter, and marquee; streaming text remains (it's functional, not
decorative).

---

## 4. Component Vocabulary

### 4.1 Console Tags

Eyebrow labels on every page header, card, and panel:

```
[ ATLOGS-CORE ]    [ SEC.02 ]    [ LOG / LG-0142 ]
```

- Uppercase, `--mono`, `--faint` color
- 9px, `letter-spacing: 0.18em`
- Brackets are literal characters, not decorative borders

### 4.2 Section Header Pattern

```
[ SEC.NN ] TAG
═══════════════════════════════
HEADLINE (Archivo Black, display size)
One-line uppercase kicker (JetBrains Mono, --dim)
```

Replaces the previous `PageHeader` component across all pages.

### 4.3 Spec Rows

Key/value fact grids with hairline dividers:

```
┌─────────────────┬─────────────────┐
│ SERIAL          │ SN-4471         │
├─────────────────┼─────────────────┤
│ LOCATION        │ Unit-3, Bay 7   │
├─────────────────┼─────────────────┤
│ STATUS          │ ● ACTIVE        │
└─────────────────┴─────────────────┘
```

Used in asset inspectors, extracted-field review, risk factors, connector details.

### 4.4 Hover-Invert Cards

Cards that flood `--fg` (white) on hover with a red corner square reveal:

```css
.card:hover {
  background: var(--fg);
  color: var(--bg);
}
.card:hover::after {
  /* red corner square */
  content: '';
  width: 8px; height: 8px;
  background: var(--accent);
}
```

Used for workflow cards, log and recommendation rows, connector entries.

### 4.5 Row-Arrow Lists

On hover: row slides right, `>>` arrow appears.

```
  Connector A                         →
  ▸ Connector B                     >>
  Connector C                         →
```

Used in logs, connectors, review queues, similar cases, audit history.

### 4.6 Hazard Stripe Divider

```css
background: repeating-linear-gradient(
  -45deg,
  var(--accent),
  var(--accent) 10px,
  var(--bg) 10px,
  var(--bg) 20px
);
```

Used sparingly — page-level section separators only.

---

## 5. Page-Level Design Map

Routes come from `frontend/src/App.tsx`. Planned paths are proposals; the
owning M task fixes them.

### Existing pages

| Page | Key Design Elements |
|------|-------------------|
| **Home** (`/`) | Metrics grid (count-up), workflow links, recent evidence; becomes the atlogs dashboard in M.13 |
| **Knowledge Graph** (`/graph`) | `GraphSphere` (d3-force-3d on canvas), sticky `NodeInspector`, type filters, hub-clustering `+N` chips; square chips, red selection state |
| **Workflows** (`/workflows`) | Workflow cards (hover-invert) |
| **Connectors** (`/connectors`) | Add modal (manual/API), streamed sync log per connector, row-arrow list |
| **Assets** (`/assets`) | Searchable list, identifier badges (spec-row style); serves as the equipment list |
| **Review queue** (`/review`) | Entity-merge candidates side-by-side (spec-row compare), merge/separate/dismiss |
| **Documents** (`/workflows/documents`) | Upload/folder, live job log (terminal styling), custodial document list |

### Planned pages

| Page | Task | Key Design Elements |
|------|------|-------------------|
| **Login** | M.1 | Single form, mono labels, error text (not colour-only) |
| **Logs** | M.2 | Paste/upload panel, type/size errors inline, duplicate warning with "submit anyway", row-arrow list with status dots |
| **Log review** | M.5 | Source text with highlighted spans beside spec-row fields; amber `needs_review` markers; confirm / correct; extracted value shown next to reviewed value |
| **Record detail** | M.7, M.9 | Reviewed fields, linked equipment, similar-cases panel (violet links to source logs, clear "no relevant match"), risk factors with *uncalibrated* tag |
| **Recommendations & schedule** | M.10–M.12 | Priority + explanation, proposed assignments, conflict rows (amber) without lowered priority; approve / modify / reject (manager only) with comment |
| **Resources** | M.8 | Technicians (skills, availability), parts (stock), equipment criticality; admin only |
| **Audit history** | M.12 | Append-only timeline: original vs final, user, timestamp, comment |
| **Dashboard notifications** | M.13 | On Home: pending review, high priority, unschedulable, recent decisions; filtered by role |

### Hidden pages (M-D1: retained, off the nav, reachable by URL)

| Page | Key Design Elements |
|------|-------------------|
| **Ask Copilot** (`/ask`) | Threaded chat, thinking trace, streaming answer with citation chips |
| **RCA** (`/workflows/rca`) | Composer, 4-stage rail, hypotheses + synthesis, confidence badges |
| **Compliance** (`/workflows/compliance`) | Rule/asset scope, posture card, at-risk table |

---

## 6. GraphSphere Visualization

The signature visualization renders a 3D force-directed graph on a 2D canvas:

- **Engine:** d3-force-3d layout (no WebGL dependency)
- **Geometry:** ball radius ~ `30 · ∛n`; charge/link/radial/collide forces
- **Depth cues:** opacity + size scale with Z-depth
- **Interaction:** auto-revolve at rest, drag-to-spin, wheel zoom, click hit-testing
- **Level-of-detail:** zoomed out → dots + halos; zoomed in / hover / selected → labelled chips
- **Colors:** asset dots use `--accent` (hazard red); node types follow the semantic status ramp via CSS variables
- **Accessibility:** `prefers-reduced-motion` pauses auto-spin

---

## 7. Responsive Design

| Breakpoint | Behavior |
|-----------|----------|
| Desktop (≥1024px) | Full sidebar navigation, multi-column layouts, full GraphSphere |
| Tablet (768–1023px) | Collapsed sidebar, stacked layouts |
| Mobile (≤767px) | Top bar + bottom tab navigation, single-column; engineer flows prioritised (log upload, log review, equipment lookup) |

Target: all pages audited at **360px** minimum width (engineer's phone).

---

## 8. Accessibility

- **Color contrast:** `--fg` on `--bg` exceeds WCAG AA (ratio > 14:1)
- **Reduced motion:** all decorative animations gated on `prefers-reduced-motion`
- **Semantic HTML:** proper heading hierarchy, ARIA labels on interactive elements
- **Keyboard navigation:** all interactive elements focusable, escape closes modals
- **Status indicators:** never color-only — always paired with icons or text labels

---

## 9. Design System Files

| File | Purpose |
|------|---------|
| `frontend/src/index.css` | All design tokens, base styles, texture overlays |
| `frontend/src/components/ui/` | shadcn-style primitives restyled to workspace theme |
| `frontend/src/components/AppShell.tsx` | App chrome, navigation, brand |
| `frontend/src/components/GraphSphere.tsx` | 3D knowledge graph visualization |
| `frontend/src/components/PageHeader.tsx` | Section header pattern |
| `frontend/src/components/NodeInspector.tsx` | OKF document renderer for graph nodes |
| `frontend/src/lib/graphColors.ts` | Shared node-type color mapping |
