# CONTEXT.md — Eudoxa Project

## Purpose

Eudoxa is a decision-support web application implementing a formal framework for multi-aspect value comparison. It allows users to define **aspects** (evaluation dimensions), **aspect levels** (the possible values of an aspect), **aspect level relations** (ordering between levels), **value differences** (VDiffs, e.g. Δ(VG,G)), **value difference comparisons** (a partial order on VDiffs), **consequences** (tuples assigning a level to each aspect), and a **dominance relation** on consequences.

The project is a Flask web application intended to run on PythonAnywhere as well as locally in Eclipse.

---

## Repository layout

```
flask-pythonanywhere-test/
├── app.py                  Flask application — routes and session helpers
├── eudoxa.py               Core data model — all domain logic
├── requirements.txt
├── tests/
│   └── test_closure.py     Unit tests for EudoxaManager.closure()
├── static/
│   ├── common.js           Shared JS utilities
│   ├── nav.js              Navbar injection (fetches project name + aspects)
│   └── styles/
│       ├── common.css
│       ├── aspect_detail.css
│       ├── aspects.css
│       ├── consequences.css
│       ├── index.css
│       ├── levels.css
│       └── vdiff_matrix.css
└── templates/
    ├── index.html          "/" — project home, aspects summary, consequences
    ├── aspects.html        "/aspects" — aspect table
    ├── aspect_detail.html  "/aspects/<name>" — levels, relations matrix, graph
    ├── consequences.html   "/consequences" — named consequences + comparison
    ├── vdiff_matrix.html   "/vdiff-matrix" — VDiff comparison matrix
    ├── dominance_graph.html"/dominance-graph"
    └── levels.html         "/aspects/<name>/levels"
```

---

## Core model (`eudoxa.py`)

### Key constants

| Name | Value | Meaning |
|---|---|---|
| `PROJ` | `"\|PROJ\|"` | Excel tab: project metadata |
| `ASP` | `"\|ASP\| "` | Excel tab prefix: one per aspect |
| `CONS` | `"\|CONS\|"` | Excel tab: consequences |
| `VDCM` | `"\|VDCM\|"` | Excel tab: VDiff comparison matrix |
| `DELTA` | `"Δ"` | VDiff display prefix |
| `ZDIFF_TUPLE` | `(None, None)` | Legacy tuple key (still used in Excel import label parsing) |
| `ZDIFF_DISPLAY` | `"◬"` (U+25EC) | Display/persistence symbol for natural zero-diffs |
| `NATURAL_ZERO` | `VDiff(None, None, None)` | Single canonical vdcm dict key for all natural zero-diffs |
| `TRUE` | `"⊒"` | VDCM: vd1 ⊒ vd2 (vd1 ≥ vd2 in the VDiff order) |
| `FALSE` | `"⋣"` | VDCM: vd1 ⋣ vd2 (vd1 < vd2) |
| `UNDEFINED` | `""` | VDCM: relation not yet set |
| `BT` / `BTE` / `EQ` / `WTE` / `WT` | `≻ ⪰ ∼ ⪯ ≺` | Aspect level relations |
| `GT` / `GTE` / `DEQ` / `LTE` / `LT` | `⊐ ⊒ ≜ ⊑ ⊏` | VDiff order relations (derived) |

### Natural zero-diffs

A natural zero-diff `◬` represents the difference Δ(X,X) — any level compared to itself. Conceptually there is only one natural zero-diff regardless of which aspect it comes from.

Internally the vdcm uses the single sentinel `NATURAL_ZERO = VDiff(None, None, None)` as the dict key for all natural-zero entries. The module-level helper `_vdiff_key(vd)` normalises any VDiff with `from_level == to_level` to `NATURAL_ZERO`; it is called by both `get_vdiff_relation` and `set_vdiff_relation`. Aspect-specific natural-zero VDiff objects (e.g. `VDiff("Betyg", None, None)`) still appear in `Aspect.vdiffs` for iteration purposes, but are never used directly as dict keys.

