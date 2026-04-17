import logging
import os
import openpyxl
from flask import Flask, session, request, jsonify, abort
from flask import render_template
import eudoxa
from eudoxa import EudoxaManager

app = Flask(__name__)
logger = logging.getLogger(__name__)

# -----------------------------------------------------------
#  SESSION / CONFIG
# -----------------------------------------------------------
app.secret_key = os.getenv("SECRET_KEY") or "dev-secret-change-me"

# Store manager data server-side to avoid Flask's 4 KB cookie limit.
_STORE_DIR = os.getenv("MANAGER_STORE_DIR") or os.path.join(
    os.path.dirname(os.path.abspath(__file__)), ".manager_store"
)
os.makedirs(_STORE_DIR, exist_ok=True)


# -----------------------------------------------------------
#  HELPERS
# -----------------------------------------------------------
def _store_path(sid: str) -> str:
    """Return the file path for a session's manager store."""
    safe = "".join(c for c in sid if c in "0123456789abcdef")
    return os.path.join(_STORE_DIR, safe + ".json")


def _get_sid() -> str:
    """Return the current session's store ID, creating one if needed."""
    import uuid
    if "sid" not in session:
        session["sid"] = uuid.uuid4().hex
    return session["sid"]


def load_manager_or_400():
    """Load EudoxaManager from the server-side store, or abort 400."""
    import json
    sid = session.get("sid")
    if not sid:
        abort(400, description="No active project")
    try:
        with open(_store_path(sid), "r", encoding="utf-8") as f:
            return EudoxaManager.from_dict(json.load(f))
    except FileNotFoundError:
        abort(400, description="No active project")
    except Exception:
        logger.exception("Failed to deserialize EudoxaManager")
        abort(400, description="Failed to load project data")


def save_manager(mgr: EudoxaManager):
    """Persist the manager to the server-side store."""
    import json
    sid = _get_sid()
    with open(_store_path(sid), "w", encoding="utf-8") as f:
        json.dump(mgr.to_dict(), f, ensure_ascii=False)


@app.get("/favicon.ico")
def favicon():
    """Return a minimal SVG favicon to silence 404 console noise."""
    from flask import Response
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">'
           '<circle cx="16" cy="16" r="14" fill="#0b5cff"/>'
           '<text x="16" y="22" font-size="18" font-family="sans-serif" '
           'text-anchor="middle" fill="white">E</text></svg>')
    return Response(svg, mimetype="image/svg+xml",
                    headers={"Cache-Control": "max-age=86400"})


@app.after_request
def no_store_html(response):
    """Prevent HTML pages from being served from bfcache on back-navigation."""
    if response.content_type.startswith("text/html"):
        response.headers["Cache-Control"] = "no-store"
    return response


# -----------------------------------------------------------
#  UI
# -----------------------------------------------------------
@app.get("/api/constants")
def get_constants():
    """Return all symbol constants used in the UI as a JSON object."""
    return {
        # VDCM raw values
        "TRUE":      eudoxa.TRUE,
        "FALSE":     eudoxa.FALSE,
        "UNDEFINED": eudoxa.UNDEFINED,
        # Aspect level relations
        "BT":        eudoxa.BT,
        "BTE":       eudoxa.BTE,
        "EQ":        eudoxa.EQ,
        "WTE":       eudoxa.WTE,
        "WT":        eudoxa.WT,
        "AL_RELATION_OPTIONS": eudoxa.AL_RELATION_OPTIONS,
        # Vdiff order relations
        "GT":        eudoxa.GT,
        "GTE":       eudoxa.GTE,
        "DEQ":       eudoxa.DEQ,
        "LTE":       eudoxa.LTE,
        "LT":        eudoxa.LT,
        "VDIFF_RELATION_OPTIONS": eudoxa.VDIFF_RELATION_OPTIONS,
        # Other symbols
        "DELTA":     eudoxa.DELTA,
        "EM_DASH":   "—",
        "ARROW":     "→",
    }, 200


@app.get("/")
def index():
    return render_template("index.html",
                           project_name=session.get("project_name"),
                           author=session.get("author", ""))

# -----------------------------------------------------------
#  REST: PROJECT
# -----------------------------------------------------------

