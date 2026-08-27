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
    ├── index.html          "/" — read-only project overview: aspects summary (Name/type/description/#levels/#Δ), consequences list
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

### Aspect type change

`Aspect.change_type(new_type: Type) -> list` validates all existing levels against `new_type` via `parse_type`. If all pass, sets `self.data_type` and returns `[]`; otherwise leaves `self.data_type` unchanged and returns the list of failing level names. Upcasts (e.g. `int`→`float`, anything→`str`) always return `[]`. Downcasts fail if any level cannot be parsed into the stricter type.

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
| `POST` | `/api/project/scan-cons-file` | Scan an Excel file's `\|CONS\|` tab and return a staged preview (aspects inferred from header row, levels from data); no project required |
| `POST` | `/api/project/commit-cons-import` | Apply a staged CONS import (`{staged: {...}}` JSON) to the current empty project; creates aspects and levels, then adds consequences |
| `GET` | `/api/export-aspects` | Download a multi-tab workbook with one `\|ASP\ <name>\|` tab per aspect (levels + relations matrix); filename `{project_name}_aspects.xlsx` |
| `GET` | `/api/export-consequences` | Download a single-tab `\|CONS\|` workbook for the current project; filename `{project_name}_consequences.xlsx` |
| `GET` | `/api/export-project` | Download Excel workbook |

#### API — Aspects

| Method | Route | Description |
|---|---|---|
| `GET` | `/api/aspects` | List aspects (table rows) |
| `POST` | `/api/aspects` | Add aspect |
| `PATCH` | `/api/aspects` | Reorder aspects |
| `PATCH` | `/api/aspects/<name>` | Update description or data type; `data_type` must be `"str"`, `"int"`, or `"float"`; rejected with 400 listing failing level names if any existing level cannot be parsed into the new type |
| `GET` | `/api/aspect-names` | List aspect names only |
| `GET` | `/api/aspects/<name>/levels` | List levels |
| `POST` | `/api/aspects/<name>/levels` | Add level; raises 400 if level already exists |
| `PATCH` | `/api/aspects/<name>/levels/<level>` | Update level description |
| `GET` | `/api/aspects/<name>/levels/<level>/delete-preview` | Return deletion impact (VDiffs, AL relations, VDCM entries, consequences) without committing |
| `DELETE` | `/api/aspects/<name>/levels/<level>` | Delete aspect level and all associated data |
| `GET` | `/api/aspects/<name>/delete-preview` | Return deletion impact for entire aspect without committing |
| `DELETE` | `/api/aspects/<name>` | Delete aspect; body `{ "consequences": "keep" \| "discard_duplicates" \| "discard_all" }` |
| `GET` | `/api/aspects/<name>/relations` | Get relations matrix |
| `PATCH` | `/api/aspects/<name>/relations/<la>/<lb>` | Set relation |
| `POST` | `/api/aspects/<name>/relations/batch` | Apply a batch of relation changes atomically; aborts all on collision |
| `POST` | `/api/aspects/<name>/relations/closure` | Get full (all-aspects) closure additions: cells where the AL relation is UNDEFINED in committed ∪ body but the closure infers one. Body: `{ "changes": [{la, lb, relation}] }` — the caller's currently pending changes, so this departs from committed ∪ pending, not the committed matrix alone. Returns `{ cells: [{la, lb, relation}], adds: [...], inferred_adds: [...] }` — `adds`/`inferred_adds` are `_fmt_al_entry`-formatted derivation strings (same as the batch-apply response) explaining the raw vdcm writes for `changes` itself and the closure-derived consequences behind `cells`. Returns 409 with `{ colls }` if the closure has collisions. |
| `POST` | `/api/aspects/<name>/relations/partial-closure` | Same body/response shape as the closure endpoint above, but the closure is restricted to this aspect's own VDiffs (skips cross-aspect propagation) — cheaper, used for live feedback while manually staging a relation. Incomplete relative to the full closure (may miss inferences that pivot through another aspect), but a collision it reports is always genuine. |
| `GET` | `/api/aspects/<name>/relations/order` | Return ordering pairs for a numerical aspect without committing. Query param: `direction=maximize\|minimize`. Returns `{ pairs: [{la, lb, relation}] }`. Read-only — does not modify the matrix. |
| `GET` | `/api/aspects/<name>/level-graph` | Level graph for Vis.js |
| `GET` | `/api/level-descriptions` | All level descriptions |
| `GET` | `/api/aspects/<name>/vdiff-classification` | Classify VDiffs as non_negative / negative / undecided; `?closure=1` for closure-based classification |

#### API — VDiff matrix

| Method | Route | Description |
|---|---|---|
| `GET` | `/api/vdiff-matrix/<an1>/<an2>` | Get sub-matrix with derived order relations |
| `GET` | `/api/vdiff-matrix/<an1>/<an2>/closure` | Get closure additions: cells where the committed order is UNDEFINED but the closure infers a relation. Returns `{ cells: [{row_label, col_label, order_rel}] }`. Returns 409 with `{ colls }` if the closure has collisions. |
| `PATCH` | `/api/vdiff-matrix/<an1>/<l1a>/<l1b>/<an2>/<l2a>/<l2b>` | Set VDiff order relation |
| `POST` | `/api/vdiff-matrix/batch` | Apply a batch of VDiff order relation changes atomically; aborts all on collision |


#### API — Other

| Method | Route | Description |
|---|---|---|
| `GET` | `/api/constants` | Symbol constants for the UI |
| `GET` | `/api/consequences` | Named consequences table; level cells are `null` (JSON) when incomplete |
| `POST` | `/api/consequences` | Add consequence |
| `PATCH` | `/api/consequences/<short_name>` | Set one aspect's level in an existing consequence; creates the level in the aspect if it does not already exist; returns `{ "new_level": true }` when a level was created |
| `DELETE` | `/api/consequences/<short_name>` | Delete a named consequence |
| `GET` | `/api/consequence_space` | Consequence space; aspects with no levels contribute a `null` placeholder row so the table is never empty; `null` cells are returned as JSON `null` |
| `GET` | `/api/dominance-graph` | Dominance graph data; returns 409 with `{ error, incomplete: [...] }` if any consequence is incomplete |

#### Formatting helpers

`dtype_label(type_name)` maps internal type names to display labels: `"str"` → `"Categorical (text)"`, `"float"` → `"Numerical (general)"`, `"int"` → `"Numerical (integer only)"`. Used in all routes that pass `dtype` to templates or API responses. The `/aspects/<name>` route passes both `dtype` (display label) and `dtype_raw` (raw name `"str"`/`"int"`/`"float"`) to the template so the type dropdown can be pre-selected correctly.

`_derive_vdiff_order(raw_fwd, raw_bwd)` is a module-level helper (extracted from `get_vdiff_matrix`) shared by both the matrix and closure endpoints. Maps raw TRUE/FALSE/UNDEFINED pairs to the derived GT/GTE/DEQ/LTE/LT/FALSE/UNDEFINED order symbol.

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

### Type change (`/aspects/<name>`)

The "Type:" row in the aspect summary `<dl>` is an inline `<select>` dropdown pre-selected on the current type. On change it immediately PATCHes `/api/aspects/<name>` with `{ data_type }`. Success shows `"Type updated."` in an inline `<span>` to the right of the dropdown; the message clears automatically after 3 seconds. Failure reverts the dropdown to its previous value and shows the error (including failing level names) in `<p id="typeError">` below the summary block; that element is dismissed by the next click anywhere on the page.

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

**Completing a consequence:** `EudoxaManager.set_consequence_level(short_name, aspect_name, level)` sets one cell. Validates that the level exists in the aspect and that the update would not create a duplicate consequence. The `PATCH /api/consequences/<short_name>` route creates the level in the aspect first if it does not yet exist (mirroring `add_consequence` behaviour), so callers may supply a brand-new level name.

**Uniqueness invariant with None values:** `None` is treated as a distinct value — two consequences with `None` for the same aspect are considered equal for that aspect. A new complete consequence cannot duplicate an existing incomplete one (since `None ≠ any_string`). After `add_aspect`, uniqueness is preserved because previously distinct consequences remain distinct.

**UI behaviour (`/consequences`):**
- Incomplete cells are shown with an amber background and a `—` placeholder (`.cons-incomplete`). Clicking an incomplete cell opens a hybrid dropdown: existing levels of that aspect plus a **New level…** option (the same pattern as the add-consequence form footer). Selecting an existing level commits immediately via `PATCH`; selecting **New level…** reveals a text input — pressing Enter commits the new level name, Escape restores the cell.
- If `new_level: true` is returned by `PATCH`, `aspectData` is updated in-place and the add-consequence form footer is rebuilt so the new level appears there too.
- On a successful commit the cell class is removed and `consNodeData` is updated.
- An amber warning banner (`.incomplete-banner`) above the table reports how many consequences and cells are incomplete.
- The **Show dominance graph** button is disabled (`disabled` attribute) while any incomplete cells exist; it re-enables automatically once all are resolved.
- Each consequence row has a **Delete** button. Deletion uses `confirm()` and calls `DELETE /api/consequences/<name>`.

**Consequence space with no-level aspects:** `EudoxaManager.compute_consequence_space` substitutes `[None]` for any aspect that has no levels, so the Cartesian product remains non-empty. The consequence space dialog displays `null` cells as "—" (amber, `.cons-incomplete`). Clicking such a row pre-fills the add-consequence form as usual but leaves the no-levels aspect dropdown at the blank "— select level —" option, prompting the user to choose or create a level.

**Consequence space highlighting:** Named consequences are highlighted in the space dialog by matching each space row against `consNodeData` (keyed by `JSON.stringify(aspectData.map(a => cons.levels[a.name] ?? null))`). This approach correctly handles `null` placeholder values; an earlier DOM-scraping approach using `td.textContent` failed because incomplete cells render "—" via a CSS `::before` pseudo-element and have empty `textContent`.

**Dominance graph guard:** `GET /api/dominance-graph` returns 409 with `{ "error": "...", "incomplete": [...] }` if `mgr.incomplete_consequences` is non-empty. The `/dominance-graph` page handles non-OK responses generically, displaying `errData.error` as an inline error message, so direct navigation with incomplete consequences shows a clean "Some consequences are incomplete." message. The consequences-page button guard additionally prevents the navigation in the first place.

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

### Delete aspect (`/aspects`)

Follows the same staging-then-confirm pattern as delete aspect level.

1. The user clicks **Delete** next to an aspect in the aspects table.
2. The browser calls `GET /api/aspects/<name>/delete-preview`, which calls `EudoxaManager.stage_remove_aspect`. Nothing is written; the method returns:
   - `levels_removed` — level names
   - `vdiffs_removed` — repr strings of all VDiffs for this aspect (excluding `NATURAL_ZERO`, which is never removed)
   - `al_relations_unset` — `[{la, relation, lb}]` for all set within-aspect AL relations
   - `vdcm_entries_removed` — `[{vd1, relation, vd2}]` for non-UNDEFINED cross-aspect VDCM entries involving this aspect's VDiffs
   - `consequence_count` — total named consequences
   - `duplicate_groups` — `[{keep, discard}]` groups where removing the aspect collapses consequences to the same tuple; `keep` is the lexicographically first short name
   - `discarded_if_keep` — count of consequences discarded under the "keep" option
3. The staging panel (`.delete-staging`, defined in `common.css`) is shown below the aspects table. It lists all impacted data and explains what each option does for duplicate groups.
4. Three action buttons are offered (simplified to Cancel + Confirm deletion when there are no consequences; "Discard duplicates" is hidden when no duplicate groups arise):
   - **Cancel** — hide panel, no changes
   - **Delete — keep consequences** — calls `DELETE /api/aspects/<name>` with `{ "consequences": "keep" }`; strips aspect key from all consequences, discards all but the lexicographically first short name from each duplicate group
   - **Delete — discard duplicates** — calls with `{ "consequences": "discard_duplicates" }`; strips aspect key, discards every member of any duplicate group, keeps only consequences that remained unique
   - **Delete — discard all consequences** — calls with `{ "consequences": "discard_all" }`; deletes all named consequences
5. On confirmation the browser reloads the page.

`EudoxaManager.confirm_remove_aspect` removes the aspect's VDCM rows/columns (excluding `NATURAL_ZERO`), deletes the aspect from `mgr.aspects`, then applies the chosen consequence mode.

The `.delete-staging` CSS block was moved from `aspect_detail.css` to `common.css` so it is available on both `/aspects` and `/aspects/<name>`.

### Aspect detail view (`/aspects/<name>`)

The Level relations section uses a **tabbed layout**: a *Matrix* tab and a *Graph* tab, toggled by `tabBtnMatrix` / `tabBtnGraph` buttons in the section header. Both tabs share the same `pendingChanges` Map and the same *Apply changes* / *Discard changes* / *View closure* buttons.

- **Batch apply workflow:** changes are accumulated in a `pendingChanges` Map (keyed by `"la|||lb"`). Each entry carries `{ la, lb, newRel, originalRel, fromClosure, fromOrdering, fromPartialClosure }`.
  Pending cells show the colour of the newly selected relation plus a dashed outline: amber (`#e6c200`, class `.rel-pending`) for user-initiated changes and for partial-closure-inferred changes (see below — same visual class, distinguished only by tooltip), blue (`#5c6bc0`, class `.rel-closure-pending`) for closure-staged changes, teal (`#00897b`, class `.rel-ordering-pending`) for ordering-staged changes (Maximize/Minimize).
  *Apply changes* and *Discard changes* buttons in the section header are disabled until at least one change is pending.
- Clicking *Apply changes* POSTs all pending changes to `/api/aspects/<name>/relations/batch`.
  On success the matrix reloads and highlights clear. On collision **pending changes remain highlighted** so the user can deselect the offending relation(s) and retry.
- **`syncMatrixCell(cellKey)`** — helper that reads the current `pendingChanges` entry for a cell and updates the `<td>` class, `<select>` value, and `title` attribute accordingly. Called by `viewClosure`, `refreshPartialClosure`, `discardPendingChanges`, `makeCellDropdown`, and `stageRelationFromGraph` to keep the matrix DOM consistent without duplicating logic.
- **View closure button:** POSTs to `/api/aspects/<name>/relations/closure` with `{ changes }` — the AL relations currently in `pendingChanges` (manual/ordering; never contains `fromClosure` entries, since the button acts as "Hide closure" instead whenever any exist) — and stages every returned cell into `pendingChanges` with `fromClosure: true` and the blue dashed border. This departs from committed ∪ pending, not the committed matrix alone, so a manual pick made before clicking "View closure" is accounted for. Cells already in `pendingChanges` (user-modified) are skipped. If no new relations can be inferred the inference panel shows a "no new relations" message; collisions show a red panel. The button label toggles to "Hide closure" while closure-staged entries exist; clicking it again unstages them (and re-runs the partial-closure preview below, since removing the full-closure overlay can change what a smaller, restricted closure would still find). While closure entries are staged, the *Show reduction* button in the Graph tab is **disabled** (tooltip: "Hide closure first to switch to reduction view") — this prevents an ill-defined mode where the committed transitive reduction and the closure overlay are active simultaneously.
- **Partial-closure preview (manual-add feedback):** every time a manual pick changes `pendingChanges` (matrix dropdown `change`, or a graph `stageRelationFromGraph` call), `refreshPartialClosure()` fires. It first strips any existing `fromPartialClosure` entries from `pendingChanges` (they're always recomputed from scratch, not diffed — cheap since the computation is restricted to the current aspect), then POSTs the remaining pending changes to `/api/aspects/<name>/relations/partial-closure`. On success, any newly-inferred cells not already pending are added with `fromPartialClosure: true` and rendered with the same `.rel-pending` (amber) styling as a manual pick, but a distinguishing tooltip (`cellTooltip(..., "local")` → "Inferred (local): …"; the graph's `pendingEdgeStyle` uses the same "Inferred (local)" prefix). On a 409 the manual pick is **not** reverted — a small dedicated panel (`#partialClosureWarning`, separate from the main `#inferencePanel` so it doesn't clobber Apply/View-closure feedback) explains that Apply will reject it; the full closure at Apply time remains the actual gate. On success with at least one newly-inferred cell, the same panel (`showPartialClosureInfo`, amber `.asp-infer-pending` styling — deliberately *not* the green `.asp-infer-ok` used by Apply's own success panel, since these cells are only staged, not committed, and green there would read as "already saved") mirrors the Apply-time inference panel's two-section layout via the shared `collapsible()` helper: "Your change" (the raw vdcm writes for the proposed *changes* themselves) and "Inferred locally" (the closure-derived consequences behind `cells`) — both `_fmt_al_entry`-formatted strings from the endpoint's `adds`/`inferred_adds`, not just the flat relation list, so the preview explains *why* a cell was inferred the same way Apply's panel does. Nothing is shown when nothing new was inferred, to avoid a panel popping on every keystroke-level edit. Note "Inferred locally" is the *entire* raw derivation trace from the restricted `closure()` call (every intermediate vdcm write, not filtered down to just what's relevant to `cells`), so it can run to dozens or low hundreds of entries even for a handful of levels — same verbosity characteristic the Apply-time panel already has, collapsed by default. A monotonically increasing sequence counter (`partialClosureSeq`) discards a response superseded by a newer edit. Because this closure is restricted to one aspect (see `EudoxaManager.closure(restrict_to_aspect=...)`), it's cheaper than "View closure" but incomplete — it can miss inferences that require pivoting through another aspect's VDiff — though a collision it does report is always genuine, since restriction only removes inference paths. **Only the most recent feedback is ever shown, regardless of source.** `clearFeedbackPanels()` hides both `#inferencePanel` and `#partialClosureWarning` and is called at the very start of every pendingChanges-mutating entry point: `refreshPartialClosure()` (covers every manual pick, matrix or graph), `viewClosure()` (both the "fetch closure" and "hide closure" branches — before this fix, the "cells found" success branch never touched either panel, so a stale message from an earlier action could sit there indefinitely), `stageOrdering()` (Maximize/Minimize — previously touched neither panel at all except its own error case), `applyPendingChanges()`, and `discardPendingChanges()`. Each function then shows whatever fresh content is relevant to its own outcome (or nothing, leaving both cleared). Before this, only `discardPendingChanges()` and (after an earlier fix) `applyPendingChanges()`'s response handler cleared stale panels — e.g. applying a change, then starting a new edit, left the old "N change(s) applied" panel visible next to the new partial-closure preview until the next Apply/Discard.
- **Maximize / Minimize buttons** (numerical aspects only — `dtype_raw` is `int` or `float`): fetches `GET /api/aspects/<name>/relations/order?direction=maximize|minimize` (read-only; returns `{ pairs: [{la, lb, relation}] }`) and stages all returned pairs into `pendingChanges` with `fromOrdering: true` and the teal dashed border. Cells already in `pendingChanges` (user-modified or closure-staged) are skipped. Clicking the same button again unstages all ordering entries (toggle off); clicking the opposite direction replaces them. Button labels toggle to "Hide maximize" / "Hide minimize" while the corresponding direction is staged. `currentOrderingDirection` tracks which direction is active (null if none staged).
- A closure-staged cell is promoted to `fromClosure: false` (amber border) the moment the user interacts with its dropdown: in the **matrix**, on `pointerdown` of the `<select>`; in the **graph picker**, likewise on `pointerdown` of the picker `<select>`. Both cover the "same value" case where `change` never fires. Ordering-staged cells are promoted to `fromOrdering: false` by the same `pointerdown` handlers.
- `cellElems` Map (keyed by `"la|||lb"`) stores `{ td, sel, originalRel, la, lb }` for every non-diagonal cell; populated by `makeCellDropdown`, cleared by `loadRelations`. Used by `syncMatrixCell`, `viewClosure`, and `stageOrdering`.
- **Cell tooltips:** non-diagonal cells show a `title` attribute of the form `la rel lb | Click to edit. Apply changes to save.`. Closure-staged cells show `Inferred: la rel lb`. Ordering-staged cells show `Ordering: la rel lb`. (`cellTooltip` takes a `source` string: `null`, `"closure"`, or `"ordering"`.)
- **Inference panel** sits between the progress bar and the tab panels (outside both `tabPanelMatrix` and `tabPanelGraph`) so it is visible regardless of the active tab.
- `loadRelations()` always clears `pendingChanges` and `cellElems` (matrix is fully replaced on every call).
- Navigating away with pending changes triggers a `beforeunload` guard.