Aspect level `*` is **not** reserved (unlike in earlier versions).

### VDiff ordering: TRUE/FALSE vs GT/GTE/DEQ/LTE/LT

The VDCM stores raw `TRUE`/`FALSE`/`UNDEFINED` entries for ordered pairs.
The derived order relation shown in the UI is computed from the raw forward and backward entries:

- `TRUE` fwd + `FALSE` bwd → `⊐` (GT, strictly greater)
- `TRUE` fwd + `TRUE` bwd → `≜` (DEQ, equal in VDiff order)
- `TRUE` fwd + `UNDEFINED` bwd → `⊒` (GTE)
- `FALSE` fwd + `TRUE` bwd → `⊏` (LT)
- etc.

### VDiff comparison matrix (vdcm) structure

The vdcm is a two-level adjacency dict:

```python
vdcm: Dict[VDiff, Dict[VDiff, str]]
# vdcm[vd1][vd2] == relation between vd1 and vd2
```

`VDiff` is hashable (`__hash__` based on `(aspect_name, from_level, to_level)`).
All natural-zero vdiffs are stored under the single `NATURAL_ZERO` key — there is no separate per-aspect entry for `◬`.

Access is always via `get_vdiff_relation(vdcm, vd1, vd2)` and `set_vdiff_relation(vdcm, vd1, vd2, rel)`, which call `_vdiff_key` to normalise before touching the dict.

`expand_vdiff_comparison_matrix(an2)` is called after each `add_level` call. It cross-products all vdiffs of every existing aspect with the vdiffs of `an2`, initialising missing entries to `UNDEFINED` (or `TRUE` for `k1 == k2`). It never overwrites existing entries.

### VDiff ordering in export and UI

VDiffs are exported and displayed sorted by `_sorted_vdiffs(asp)`: zero-diff first, then `(from, to)` pairs sorted by `(level_index[from], level_index[to])` where `level_index` follows the insertion order of levels in the aspect.

### Excel format

Tabs in order: `|PROJ|`, `|ASP| <name>` (one per aspect), `|CONS|`, `|VDCM|`.

**`|PROJ|` tab:**
```
EUDOXA    0.1
Project name:  <name>
Author:        <author>
Aspects:
-              <aspect1>
-              <aspect2>
...
```
Aspect order in `|PROJ|` controls import order, which becomes `mgr.aspects` dict insertion order, which drives all views and exports.

**`|VDCM|` tab layout:**
- Row 2: aspect name column headers (written only on first column of each aspect block)
- Row 3: VDiff labels (`◬`, `(VG,G)`, …); col C is the corner cell `Δ\Δ`
- Row 4+: col B = aspect name (only on first row of each aspect block), col C = VDiff label, cols D+ = relation values

Import tracks `current_row_asp` to handle blank col B cells (continuation rows). Import accepts `◬` as the natural zero-diff label.

### Aspect name restrictions

- Aspect names may **not** contain `|` (enforced in `add_aspect`), because `|` is used as separator in the `selPair` dropdown value encoding in `/vdiff-matrix`.
- Aspect names may not be duplicates.

### Session storage

The `EudoxaManager` is serialised via `to_dict()` / `from_dict()` and persisted to a server-side file store at `.manager_store/<sid>.json`, keyed by a session ID (`session["sid"]`). The Flask cookie holds only `sid`, `project_name`, and `author` — it does **not** hold the serialised manager. This avoids Flask's ~4 KB signed cookie limit.

The store directory is configurable via the `MANAGER_STORE_DIR` environment variable, defaulting to `.manager_store/` adjacent to `app.py`.

#### Session helpers

```python
_store_path(sid)        # returns file path for a given session ID
_get_sid()              # returns session["sid"], creating one (uuid4.hex) if absent
load_manager_or_400()   # reads and deserialises from file store; aborts 400 if missing
save_manager(mgr)       # serialises and writes to file store
```

### `to_dict` / `from_dict` serialisation

The file format is versioned via `"__schema__"` in the top-level dict.