@app.post("/api/project")
def create_project():
    """Create a new project (only if no project already exists)."""
    if "project_name" in session:
        return {"error": "A project already exists. Use PUT to rename."}, 409

    data = request.get_json(silent=True) or {}
    name = (data.get("project_name") or "").strip()

    if not name:
        return {"error": "Project name must be non-empty."}, 400

    mgr = EudoxaManager()

    _get_sid()  # allocate store ID before first save
    session["project_name"] = name
    author = (data.get("author") or "").strip()
    if author:
        session["author"] = author
    save_manager(mgr)

    return {"message": "Project created", "project_name": name}, 201

@app.put("/api/project")
def rename_project():
    """Rename an existing project."""
    if "project_name" not in session:
        return {"error": "No active project. Use POST to create a project."}, 404

    data = request.get_json(silent=True) or {}
    name = (data.get("project_name") or "").strip()

    if not name:
        return {"error": "Project name must be non-empty."}, 400

    session["project_name"] = name
    author = (data.get("author") or "").strip()
    if author:
        session["author"] = author
    elif "author" in data:
        session.pop("author", None)

    return {"message": "Project renamed", "project_name": name}, 200

@app.get("/api/project")
def get_project():
    """Get the project name and author."""
    name = session.get("project_name")
    sid  = session.get("sid")

    if not name or not sid:
        return {"error": "No active project"}, 404

    if not os.path.exists(_store_path(sid)):
        return {"error": "No active project"}, 404

    return {
        "project_name": name,
        "author":       session.get("author", ""),
    }, 200


@app.delete("/api/project")
def delete_project():
    """Delete the project and manager from the session."""
    sid = session.get("sid")
    session.clear()
    if sid:
        try: os.remove(_store_path(sid))
        except FileNotFoundError: pass
    return "", 204


@app.post("/api/project/import")
def import_project():
    mgr = load_manager_or_400()

    if mgr.aspects:
        return {"error": "Import is only allowed when no aspects are defined."}, 409

    f = request.files.get("file")
    if not f:
        return {"error": "No file uploaded."}, 400

    try:
        wb = openpyxl.load_workbook(f.stream, data_only=True)
    except Exception:
        logger.exception("Failed to open uploaded workbook")
        return {"error": "Could not read the uploaded file. Is it a valid Excel file?"}, 400

    if not any(name.startswith(eudoxa.ASP) for name in wb.sheetnames):
        return {"error": "No aspect worksheets found in the file."}, 400

    try:
        result = mgr.validate_and_import_workbook(wb)
    except Exception:
        logger.exception("Unexpected error during import")
        return {"error": "An unexpected error occurred during import."}, 500

    if not result["success"]:
        return {"import_result": result}, 422

    # Persist project name from |PROJ| tab if provided
    if result.get("project_name"):
        session["project_name"] = result["project_name"]
    if result.get("author"):
        session["author"] = result["author"]

    save_manager(mgr)
    return {"import_result": result}, 200


@app.get("/aspects")
def aspects_html():
    """Render an HTML table of all aspects."""
    mgr = load_manager_or_400()
    aspects = mgr.aspects

    # Build rows for the HTML table
    table_rows = []
    for name, aspect in aspects.items():
        dtype = getattr(aspect.data_type, "__name__", str(aspect.data_type))
        n_levels = len(aspect.levels)
        n_vdiffs = len(aspect.vdiffs)
        table_rows.append({
            "name": name,
            "dtype": dtype,
            "description": aspect.description or "",
            "n_levels": n_levels,
            "vdiffs": n_vdiffs
        })

    return render_template("aspects.html", rows=table_rows)

@app.patch("/api/aspects/<aspect_name>")
def patch_aspect(aspect_name):
    mgr = load_manager_or_400()
    aspect = mgr.aspects.get(aspect_name)
    if not aspect:
        return {"error": f"Aspect '{aspect_name}' not found"}, 404

    data = request.get_json(silent=True) or {}
    if "description" in data:
        aspect.add_description(data["description"] or None)

    save_manager(mgr)
    return {"message": "Aspect updated"}, 200