**Graph tab:**

- `activateTab(name)` switches between `tabPanelMatrix` and `tabPanelGraph`, updates tab button styles, and fires `requestAnimationFrame(() => renderGraphFromState())` on switch to Graph — deferring until the container has real pixel dimensions so Vis.js measures them correctly.
- `renderGraphFromState()` — async. Fetches committed graph data (cached in `graphCache`; invalidated by `loadRelations` / `loadLevelGraph`). Builds an `edgeMap` from committed edges, then overlays `pendingChanges`: closure/ordering entries sorted first (low priority), user entries sorted last (amber dashed, high priority), so user entries always win when both directions of the same cell pair appear. Edge colours: amber (`#e6c200`) = manual pending, blue (`#5c6bc0`) = closure-inferred, teal (`#00897b`) = ordering-staged, red (`#e07070`) = pending deletion. Calls `mainNetwork.fit()` immediately after construction (hierarchical layout is synchronous, so the viewport is correct immediately).
- `stageRelationFromGraph(membersA, membersB, rel)` — stages the relation for all cell pairs across the two equivalence classes into `pendingChanges` with `fromClosure: false`, calls `syncMatrixCell` for each pair, then calls `renderGraphFromState`.
- **Node interaction:** click one node → picker label A appears; click a second node → picker label B appears and a `<select>` is populated with the current relation (pending takes priority over committed). On `pointerdown` of the picker select, any closure-staged entry for that pair is promoted to `fromClosure: false` and the graph repaints immediately (amber). On `change`, `stageRelationFromGraph` is called and the picker closes. Cancel or outside-click calls `clearFirstNode` without staging anything.
- **TR toggle** (*Show full graph* / *Show reduction*): toggles `trStateMain` and re-renders from `graphCache`. Disabled while closure entries are staged.