**Schema 2 (current):** Each VDiff is serialised as a single string key:
- `NATURAL_ZERO` → `"◬"`
- Other vdiffs → `"aspect_name|||from_level|||to_level"`

The vdcm is stored as a two-level JSON object mirroring the adjacency dict:
```json
{ "◬": { "◬": "⊒", "Betyg|||G|||IG": "" },
  "Betyg|||G|||IG": { "◬": "", "Betyg|||VG|||G": "⊒" } }
```

**Schema 1 (legacy):** Outer key `"A1|||A2"` (aspect pair), inner key `"f1::t1>>f2::t2"` (two vdiff tuples, `None` as `""`). `from_dict` detects schema 1 and migrates automatically by normalising natural zeros to `NATURAL_ZERO`. Files produced on the `main` branch before this refactor are schema 1.

---

## Flask app (`app.py`)

### Routes

#### HTML pages

| Route | Template | Description |
|---|---|---|
| `GET /` | `index.html` | Project home |
| `GET /aspects` | `aspects.html` | Aspect table |
| `GET /aspects/<name>` | `aspect_detail.html` | Levels, relations, graph |
| `GET /aspects/<name>/levels` | `levels.html` | Level list |
| `GET /consequences` | `consequences.html` | Named consequences |
| `GET /vdiff-matrix` | `vdiff_matrix.html` | VDiff comparison matrix |
| `GET /dominance-graph` | `dominance_graph.html` | Dominance graph |
| `GET /favicon.ico` | — | SVG favicon served dynamically (no static file) |

#### API — Project

| Method | Route | Description |
|---|---|---|
| `POST` | `/api/project` | Create project; accepts `project_name` and optional `author` |
| `PUT` | `/api/project` | Rename / update author; clears author if key present but empty |
| `GET` | `/api/project` | Returns `{ project_name, author }`; 404 if no store file exists |
| `DELETE` | `/api/project` | Clears session and removes store file |
| `POST` | `/api/project/import` | Import from Excel |
| `GET` | `/api/export-project` | Download Excel workbook |

#### API — Aspects

| Method | Route | Description |
|---|---|---|
| `GET` | `/api/aspects` | List aspects (table rows) |
| `POST` | `/api/aspects` | Add aspect |
| `PATCH` | `/api/aspects` | Reorder aspects |
| `PATCH` | `/api/aspects/<name>` | Update description |
| `GET` | `/api/aspect-names` | List aspect names only |
| `GET` | `/api/aspects/<name>/levels` | List levels |
| `POST` | `/api/aspects/<name>/levels` | Add level; raises 400 if level already exists |
| `PATCH` | `/api/aspects/<name>/levels/<level>` | Update level description |
| `GET` | `/api/aspects/<name>/levels/<level>/delete-preview` | Return deletion impact (VDiffs, AL relations, VDCM entries, consequences) without committing |
| `DELETE` | `/api/aspects/<name>/levels/<level>` | Delete aspect level and all associated data |
| `GET` | `/api/aspects/<name>/relations` | Get relations matrix |
| `PATCH` | `/api/aspects/<name>/relations/<la>/<lb>` | Set relation |
| `POST` | `/api/aspects/<name>/relations/batch` | Apply a batch of relation changes atomically; aborts all on collision |
| `GET` | `/api/aspects/<name>/level-graph` | Level graph for Vis.js |
| `GET` | `/api/level-descriptions` | All level descriptions |
| `GET` | `/api/aspects/<name>/vdiff-classification` | Classify VDiffs as non_negative / negative / undecided; `?closure=1` for closure-based classification |

#### API — VDiff matrix

| Method | Route | Description |
|---|---|---|
| `GET` | `/api/vdiff-matrix/<an1>/<an2>` | Get sub-matrix with derived order relations |
| `PATCH` | `/api/vdiff-matrix/<an1>/<l1a>/<l1b>/<an2>/<l2a>/<l2b>` | Set VDiff order relation |
| `POST` | `/api/vdiff-matrix/batch` | Apply a batch of VDiff order relation changes atomically; aborts all on collision |