@app.get("/api/aspect-names")
def get_aspect_names():
    mgr = load_manager_or_400()
    return {"aspects": list(mgr.aspects.keys())}, 200

@app.post("/api/aspects")
def add_aspect():
    mgr = load_manager_or_400()

    data = request.get_json()
    name = data["name"]
    data_type = data["data_type"]
    description = data.get("description")

    try:
        mgr.add_aspect(name, data_type, description)
    except Exception as e:
        return {"error": str(e)}, 400

    save_manager(mgr)
    return {"message": "Aspect added"}, 201


@app.get("/api/level-descriptions")
def get_level_descriptions():
    """Return all aspect level descriptions as a nested dict:
    { aspect_name: { level: description } }"""
    mgr = load_manager_or_400()
    result = {}
    for asp_name, aspect in mgr.aspects.items():
        result[asp_name] = {
            level: desc or ""
            for level, desc in aspect.levels.items()
        }
    return result, 200


@app.get("/api/aspects")
def list_aspects():
    """
    Return a table of all aspects as JSON:
    { "headers": [...], "rows": [...] }
    Columns: Name, Data type, Description, Levels, #Δ
    """
    mgr = load_manager_or_400()

    headers = ["Name", "Data type", "Description", "Levels", "#Δ"]

    rows = []
    for name, aspect in (mgr.aspects or {}).items():

        # Data type: convert Python type to str
        dtype = getattr(aspect.data_type, "__name__", str(aspect.data_type))

        # List level names
        level_names = ", ".join(aspect.levels.keys())

        # Number of value-differences
        n_vdiffs = len(aspect.vdiffs) if aspect.vdiffs else 0

        rows.append([
            name,
            dtype,
            "" if aspect.description is None else str(aspect.description),
            level_names,
            n_vdiffs
        ])

    return {"headers": headers, "rows": rows}, 200

# -----------------------------------------------------------
#  REST: LEVELS
# -----------------------------------------------------------
@app.get("/aspects/<aspect_name>")
def aspect_detail(aspect_name):
    mgr = load_manager_or_400()
    aspect = mgr.aspects.get(aspect_name)
    if not aspect:
        abort(404, f"Aspect '{aspect_name}' not found")

    dtype = getattr(aspect.data_type, "__name__", str(aspect.data_type))

    level_rows = []
    for level_name, description in aspect.levels.items():
        level_rows.append({
            "level": level_name,
            "description": "" if description is None else str(description)
        })

    return render_template(
        "aspect_detail.html",
        aspect_name=aspect_name,
        dtype=dtype,
        description=aspect.description or "",
        level_rows=level_rows
    )

@app.get("/aspects/<aspect_name>/levels")
def levels_html(aspect_name):
    mgr = load_manager_or_400()

    aspect = mgr.aspects.get(aspect_name)
    if not aspect:
        abort(404, f"Aspect '{aspect_name}' not found")

    rows = []
    for level_name, level_obj in aspect.levels.items():
        rows.append({
            "level": level_name,
            "description": "" if level_obj is None else str(level_obj)
        })

    return render_template(
        "levels.html",
        aspect_name=aspect_name,
        rows=rows
    )

@app.get("/api/aspects/<aspect_name>/levels")
def list_levels(aspect_name):
    mgr = load_manager_or_400()
    aspect = mgr.aspects.get(aspect_name)

    if not aspect:
        return {"error": f"Aspect '{aspect_name}' not found"}, 404

    levels = aspect.levels or {}

    rows = []
    for level_name, description in levels.items():
        rows.append([
            level_name,
            "" if description is None else str(description)
        ])

    return {
        "headers": ["Level", "Description"],
        "rows": rows
    }, 200

@app.post("/api/aspects/<aspect_name>/levels")
def add_level(aspect_name):
    mgr = load_manager_or_400()
    data = request.get_json()

    level = data["level"]
    description = data.get("description")

    try:
        mgr.add_aspect_level(aspect_name, level, description)
    except Exception as e:
        return {"error": str(e)}, 400

    save_manager(mgr)
    return {"message": "Level added"}, 201