### VDiff matrix view (`/vdiff-matrix`)

- Single `<select id="selPair">` dropdown with values `"A1|A2"` (pipe-separated) and display labels `"A1-A2"`. Aspect names may not contain `|`.
- Matrix loads immediately on page open and on pair selection change.
- **Batch apply workflow:** relation dropdowns do not fire API calls immediately.
  Changes are accumulated in a `pendingChanges` Map (keyed by cell coordinates). Each entry carries a `fromClosure` flag (see below).
  Pending cells show the colour of the newly selected relation plus a dashed outline: amber (`#e6c200`, `.vdiff-pending`) for user-initiated changes, blue (`#5c6bc0`, `.vdiff-closure-pending`) for closure-staged changes.
  *Apply changes* and *Discard changes* buttons in the section header are disabled until at least one change is pending.
- Clicking *Apply changes* POSTs all pending changes to `/api/vdiff-matrix/batch`.
  An indeterminate progress bar (`.progress-bar`) is shown during the request. On success the matrix reloads and highlights clear. On collision **pending changes remain highlighted**
  so the user can deselect the offending relation(s) and retry; the inference panel explains this. Clicking *Discard changes* restores all dropdowns and clears the pending state at any time.
- **View closure button:** fetches `GET /api/vdiff-matrix/<an1>/<an2>/closure` and stages every closure addition directly into `pendingChanges` with `fromClosure: true` and the blue dashed border. Cells that are already in `pendingChanges` (user-modified) are skipped. If no new relations can be inferred the inference panel shows a "no new relations" message; collisions show a red panel. The button label toggles to "Hide closure" while closure-staged entries exist; clicking it again unstages them (reverts select value, class, and tooltip). A closure-staged cell is promoted to `fromClosure: false` (amber border) as soon as the user clicks its dropdown (`pointerdown`), before a value is even selected. This covers the case where the user re-selects the same option (which suppresses the `change` event) and makes the feedback immediate.
- `cellElems` Map (keyed by cellKey) stores `{ td, sel, originalOrder }` for every non-diagonal cell; populated by `renderMatrix`, cleared by `loadMatrix`. Used by `viewClosure` to look up elements.
- **Cell tooltips:** non-diagonal cells with a committed relation show a `title` attribute of the form `Δ[A1](la,lb) ⊐ Δ[A2](la,lb)`. Closure-staged cells show `Inferred: Δ[A1](la,lb) ⊐ Δ[A2](la,lb)`. Tooltips are cleared when a cell reverts to UNDEFINED.
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
| Dashed amber outline (`#e6c200`) | Pending — user-initiated change not yet applied, or a consequence of one inferred by the restricted (aspect-local) partial-closure preview — same colour, distinguished only by tooltip ("Inferred (local): …") |
| Dashed blue outline (`#5c6bc0`) | Pending — closure-inferred change staged by "View closure" |
| Dashed teal outline (`#00897b`) | Pending — ordering-staged change from "Maximize" or "Minimize" |

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
- `/` — shown during export (`GET /api/export-project`, `GET /api/export-aspects`, and `GET /api/export-consequences`), during full Excel import (`POST /api/project` + `POST /api/project/import`), and during the CONS-only import scan and commit steps (`POST /api/project/scan-cons-file` / `POST /api/project/commit-cons-import`)