#### API — Other

| Method | Route | Description |
|---|---|---|
| `GET` | `/api/constants` | Symbol constants for the UI |
| `GET` | `/api/consequences` | Named consequences table; level cells are `null` (JSON) when incomplete |
| `POST` | `/api/consequences` | Add consequence |
| `PATCH` | `/api/consequences/<short_name>` | Set one aspect's level in an existing consequence (existing levels only) |
| `DELETE` | `/api/consequences/<short_name>` | Delete a named consequence |
| `GET` | `/api/consequence_space` | Full consequence space |
| `GET` | `/api/dominance-graph` | Dominance graph data; returns 409 with `{ error, incomplete: [...] }` if any consequence is incomplete |

#### Formatting helpers

`_make_vd(asp, la, lb)`, `_fmt_tokens`, `_fmt_entry`, `_fmt_coll` are module-level helpers shared by `patch_vdiff_relation` and `batch_patch_vdiff_relations`. `_make_vd` normalises `la == lb == "*"` to a natural zero-diff VDiff.

`_fmt_al_tokens`, `_fmt_al_origin`, `_fmt_al_entry`, `_fmt_al_coll` are the equivalent module-level helpers for aspect level relation endpoints (`patch_relation` and `batch_patch_relations`).

---

## Navigation bar (`nav.js`)

Injected above the first `<h1>` on every page (loaded with `defer`). Format:

```
EUDOXA 0.1: Project | Aspects>A1-A2-A3 | Consequences | Value differences
```

- Fetches `/api/constants` → sets `window.EUDOXA`
- Fetches `/api/project` and `/api/aspects` in parallel; returns early silently if either is non-OK — so `/api/project` is a **critical endpoint** for the UI even on pages that don't otherwise use it 
- Current page link shown bold and non-clickable (`.site-nav-current`)
- Fails silently (non-critical)

---

## UI conventions

### Form feedback (add-level / add-consequence)

Both `/aspects/<name>` and `/consequences` show inline feedback after an add-form submission instead of browser `alert()` dialogs.

- **Success** — green box (`.feedback-ok`, defined in `common.css`): `"Level '<name>' added."` / `"Consequence '<name>' added."` with optional `"New levels: …"` suffix.
- **Failure** — red box (`.feedback-error`, defined in `common.css`): validation message or `j.error` from the API response.
- The feedback element persists until the next form submission or *Clear* click.
- In `aspect_detail.html` the element is `<p id="addLevelFeedback">` placed below the levels table.
- In `consequences.html` the element is `<p id="addConsequenceFeedback">` inside the existing `.add-consequence-notice` tfoot row, which is shown/hidden by `showConsequenceFeedback()` / `hideConsequenceFeedback()`.

### Inference panels

Both `/aspects/<name>` and `/vdiff-matrix` show an inference panel after applying changes. Structure:

- Green box (`.asp-infer-ok` / `.vdiff-infer-ok`) for success
- Red box (`.asp-infer-coll` / `.vdiff-infer-coll`) for collision
- Collapsible `<details>` sections: "Added to matrix (N)" and "Inferred in closure (N)", collapsed by default
- No auto-hide timer — panel stays until next Apply, Discard, or pair switch

### Incomplete consequences

A named consequence is **incomplete** when at least one aspect has `None` as its level value. This arises when a new aspect is added after consequences already exist.

**How incompleteness is introduced:** `EudoxaManager.add_aspect` iterates all existing consequences and sets `consequence.aspect_levels[new_aspect] = None` for each. This makes the incomplete state explicit in the stored data rather than relying on the `__getitem__` None fallback.

**Detection:** `EudoxaManager.incomplete_consequences` (property) returns `{short_name: [missing_aspect_names]}` for all consequences that have at least one `None` level.

**Completing a consequence:** `EudoxaManager.set_consequence_level(short_name, aspect_name, level)` sets one cell. Validates that the level exists in the aspect and that the update would not create a duplicate consequence.