@app.get("/api/aspects/<aspect_name>/relations")
def get_relations(aspect_name):
    mgr = load_manager_or_400()
    aspect = mgr.aspects.get(aspect_name)
    if not aspect:
        return {"error": f"Aspect '{aspect_name}' not found"}, 404

    levels = list(aspect.levels.keys())
    descriptions = {name: desc for name, desc in aspect.levels.items()}
    options = eudoxa.AL_RELATION_OPTIONS

    cells = {}
    for la in levels:
        for lb in levels:
            rel = mgr.get_aspect_level_relation(aspect_name, la, lb)
            cells[f"{la}|||{lb}"] = rel if rel is not NotImplemented else eudoxa.UNDEFINED

    return {"levels": levels, "descriptions": descriptions, "options": options, "cells": cells}, 200


@app.get("/api/aspects/<aspect_name>/level-graph")
def get_level_graph(aspect_name):
    """Return both the defined-relations graph and the closure graph
    as node/edge lists for client-side rendering."""
    mgr = load_manager_or_400()
    aspect = mgr.aspects.get(aspect_name)
    if not aspect:
        return {"error": f"Aspect '{aspect_name}' not found"}, 404
    try:
        def nxdg_to_json(nxdg):
            nodes = []
            for node_key in nxdg.nodes:
                attrs   = nxdg.nodes[node_key]
                lbl     = attrs.get('label', str(node_key))
                members = attrs.get('members', list(node_key))
                desc_parts = [
                    f"{m}: {aspect.levels[m]}" if aspect.levels.get(m) else m
                    for m in members
                ]
                nodes.append({
                    "id":      str(node_key),
                    "label":   lbl,
                    "title":   " | ".join(desc_parts),
                    "members": members
                })
            edges = [
                {"from": str(src), "to": str(dst)}
                for src, dst in nxdg.edges
            ]
            return {"nodes": nodes, "edges": edges}

        def build(use_closure, use_tr):
            return nxdg_to_json(
                mgr.create_aspect_level_relations_graph(
                    aspect_name, use_closure=use_closure, use_tr=use_tr
                )
            )

        return {
            "defined_tr":   build(use_closure=False, use_tr=True),
            "defined_full": build(use_closure=False, use_tr=False),
            "closure_tr":   build(use_closure=True,  use_tr=True),
            "closure_full": build(use_closure=True,  use_tr=False),
        }, 200
    except Exception:
        logger.exception("Failed to build level graph")
        return {"error": "Could not compute level graph."}, 500


@app.patch("/api/aspects/<aspect_name>/relations/<la>/<lb>")
def patch_relation(aspect_name, la, lb):
    mgr = load_manager_or_400()
    aspect = mgr.aspects.get(aspect_name)
    if not aspect:
        return {"error": f"Aspect '{aspect_name}' not found"}, 404

    data = request.get_json(silent=True) or {}
    rel = data.get("relation", eudoxa.UNDEFINED)
    if rel not in eudoxa.AL_RELATION_OPTIONS:
        return {"error": f"Invalid relation '{rel}'"}, 400

    def fmt_tokens(items):
        """Render a mixed list of VDiffs and relation strings as a single string."""
        return " ".join(repr(x) if hasattr(x, 'aspect_name') else (str(x) if x else '—') for x in items)

    RULE_LABELS = {
        'DiffP':      'Difference property',
        'NegDiffP':   'Negative difference property',
        'TransP':     'Transitivity property',
        'InvP':       'Inverse difference property',
        'TransP2':    'Transitivity property 2',
        'NegTransP':  'Negative transitivity property',
        'NegTransP2': 'Negative transitivity property 2',
        'NegInvP':    'Negative inverse difference property',
    }

    def fmt_origin(origin_type, origin_detail):
        """Translate an inference rule origin to natural language where known,
        falling back to the raw symbolic form for unrecognised patterns."""
        if origin_type == 'SETREL':
            # ['SETREL', [aspect, la, rel, lb]]
            aspect, la, rel, lb = origin_detail
            rel_label = rel if rel else '\u2014'
            return f"Set '{la} {rel_label} {lb}' in {aspect}"
        label = RULE_LABELS.get(origin_type)
        if label:
            return f"{label}: {fmt_tokens(origin_detail)}"
        # Fallback: raw symbolic form
        return f"{origin_type}({fmt_tokens(origin_detail)})"

    def fmt_result(add):
        """Render the result of an inference step as a symbolic vdiff relation."""
        return fmt_tokens(add)

    def fmt_add(entry):
        origin_type, origin_detail, add = entry
        return f"{fmt_origin(origin_type, origin_detail)} \u2192 {fmt_result(add)}"

    def fmt_coll(entry):
        origin_type, origin_detail, coll = entry
        # coll alternates: vd1, existing_rel, vd2, attempted_rel
        vd1, existing_rel, vd2, attempted_rel = coll
        return (
            f"{fmt_origin(origin_type, origin_detail)} \u2192 "
            f"attempted {repr(vd1)} {attempted_rel} {repr(vd2)} "
            f"conflicts with existing {repr(vd1)} {existing_rel} {repr(vd2)}"
        )

    try:
        adds, colls, inferred_adds = mgr.try_set_aspect_level_relation(aspect_name, la, lb, rel)
    except ValueError as e:
        return {"error": str(e)}, 404

    if colls:
        return {
            "message": "Relation rejected",
            "colls": [fmt_coll(e) for e in colls]
        }, 409

    save_manager(mgr)

    return {
        "message": "Relation updated",
        "adds":          [fmt_add(e) for e in adds],
        "inferred_adds": [fmt_add(e) for e in inferred_adds]
    }, 200