### Button styles

- `.primary` — blue (`#0b5cff`), white text
- `.danger` — dark red (`#c0392b`), white text; used for Confirm deletion; defined in `common.css`
- `.btn-stage-delete` — pale red, used on Delete buttons in the levels table and consequence rows; defined in `common.css`
- Default — grey (`#f6f6f6`), matches `.header-link-button` exactly
- `button:disabled` — opacity 0.45, cursor `not-allowed`; defined in `common.css`; applies to all pages
- `.header-link-button` — `<a>` styled as a button (defined in `common.css`); has `display: inline-block` and `line-height: normal` so it renders identically to `<button>` in all layout contexts
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

Computes the transitive closure of the ⊒ relation over all VDiffs, checking internal consistency. Returns `(closure, adds, colls)`: the closed matrix, list of inferences made, and list of collisions (inconsistencies). A non-empty `colls` means the preference structure is inconsistent. On the success path, `adds` is topologically sorted before being returned — see "Derivation-order sorting of adds" below.

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

`NegDiffP`'s `origin_detail` used to record a copy of its own conclusion (`[fd, rel_cd_ef, ec]`) instead of the premise that triggered it (`[cd, rel_cd_ef, ef]`) — a copy-paste artifact from adapting `DiffP`'s logging pattern. This made the "why" explanation for `NegDiffP` entries tautological (`X ⋣ Y → X ⋣ Y`) and, more importantly, made such entries look dependency-free to anything trying to trace derivation chains (their "premise" could never match another entry's conclusion). Fixed; covered by `TestNegDiffPOrigin`.

### Derivation-order sorting of adds

Each `adds` entry is `[rule_label, origin_detail, result]`; `result` is `[vd1, rel, vd2]` (from `set_vdiff_relation`'s return), and `origin_detail`'s shape depends on the rule (`_RULE_PREMISE_VD_PAIRS` maps each rule label to which `(vd1, vd2)` pairs within `origin_detail` are its premises — one for `DiffP`/`NegDiffP`, two for the `TransP`/`InvP`/`NegTransP`/`NegInvP` family; `SETREL` has none, it's a leaf/axiom).

The fixed-point loop doesn't discover entries in dependency order — Phase 1/Phase 2 interleave across outer iterations, so a premise can be discovered well after something that used it. `_topological_sort_adds(adds)` fixes this as a cheap post-processing pass: because `set_vdiff_relation` only ever writes a given `(vd1, vd2)` cell once (a repeat of the same value is a no-op; a conflicting one is a collision that aborts the whole computation), every fact has *at most one* entry in `adds` that established it, so `_entry_conclusion_key`/`_entry_premise_keys` (also module-level) give an unambiguous entry → premise-entries mapping with no separate graph-construction step needed elsewhere. A stable Kahn's-algorithm sort over that mapping (ties broken by original index) produces the reordered list; `closure()` applies it to `adds` before returning on the success path (not on early-collision returns, since callers discard `adds` on collision anyway). This benefits every caller of `closure()` uniformly (Apply's inference panel, "View closure", the partial-closure preview, VDiff-matrix inference/collision panels) with no changes needed outside `eudoxa.py`, since display order is just list order downstream. Covered by `TestTopologicalSortAdds` (hand-built dependency and independence cases, plus an integration check against real `closure()` output).

### Cross-aspect VDiff disambiguation in derivation/collision text (`app.py: _fmt_vdiff`)

`VDiff.__repr__` deliberately omits the aspect name (e.g. `Δ(1,2)`, not `Δ[A](1,2)`) — the right call for same-aspect displays (a `/vdiff-matrix` row/column already implies its aspect from context) where repeating it would just be noise. But the *cross-aspect* closure can legitimately derive two different facts, from different aspects, that share level names — e.g. `Δ(A,"0","1")` and `Δ(B,"0","1")` — and those rendered as identical-looking `Negative transitivity property: Δ(0,1) ⋣ ◬ ⋣ Δ(1,0) → Δ(1,0) ⋣ Δ(0,1)` lines look like a duplicated/erroneous inference when they're actually two distinct, correct ones. `_fmt_vdiff(vd)` renders `Δ[aspect](la,lb)` for a non-zero VDiff (the natural zero-diff `◬` is left bare — there's only one, regardless of aspect, so it's never ambiguous) and is used everywhere a derivation or collision message can mix aspects: `_fmt_al_tokens`/`_fmt_al_coll` (AL relations) and `_fmt_tokens`/`_fmt_coll`/`_fmt_entry`'s `SETVDREL` branch (VDiff matrix). It is *not* used for the `/vdiff-matrix` table's own row/column labels or `vdiff-classification`'s output — those stay same-aspect and bare `repr()` is correct there.

This required one small change in `eudoxa.py`: `try_set_vdiff_order_relation`'s `SETVDREL` origin used to pre-format its VDiffs with `repr()` before storing them in `origin_detail` (`['SETVDREL', [repr(vd1), order_rel, repr(vd2)]]`), baking in the ambiguity before `app.py` ever saw it. It now stores the raw VDiff objects (`[vd1, order_rel, vd2]`), matching every other origin type, and `_fmt_entry`'s `SETVDREL` branch formats them via `_fmt_vdiff` at display time instead. Covered by `TestSetVdiffRelationOrigin`.

### Closure rule labels (`app.py: _CLOSURE_RULE_LABELS`)

`_fmt_al_origin`/`_fmt_entry` look up a readable label for each rule (e.g. "Transitivity property") before falling back to an unlabelled `RuleName(...)` display. The lookup dict (originally `_AL_RULE_LABELS`, renamed `_CLOSURE_RULE_LABELS` since it's shared by both AL-relation and VDiff-matrix formatting) used stale keys — `InvP`, `TransP2`, `NegTransP2`, `NegInvP` — that `closure()` never actually emits (the real labels always carry an `_L`/`_R` or `_DEQ_L`/`_DEQ_R` suffix: `InvP_R`, `InvP_L`, `NegTransP_DEQ_L`, `NegTransP_DEQ_R`, `NegInvP_L`, `NegInvP_R`). So six of the ten real rule labels silently fell through to the raw fallback (e.g. `InvP_R(Δ[Matsvinn](0,5) ⊒ ◬ ⊒ ◬) → ◬ ⊒ Δ[Matsvinn](5,0)` instead of `Inverse difference property (right): …`), while four of the dict's entries were dead code. Fixed by keying the dict on the actual labels (see the `origin = [...]` assignments in `closure()`); `_fmt_entry`'s generic branch (VDiff matrix) now also consults it instead of always using the raw fallback, which it did unconditionally for every rule before this fix. `TestClosureRuleLabelsComplete` diffs `_CLOSURE_RULE_LABELS`'s keys against `_RULE_PREMISE_VD_PAIRS` (eudoxa.py, which enumerates every non-axiom rule label) so a future rule added to one but not the other fails a test instead of silently rendering unlabelled. This test imports `app.py`, so running `tests/test_closure.py` now requires Flask to be installed (already a project dependency — the app can't run without it — but worth knowing if invoking the test file directly with a bare interpreter that isn't the project's venv).

### Unit tests (`tests/test_closure.py`)

45 tests organised into fourteen classes, run with `python -m unittest tests/test_closure.py`.

| Class | What is tested |
|---|---|
| `TestClosureBasic` | Empty manager; single relation; zero-diff reflexivity; unrelated-cell isolation |
| `TestClosureTransP` | Intra- and cross-aspect chains; length-4 chain; no spurious reverse |
| `TestClosureNegTransP` | Cross-aspect and length-4 negative chains; single-premise isolation |
| `TestClosureDiffP` | `DiffP` and `NegDiffP`; cross-aspect guard; `DiffP`→`TransP` multi-pass case |
| `TestClosureInvP` | `InvP_R` and `InvP_L` (both zero-diff endpoint variants) |
| `TestClosureNegInvP` | `NegInvP_L` and `NegInvP_R` |
| `TestClosureRestricted` | `closure(restrict_to_aspect=...)`: intra-aspect chain still inferred, cross-aspect pivot not inferred, intra-aspect collision still caught |
| `TestTryStageAspectLevelRelations` | `try_stage_aspect_level_relations`: clean multi-change staging returns inferred cells, colliding staging returns colls and no cells; never writes to `self.vdiff_comparison_matrix` |
| `TestClosureNegTransPDEQ` | `NegTransP_DEQ_L`, `NegTransP_DEQ_R`; DEQ-alone spurious-⋣ guard |
| `TestClosureCollisions` | Direct clash via `set_vdiff_relation`; closure-derived collisions for every rule |
| `TestSetVdiffRelationOrigin` | `try_set_vdiff_order_relation`'s `SETVDREL` origin holds VDiff objects, not pre-formatted strings |
| `TestNegDiffPOrigin` | `NegDiffP`'s `origin_detail` records the premise, not the conclusion |
| `TestTopologicalSortAdds` | `_topological_sort_adds`: a dependent entry is moved after its premise; independent entries keep relative order; real `closure()` output is fully dependency-ordered |
| `TestClosureRuleLabelsComplete` | Every rule label `closure()` can produce has a readable name in `app.py`'s `_CLOSURE_RULE_LABELS` |

Helper functions `make_mgr(aspects)` and `rel(closure, a1, l1a, l1b, a2, l2a, l2b)` reduce boilerplate throughout.

### Complexity

The algorithm runs a fixed-point outer loop (repeat until no new entry is added to the closure), with two phases per iteration:

- **Phase 1 — DiffP / NegDiffP** (same-aspect only): iterates over aspects and   then over all ordered pairs of levels within each aspect, so cost is O(Σ_asp n_asp⁴) per outer iteration — much cheaper than O(n⁴) because cross-aspect pairs are never visited.
- **Phase 2 — TransP / InvP / NegTransP / NegInvP** (cross-aspect): Floyd-Warshall with `cd` as the outermost (pivot) loop, then `ab` and `ef` as inner loops. Cost is O(n³) per outer iteration. InvP/NegInvP are handled inside Phase 2 via zero-diff checks (`ef.natural_zero()`, `ab.natural_zero()`) because they involve cross-aspect triples.

The fixed-point loop terminates because every iteration must add at least one new entry (the closure is monotone and finite). Worst-case complexity is O(n⁴) — when DiffP and TransP alternate to depth n — but the typical depth d ≈ 2–4, giving O(d·n³) in practice. The `cd`-outermost order in Phase 2 means a single Phase 2 pass suffices for pure transitivity chains (Floyd-Warshall invariant);
extra outer iterations are only needed when Phase 1 adds new entries that create new TransP premises.

### Restricted closure (`closure(restrict_to_aspect=...)`)

Both phases can be limited to one aspect's own VDiffs (plus the shared `NATURAL_ZERO` bridge): Phase 1 scans only that aspect, and Phase 2's `vd_enum_verbose(aspect_name)` pivot/endpoint loops range only over its VDiffs. This skips the expensive cross-aspect Floyd-Warshall propagation, so it's cheap regardless of how many aspects the project has — cost is bounded by the single aspect's own level count. It's incomplete relative to the unrestricted closure (it can miss an inference that requires pivoting through another aspect's VDiff), but it never produces a false negative on collisions: restriction only removes inference paths, so any collision found under restriction is also present in the unrestricted closure. Used by `try_stage_aspect_level_relations(..., restrict_to_aspect=True)` for the partial-closure manual-add preview in `/aspects/<name>`; `restrict_to_aspect=False` there runs the full closure, used by "View closure".

`EudoxaManager.get_aspect_level_relation(aspect, la, lb, matrix=None)` accepts an optional closure matrix to derive the BT/BTE/EQ/WTE/WT relation against instead of the live vdcm — used by `closure_cells_for_aspect` to extract inferable cells from either a restricted or full closure result without duplicating the derivation logic. The vdcm-write logic shared by `set_aspect_level_relation` and `try_set_aspect_level_relation` (and now `try_stage_aspect_level_relations`) lives in one place, the module-level `_apply_al_relation(matrix, aspect, la_str, lb_str, rel)`.

## Known issues

- **Aspect reordering via drag-and-drop** in `/` was attempted but deferred.

- `pos`, `zero`, and `non_pos` had a natural-zero bug (returning incorrect results for ◬) that was present in `non_neg` and `neg` too; all five were corrected in the vdcm refactor (branch `refactor/vdcm`).

- **Response time** for Apply changes in `/vdiff-matrix` and `/aspects/<name>` is dominated by the closure computation. Worst-case complexity is O(n⁴) but typical cost is O(d·n³) with d ≈ 2–4. An incremental closure algorithm (O(n²) per relation change) remains a longer-term option.

---

## Planned/pending work

- Consider incremental closure algorithm to reduce per-apply cost from O(n⁴) to O(n²) per relation

- ~~Live feedback on a manually-staged AL relation before Apply~~ Resolved: `closure(restrict_to_aspect=...)` computes a closure limited to one aspect (skips cross-aspect propagation, so it's cheap regardless of project size); `POST /api/aspects/<name>/relations/partial-closure` and the client's `refreshPartialClosure()` stage the newly-inferable consequences of a manual pick as amber-pending, alongside a "View closure" fix so it also departs from committed ∪ pending rather than the committed matrix alone.

- ~~Transform the "/" view into a 'Project overview' view with no editing, to avoid different views with (partially) overlapping functionality~~ Resolved: aspects table expanded to Name/Data type/Description/#Levels/#Δ; consequence space dialog and add-consequence form removed from "/".

- Show collection of differences (special view?) and let the user set "undecided" differences as pos/non-neg/zero/non-pos/neg

- ~~Design choice: Special treatment of natural zero diff, to avoid redundancy?~~ Resolved: vdcm refactored to adjacency dict with single `NATURAL_ZERO` key (branch `refactor/vdcm`).

- ~~Vdiff relation matrix closure~~ Resolved: "View closure" button in both `/vdiff-matrix` and `/aspects/<name>` stages all closure-inferred relations as pending changes with a blue dashed border; toggleable and fully integrated with the existing Apply/Discard workflow in each view.

- Show vdiffs for a given aspect (organized by level)

- ~~Show vdiff matrix closure~~ Resolved: see "Vdiff relation matrix closure" above.

- Change (re-sort) aspect order 

- Manually change (re-sort) aspect level order

- Automatically change (re-sort) aspect level order according to some criterion

- ~~Add 'Maximize' and 'Minimize' buttons to numerical aspects~~ Resolved (Option A): **Maximize** and **Minimize** buttons appear in the section header of `/aspects/<name>` when the aspect is numerical. Clicking a button fetches all implied `≻` pairs from `GET /api/aspects/<name>/relations/order?direction=…` and stages them as teal-bordered pending changes, integrated with the existing Apply/Discard workflow. Buttons toggle: clicking again unstages. Consider Option B (persistent property, auto-applied on new levels) as a future enhancement.

- ~~Import/export consequences only~~ Resolved: "Create project from consequences" on `/` bootstraps a new project from a `\|CONS\|`-only file (aspects and levels inferred, staged preview before commit). "Export consequences" in the consequences section header on `/` downloads a single-tab `\|CONS\|` workbook.

- ~~Import/export single aspect~~ Resolved (export side): "Export aspects" in the Aspects section header on `/` downloads a multi-tab workbook with one `\|ASP\|` tab per aspect including the relations matrix, importable via the existing pipeline. Per-aspect import is still pending.

- More feedback (and more human-readable) to user on import and export

- Export for utility functions and utility difference calculations

- Client-side logging

- Server-side logging

- ~~Change aspect data type to "categorical" (str) and "numerical" (float)~~ Resolved differently: type names are displayed as "Categorical (text)" / "Numerical (general)" / "Numerical (integer only)" throughout the UI (internal representation and Excel format unchanged); `/aspects/<name>` supports upcast/downcast via an inline type dropdown with validation.