**Uniqueness invariant with None values:** `None` is treated as a distinct value — two consequences with `None` for the same aspect are considered equal for that aspect. A new complete consequence cannot duplicate an existing incomplete one (since `None ≠ any_string`). After `add_aspect`, uniqueness is preserved because previously distinct consequences remain distinct.

**UI behaviour (`/consequences`):**
- Incomplete cells are shown with an amber background and a `—` placeholder (`.cons-incomplete`). Clicking an incomplete cell opens a dropdown of the aspect's existing levels.
- On selection, a `PATCH /api/consequences/<name>` call updates the cell in place; the class is removed.
- If an aspect has no levels yet, clicking the cell shows an explanatory tooltip.
- An amber warning banner (`.incomplete-banner`) above the table reports how many consequences and cells are incomplete.
- The **Show dominance graph** button is disabled (`disabled` attribute) while any incomplete cells exist; it re-enables automatically once all are resolved.
- Each consequence row has a **Delete** button. Deletion uses `confirm()` and calls `DELETE /api/consequences/<name>`.

**Dominance graph guard:** `GET /api/dominance-graph` returns 409 with `{ "error": "...", "incomplete": [...] }` if `mgr.incomplete_consequences` is non-empty. The `/dominance-graph` page does not currently handle this 409 specially — direct navigation with incomplete consequences will show a broken graph. The consequences-page button guard is the primary protection.

### Delete aspect level (`/aspects/<name>`)

Follows the same staging-then-confirm pattern used elsewhere (import, relation setting).