@app.patch("/api/aspects/<aspect_name>/levels/<level_name>")
def patch_level(aspect_name, level_name):
    mgr = load_manager_or_400()

    data = request.get_json(silent=True) or {}
    if "description" in data:
        try:
            mgr.set_level_description(aspect_name, level_name, data["description"] or None)
        except ValueError as e:
            return {"error": str(e)}, 404

    save_manager(mgr)
    return {"message": "Level updated"}, 200

# -----------------------------------------------------------
#  REST: CONSEQUENCES
# -----------------------------------------------------------
# -----------------------------------------------------------
#  REST: VDIFF COMPARISON MATRIX
# -----------------------------------------------------------
@app.get("/api/vdiff-matrix/<an1>/<an2>")
def get_vdiff_matrix(an1, an2):
    """Return the value-difference comparison sub-matrix for aspect pair (an1, an2).
    Response: { row_labels, col_labels,
                cells: [[{order_rel, raw_rel, diagonal}, ...], ...] }
    """
    mgr = load_manager_or_400()
    if an1 not in mgr.aspects:
        return {"error": f"Aspect '{an1}' not found"}, 404
    if an2 not in mgr.aspects:
        return {"error": f"Aspect '{an2}' not found"}, 404

    vdcm = mgr.vdiff_comparison_matrix

    def derive_order(raw_fwd, raw_bwd):
        T, F = eudoxa.TRUE, eudoxa.FALSE
        if raw_fwd == T and raw_bwd == F:  return eudoxa.GT
        if raw_fwd == T and raw_bwd == T:  return eudoxa.DEQ
        if raw_fwd == T:                   return eudoxa.GTE
        if raw_fwd == F and raw_bwd == T:  return eudoxa.LT
        if raw_bwd == T:                   return eudoxa.LTE
        if raw_fwd == F:                   return eudoxa.FALSE
        return eudoxa.UNDEFINED

    row_vdiffs = mgr._sorted_vdiffs(mgr.aspects[an1])
    col_vdiffs = mgr._sorted_vdiffs(mgr.aspects[an2])
    row_labels = [repr(v) for v in row_vdiffs]
    col_labels  = [repr(v) for v in col_vdiffs]

    cells = []
    for rv in row_vdiffs:
        row = []
        for cv in col_vdiffs:
            raw_fwd = eudoxa.get_vdiff_relation(vdcm, rv, cv)
            raw_bwd = eudoxa.get_vdiff_relation(vdcm, cv, rv)
            diag    = (an1 == an2 and rv == cv)
            row.append({
                "order_rel": derive_order(raw_fwd, raw_bwd),
                "raw_rel":   raw_fwd,
                "diagonal":  diag,
            })
        cells.append(row)

    return {"row_labels": row_labels, "col_labels": col_labels, "cells": cells}, 200


@app.get("/vdiff-matrix")
def vdiff_matrix_html():
    """Render the value-difference comparison matrix view."""
    mgr = load_manager_or_400()
    aspect_names = list(mgr.aspects.keys())
    return render_template("vdiff_matrix.html", aspect_names=aspect_names)


@app.get("/api/export-project")
def export_project():
    """Export the full project as a downloadable Excel workbook."""
    import io
    from flask import send_file
    mgr = load_manager_or_400()
    try:
        mgr.project_name = session.get("project_name", "")
        mgr.author       = session.get("author", "")
        wb  = mgr.export_project_to_workbook()
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        project_name = session.get("project_name", "project")
        filename = f"{project_name}.xlsx"
        return send_file(
            buf,
            mimetype="application/vnd.openxmlformats-officedocument"
                     ".spreadsheetml.sheet",
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        logger.exception("Failed to export project")
        return {"error": f"Export failed: {e}"}, 500


@app.get("/api/aspects/<aspect_name>/vdiff-classification")
def get_vdiff_classification(aspect_name):
    """Return VDiffs for the given aspect classified into three buckets.
    Query param: closure=1 to classify based on the VDCM closure (default: 0).
    Response: { "non_negative": [...], "negative": [...], "undecided": [...] }
    Each list contains VDiff label strings in canonical order.
    """
    mgr = load_manager_or_400()
    asp = mgr.aspects.get(aspect_name)
    if not asp:
        return {"error": f"Aspect '{aspect_name}' not found"}, 404

    use_closure = request.args.get("closure", "0") != "0"

    if use_closure:
        closure_vdcm, _, colls = mgr.closure()
        if colls:
            return {"error": "Closure computation produced collisions"}, 409
        vdcm = closure_vdcm
    else:
        vdcm = mgr.vdiff_comparison_matrix

    classified = eudoxa.classify_vdiffs(asp, vdcm)

    return {
        key: [repr(vd) for vd in vdiffs]
        for key, vdiffs in classified.items()
    }, 200


# ── VDIFF formatting helpers (shared by single and batch endpoints) ──────────

def _make_vd(asp, la, lb):
    return eudoxa.VDiff(asp, None, None) if (la == "*" and lb == "*") \
           else eudoxa.VDiff(asp, la, lb)


def _fmt_tokens(items):
    return " ".join(repr(x) if hasattr(x, 'aspect_name')
                     else (str(x) if x else "\u2014") for x in items)


def _fmt_entry(entry):
    origin_type, origin_detail, result_items = entry
    if origin_type == 'SETVDREL':
        vd1_r, rel, vd2_r = origin_detail
        rel_label = rel if rel else "\u2014"
        origin_str = f"Set {vd1_r} {rel_label} {vd2_r}"
    else:
        origin_str = f"{origin_type}({_fmt_tokens(origin_detail)})"
    return f"{origin_str} \u2192 {_fmt_tokens(result_items)}"


def _fmt_coll(entry):
    _, _, coll = entry  # entry is [origin_type, origin_detail, coll]
    vd1_c, old_rel, vd2_c, new_rel_c = coll
    return (f"{repr(vd1_c)} {new_rel_c or '\u2014'} {repr(vd2_c)} "
            f"conflicts with existing {repr(vd1_c)} {old_rel} {repr(vd2_c)}")


@app.patch("/api/vdiff-matrix/<an1>/<l1a>/<l1b>/<an2>/<l2a>/<l2b>")
def patch_vdiff_relation(an1, l1a, l1b, an2, l2a, l2b):
    """Set or unset the order relation between two vdiffs.
    Body: { "relation": one of ⊐ ⊒ ≜ ⊑ ⊏ or '' }
    """
    mgr  = load_manager_or_400()
    data = request.get_json(force=True)
    order_rel = data.get("relation", "")

    if order_rel not in (eudoxa.GT, eudoxa.GTE, eudoxa.DEQ,
                         eudoxa.LTE, eudoxa.LT, eudoxa.UNDEFINED):
        return {"error": f"Invalid relation: {order_rel!r}"}, 400

    for asp, la, lb in [(an1, l1a, l1b), (an2, l2a, l2b)]:
        if asp not in mgr.aspects:
            return {"error": f"Aspect '{asp}' not found"}, 404
        if la != "*" and la not in mgr.aspects[asp].levels:
            return {"error": f"Level '{la}' not found in aspect '{asp}'"}, 404
        if lb != "*" and lb not in mgr.aspects[asp].levels:
            return {"error": f"Level '{lb}' not found in aspect '{asp}'"}, 404

    vd1 = _make_vd(an1, l1a, l1b)
    vd2 = _make_vd(an2, l2a, l2b)

    try:
        adds, colls, inferred_adds = mgr.try_set_vdiff_order_relation(
            vd1, vd2, order_rel
        )
    except Exception as e:
        logger.exception("Failed to set vdiff relation")
        return {"error": str(e)}, 500

    if colls:
        return {"colls": [_fmt_coll(c) for c in colls]}, 409

    save_manager(mgr)
    return {
        "adds":          [_fmt_entry(a) for a in adds],
        "inferred_adds": [_fmt_entry(a) for a in inferred_adds]
    }, 200


@app.post("/api/vdiff-matrix/batch")
def batch_patch_vdiff_relations():
    """Apply a batch of vdiff order relation changes atomically.
    Body: { "changes": [{ "an1", "l1a", "l1b", "an2", "l2a", "l2b", "relation" }, ...] }
    Changes are applied sequentially; if any causes a collision the whole batch
    is aborted (manager is not saved) and 409 is returned with collision details.
    Response on success:  { "adds": [...], "inferred_adds": [...] }
    Response on collision: { "colls": [...] }, 409
    """
    mgr     = load_manager_or_400()
    data    = request.get_json(force=True)
    changes = data.get("changes", [])

    if not changes:
        return {"error": "No changes provided"}, 400

    valid_rels = (eudoxa.GT, eudoxa.GTE, eudoxa.DEQ,
                  eudoxa.LTE, eudoxa.LT, eudoxa.UNDEFINED)

    # ── Validate all changes before applying any ─────────────────────────────
    for ch in changes:
        if ch.get("relation", "") not in valid_rels:
            return {"error": f"Invalid relation: {ch.get('relation')!r}"}, 400
        for asp, la, lb in [(ch["an1"], ch["l1a"], ch["l1b"]),
                            (ch["an2"], ch["l2a"], ch["l2b"])]:
            if asp not in mgr.aspects:
                return {"error": f"Aspect '{asp}' not found"}, 404
            if la != "*" and la not in mgr.aspects[asp].levels:
                return {"error": f"Level '{la}' not found in aspect '{asp}'"}, 404
            if lb != "*" and lb not in mgr.aspects[asp].levels:
                return {"error": f"Level '{lb}' not found in aspect '{asp}'"}, 404

    # ── Apply changes sequentially; abort all on first collision ─────────────
    all_adds          = []
    all_inferred_adds = []

    for ch in changes:
        vd1 = _make_vd(ch["an1"], ch["l1a"], ch["l1b"])
        vd2 = _make_vd(ch["an2"], ch["l2a"], ch["l2b"])
        try:
            adds, colls, inferred_adds = mgr.try_set_vdiff_order_relation(
                vd1, vd2, ch["relation"]
            )
        except Exception as e:
            logger.exception("Failed to set vdiff relation in batch")
            return {"error": str(e)}, 500

        if colls:
            # Collision — abort entire batch (manager not saved)
            return {"colls": [_fmt_coll(c) for c in colls]}, 409

        all_adds.extend(adds)
        all_inferred_adds.extend(inferred_adds)

    save_manager(mgr)
    return {
        "adds":          [_fmt_entry(a) for a in all_adds],
        "inferred_adds": [_fmt_entry(a) for a in all_inferred_adds]
    }, 200


@app.get("/api/dominance-graph")
def get_dominance_graph():
    """Return confirmed and possible dominance edges, plus node completeness.
    Query param: tr=1 (default) applies transitive reduction to confirmed edges.
    Response: { nodes, edges_confirmed, edges_possible }
    """
    mgr = load_manager_or_400()
    if not mgr.consequences:
        return {"nodes": [], "edges_confirmed": [], "edges_possible": []}, 200
    try:
        from flask import request as freq
        use_tr = freq.args.get("tr", "1") != "0"
        graph  = mgr.create_dominance_graph(use_tr=use_tr)

        def make_tooltip(name, consequence):
            parts = [name] + [
                f"{asp_name}: {consequence[asp_name]}"
                for asp_name in mgr.aspects
            ]
            return " | ".join(parts)

        nodes = [
            {
                "id":       n["id"],
                "label":    f"{n['name']}: {n['id']}",
                "title":    make_tooltip(n["name"],
                                         mgr.consequences[n["name"]]),
                "complete": n["complete"],
                "name":     n["name"],
                "levels":   {
                    asp: str(mgr.consequences[n["name"]][asp])
                    for asp in mgr.aspects
                }
            }
            for n in graph["nodes"]
        ]
        edges_confirmed = [
            {"from": src, "to": dst}
            for src, dst in graph["edges_confirmed"]
        ]
        edges_possible = [
            {"from": src, "to": dst}
            for src, dst in graph["edges_possible"]
        ]
        return {
            "nodes":           nodes,
            "edges_confirmed": edges_confirmed,
            "edges_possible":  edges_possible
        }, 200
    except Exception as e:
        logger.exception("Failed to build dominance graph")
        import sys
        return {"error": f"Could not compute dominance graph: {e} | Python: {sys.executable} | Path: {sys.path}"}, 500


@app.get("/dominance-graph")
def dominance_graph_html():
    return render_template("dominance_graph.html")


@app.get("/consequences")
def consequences_html():
    """Render an HTML table of all consequences."""
    mgr = load_manager_or_400()

    aspects = list(mgr.aspects.values())
    consequences = mgr.consequences

    # Build column headers: one per aspect
    headers = [a.name for a in aspects]

    # Build rows: short name + one level value per aspect
    table_rows = []
    for short_name, consequence in consequences.items():
        levels = [consequence[a.name] or "" for a in aspects]
        table_rows.append({
            "short_name": short_name,
            "levels": levels
        })

    return render_template(
        "consequences.html",
        headers=headers,
        rows=table_rows
    )

@app.get("/api/consequences")
def get_consequences():
    # Returns named consequences as JSON:
    # { "headers": ["Short name", aspect1, ...], "rows": [[short_name, level1, ...], ...] }
    mgr = load_manager_or_400()

    aspects = list(mgr.aspects.values())
    headers = ["Short name"] + [a.name for a in aspects]

    rows = []
    for short_name, consequence in mgr.consequences.items():
        row = [short_name] + [
            "" if consequence[a.name] is None else str(consequence[a.name])
            for a in aspects
        ]
        rows.append(row)

    return {"headers": headers, "rows": rows}, 200
    
@app.get("/api/consequence_space")
def get_consequence_space():
    """
    Return the consequence space as JSON:
    { "headers": [...], "rows": [...] }
    One column per aspect, one row per consequence in the space.
    """
    mgr = load_manager_or_400()

    aspects = list(mgr.aspects.values())

    headers = [a.name for a in aspects]

    rows = []
    for consequence in mgr.consequence_space:
        row = [
            "" if consequence[a.name] is None else str(consequence[a.name])
            for a in aspects
        ]
        rows.append(row)

    return {"headers": headers, "rows": rows}, 200

@app.post("/api/consequences")
def add_consequence():
    mgr = load_manager_or_400()

    data = request.get_json()
    short = data["short_name"]
    levels = data["aspect_levels"]

    try:
        new_levels = mgr.add_consequence(short, levels)
    except Exception as e:
        return {"error": str(e)}, 400

    save_manager(mgr)
    return {"message": "Consequence added", "new_levels": new_levels}, 201


# -----------------------------------------------------------
#  TEST PANEL
# -----------------------------------------------------------
@app.get("/testpanel")
def testpanel():
    return render_template("testpanel.html")


# -----------------------------------------------------------
#  START SERVER
# -----------------------------------------------------------
if __name__ == "__main__":
    app.run(debug=True)