1. The user clicks **Delete** next to a level in the levels table.
2. The browser calls `GET /api/aspects/<name>/levels/<level>/delete-preview`, which calls `EudoxaManager.stage_remove_aspect_level`. Nothing is written; the method returns:
   - `vdiffs_removed` — repr strings of all VDiffs whose `from_level` or `to_level` is the target level
   - `al_relations_unset` — within-aspect AL relations currently set for pairs involving the level (BT/BTE/EQ/WTE/WT format, reported from the level's perspective)
   - `vdcm_entries_removed` — non-UNDEFINED cross-aspect VDCM raw entries (`TRUE`/`FALSE`) involving the deleted VDiffs, excluding the NATURAL_ZERO-backed entries already covered by `al_relations_unset`
   - `consequences_removed` — short names of consequences whose entry for this aspect equals the deleted level
3. The staging panel (`.delete-staging`) is shown below the levels table listing all impacted data.
4. On **Confirm deletion** the browser calls `DELETE /api/aspects/<name>/levels/<level>`, which calls `EudoxaManager.confirm_remove_aspect_level`. That method:
   - Removes all VDCM rows keyed by a deleted VDiff, and removes those keys from every other row (including the `NATURAL_ZERO` row)
   - Removes the level from `aspect.levels` and prunes `aspect.vdiffs`
   - Deletes all consequences whose value for this aspect equals the deleted level
   - Saves and returns 200; the browser reloads the page
5. On **Cancel** the staging panel is hidden and no changes are made.

The delete button column is a third `<th>`/`<td>` added to the levels table. Dynamically added rows (via *Add level*) also receive the button. Event delegation on `<tbody>` handles both.

### Aspect detail view (`/aspects/<name>`)

- **Batch apply workflow:** the level relations matrix uses the same pending-changes pattern as the VDiff matrix (see below).
  Changes are accumulated in a `pendingChanges` Map (keyed by `"la|||lb"`).
  Pending cells show the colour of the newly selected relation plus a dashed amber outline (`#e6c200`, class `.rel-pending` on the `<td>`).
  *Apply changes* and *Discard changes* buttons in the section header are disabled until at least one change is pending.
- Clicking *Apply changes* POSTs all pending changes to `/api/aspects/<name>/relations/batch`.
  On success the matrix reloads and highlights clear. On collision **pending changes remain highlighted** so the user can deselect the offending relation(s) and retry.
- `loadRelations()` always clears pending state (matrix is fully replaced on every call).
- Navigating away with pending changes triggers a `beforeunload` guard.

### VDiff matrix view (`/vdiff-matrix`)

- Single `<select id="selPair">` dropdown with values `"A1|A2"` (pipe-separated) and display labels `"A1-A2"`. Aspect names may not contain `|`.
- Matrix loads immediately on page open and on pair selection change.
- **Batch apply workflow:** relation dropdowns do not fire API calls immediately.
  Changes are accumulated in a `pendingChanges` Map (keyed by cell coordinates).
  Pending cells show the colour of the newly selected relation plus a dashed amber outline (`#e6c200`, class `.vdiff-pending` on the `<td>`).
  *Apply changes* and *Discard changes* buttons in the section header are disabled until at least one change is pending.
- Clicking *Apply changes* POSTs all pending changes to `/api/vdiff-matrix/batch`.
  An indeterminate progress bar (`.progress-bar`) is shown during the request. On success the matrix reloads and highlights clear. On collision **pending changes remain highlighted**
  so the user can deselect the offending relation(s) and retry; the inference panel explains this. Clicking *Discard changes* restores all dropdowns and clears the pending state at any time.
- The inference panel sits between the section header and the matrix table so it is always visible without scrolling. It stays visible until the next Apply, Discard, or pair switch.
- Switching pair with pending changes prompts a confirmation dialog. Navigating away from the page with pending changes triggers a `beforeunload` guard.
- Toggle state of *Hide/Show negative* persists across pair changes.

### Colour coding (relations)

| Colour | Meaning |
|---|---|
| Green (`#e6f4ea`) | Better / GT / GTE |
| Yellow (`#fffde7`) | Equal / DEQ |
| Red (`#fce8e6`) | Worse / LT / LTE / FALSE |
| Off-white (`#f8f8f8`) | Undefined |
| Grey (`#d8d8d8`) | Diagonal (immutable) |
| Dashed amber outline (`#e6c200`) | Pending (changed but not yet applied) |

### Indeterminate progress bar

`.progress-bar` / `.progress-bar-fill` (defined in `common.css`) is used wherever an async operation has no deterministic duration. The fill animates left-to-right via `@keyframes progress-slide`. Usage pattern:

```js
progressBar.hidden = false;
try { await fetch(…); }
finally { progressBar.hidden = true; }
```

Used on:
- `/aspects/<name>` — shown during *Apply changes* (`POST /api/aspects/<name>/relations/batch`)
- `/vdiff-matrix` — shown during *Apply changes* (`POST /api/vdiff-matrix/batch`)
- `/` — shown during export (`GET /api/export-project`) and during import (`POST /api/project` + `POST /api/project/import`)

### Button styles

- `.primary` — blue (`#0b5cff`), white text
- `.danger` — dark red (`#c0392b`), white text; used for Confirm deletion
- `.btn-stage-delete` — pale red, used on the per-level Delete button in the levels table
- Default — grey (`#f6f6f6`), matches `.header-link-button` exactly
- `.header-link-button` — `<a>` styled as a button (defined in `common.css`)
- The *Export project* button on `/` is a real `<button>` (not `<a>`); it downloads via `fetch()` + Blob URL so the progress bar can wrap the entire request

---

## Test files

| File | Description |
|---|---|
| `Konsertproblemet.xlsx` | Canonical test file — new format with `◬`, `\|PROJ\|` tab, cross-aspect VDCM entry `Δ(G,IG)⊒Δ(VG,G)` |
| `K_err.xlsx` | Collision test — cell D5 in `\|VDCM\|` causes `Δ(VG,G)⋣◬` to conflict with inferred `Δ(VG,G)⊒◬` |
| `konsert.xlsx` | Older format without `\|PROJ\|` tab |

---

## VDiff classification

VDiffs for a given aspect are classified into three mutually exclusive and exhaustive types based on their relation to the natural zero-diff ◬:

- **non_negative**: Δ(X,Y) ⊒ ◬  (forward relation is TRUE, or natural zero-diff)
- **negative**: Δ(X,Y) ⋣ ◬  (forward relation is FALSE)
- **undecided**: no relation to ◬ set (forward relation is UNDEFINED)

The natural zero-diff ◬ is always classified as non_negative.

### Implementation

`classify_vdiffs(asp: Aspect, vdcm) -> dict` is a **module-level function** in `eudoxa.py` (grouped with `non_neg`, `neg` etc.), taking an `Aspect` and any vdcm — the live matrix or a computed closure. Returns a dict with keys `non_negative`, `negative`, `undecided`, each mapping to a list of `VDiff` objects in `asp.vdiffs` order.

The existing `non_neg` and `neg` functions were corrected to handle the natural zero-diff explicitly (previously they would incorrectly return `False` for it).

### API route

`GET /api/aspects/<name>/vdiff-classification`  
Query param: `closure=1` to classify against the VDCM closure instead of the live matrix (calls `mgr.closure()`, returns 409 if closure has collisions).  
Response: `{ "non_negative": [...], "negative": [...], "undecided": [...] }`  
Each list contains VDiff label strings (`◬`, `Δ(VG,G)`, …) matching the labels used in `/api/vdiff-matrix`.

### UI

`/vdiff-matrix` has a "Hide negative / Show negative" toggle button to the right of the `Δ(<name>) vs Δ(<name>)` header. Hides/shows rows and columns whose label is in the negative set. Classification is fetched in parallel with the Imatrix via `Promise.all`. Toggle state persists across aspect pair changes.

---

## Closure algorithm (`EudoxaManager.closure`)

Computes the transitive closure of the ⊒ relation over all VDiffs, checking internal consistency. Returns `(closure, adds, colls)`: the closed matrix, list of inferences made, and list of collisions (inconsistencies). A non-empty `colls` means the preference structure is inconsistent.

### Inference rules

| Label | Premises | Conclusion | Notes |
|---|---|---|---|
| `DiffP` | cd⊒ef (same aspect) | ce⊒df | Intra-aspect difference property |
| `NegDiffP` | cd⋣ef (same aspect) | fd⋣ec | Negative difference property |
| `TransP` | ab⊒cd, cd⊒ef | ab⊒ef | Positive transitivity |
| `InvP_R` | ab⊒cd, cd⊒xx | dc⊒ba | Inversion when right endpoint is zero-diff |
| `InvP_L` | xx⊒cd, cd⊒ef | fe⊒dc | Inversion when left endpoint is zero-diff |
| `NegTransP` | ab⋣cd, cd⋣ef | ab⋣ef | Negative transitivity |
| `NegTransP_DEQ_L` | ab≜cd, cd⋣ef | ab⋣ef | Neg. transitivity; left premise weakened to ≜ |
| `NegTransP_DEQ_R` | ab⋣cd, cd≜ef | ab⋣ef | Neg. transitivity; right premise weakened to ≜ |
| `NegInvP_L` | xx⋣cd, cd⋣ef | fe⋣dc | Neg. inversion when left endpoint is zero-diff |
| `NegInvP_R` | ab⋣cd, cd⋣xx | dc⋣ba | Neg. inversion when right endpoint is zero-diff |

`xx` denotes a natural zero-diff (from_level == to_level). `InvP_L`/`InvP_R` and `NegInvP_L`/`NegInvP_R` are not derivable by chaining `DiffP`/`NegDiffP`
and are therefore necessary axioms, not speed-up heuristics. `NegTransP_DEQ_L` and `NegTransP_DEQ_R` are negative-transitivity variants (conclusion is `⋣`), not variants of positive transitivity — the former label `TransP2` was a misnomer.

### Unit tests (`tests/test_closure.py`)

34 tests organised into eight classes, run with `python -m unittest tests/test_closure.py`.

| Class | What is tested |
|---|---|
| `TestClosureBasic` | Empty manager; single relation; zero-diff reflexivity; unrelated-cell isolation |
| `TestClosureTransP` | Intra- and cross-aspect chains; length-4 chain; no spurious reverse |
| `TestClosureNegTransP` | Cross-aspect and length-4 negative chains; single-premise isolation |
| `TestClosureDiffP` | `DiffP` and `NegDiffP`; cross-aspect guard; `DiffP`→`TransP` multi-pass case |
| `TestClosureInvP` | `InvP_R` and `InvP_L` (both zero-diff endpoint variants) |
| `TestClosureNegInvP` | `NegInvP_L` and `NegInvP_R` |
| `TestClosureNegTransPDEQ` | `NegTransP_DEQ_L`, `NegTransP_DEQ_R`; DEQ-alone spurious-⋣ guard |
| `TestClosureCollisions` | Direct clash via `set_vdiff_relation`; closure-derived collisions for every rule |

Helper functions `make_mgr(aspects)` and `rel(closure, a1, l1a, l1b, a2, l2a, l2b)` reduce boilerplate throughout.

### Complexity

The algorithm runs a fixed-point outer loop (repeat until no new entry is added to the closure), with two phases per iteration:

- **Phase 1 — DiffP / NegDiffP** (same-aspect only): iterates over aspects and   then over all ordered pairs of levels within each aspect, so cost is O(Σ_asp n_asp⁴) per outer iteration — much cheaper than O(n⁴) because cross-aspect pairs are never visited.
- **Phase 2 — TransP / InvP / NegTransP / NegInvP** (cross-aspect): Floyd-Warshall with `cd` as the outermost (pivot) loop, then `ab` and `ef` as inner loops. Cost is O(n³) per outer iteration. InvP/NegInvP are handled inside Phase 2 via zero-diff checks (`ef.natural_zero()`, `ab.natural_zero()`) because they involve cross-aspect triples.

The fixed-point loop terminates because every iteration must add at least one new entry (the closure is monotone and finite). Worst-case complexity is O(n⁴) — when DiffP and TransP alternate to depth n — but the typical depth d ≈ 2–4, giving O(d·n³) in practice. The `cd`-outermost order in Phase 2 means a single Phase 2 pass suffices for pure transitivity chains (Floyd-Warshall invariant);
extra outer iterations are only needed when Phase 1 adds new entries that create new TransP premises.

## Known issues

- **Incomplete consequences** — decide on how to handle consequences that are added before first aspect level is added.

- **Aspect reordering via drag-and-drop** in `/` was attempted but deferred.

- `pos`, `zero`, and `non_pos` had a natural-zero bug (returning incorrect results for ◬) that was present in `non_neg` and `neg` too; all five were corrected in the vdcm refactor (branch `refactor/vdcm`).

- **Response time** for Apply changes in `/vdiff-matrix` and `/aspects/<name>` is dominated by the closure computation. Worst-case complexity is O(n⁴) but typical cost is O(d·n³) with d ≈ 2–4. An incremental closure algorithm (O(n²) per relation change) remains a longer-term option.

---

## Planned/pending work

- Consider incremental closure algorithm to reduce per-apply cost from O(n⁴) to O(n²) per relation

- Handle incomplete consequences on `/dominance-graph` (direct navigation with incomplete consequences currently shows a broken page; the button guard in `/consequences` is the primary protection)

- Add Delete aspect functionality

- Show collection of differences (special view?) and let the user set "undecided" differences as pos/non-neg/zero/non-pos/neg

- ~~Design choice: Special treatment of natural zero diff, to avoid redundancy?~~ Resolved: vdcm refactored to adjacency dict with single `NATURAL_ZERO` key (branch `refactor/vdcm`).

- Vdiff relation matrix closure

- Show vdiffs for a given aspect (organized by level)

- Show vdiff matrix closure

- Change (re-sort) aspect order 

- Manually change (re-sort) aspect level order

- Automatically change (re-sort) aspect level order according to some criterion

- Add 'Maximize' and 'Minimize' property to numerical aspects, and apply to all levels

- Import consequences only

- Export single aspect

- More feedback (and more human-readable) to user on import and export

- Export for utility functions and utility difference calculations

- Client-side logging

- Server-side logging

- Change aspect data type to "categorical" (str) and "numerical" (float)
