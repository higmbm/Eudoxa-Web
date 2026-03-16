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


# -----------------------------------------------------------
#  HELPERS
# -----------------------------------------------------------
def load_manager_or_400():
    """Load EudoxaManager from the session, or abort 400 if no active project."""
    serialized_mgr = session.get("manager")
    if not serialized_mgr:
        abort(400, description="No active project")
    try:
        return EudoxaManager.from_dict(serialized_mgr)
    except Exception:
        logger.exception("Failed to deserialize EudoxaManager from session")
        abort(400, description="Failed to load project data")


def save_manager(mgr: EudoxaManager):
    """Save the manager to the session."""
    session["manager"] = mgr.to_dict()


@app.after_request
def no_store_html(response):
    """Prevent HTML pages from being served from bfcache on back-navigation."""
    if response.content_type.startswith("text/html"):
        response.headers["Cache-Control"] = "no-store"
    return response


# -----------------------------------------------------------
#  UI
# -----------------------------------------------------------
@app.get("/")
def index():
    return render_template("index.html", project_name=session.get("project_name"))

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

    session["project_name"] = name
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

    return {"message": "Project renamed", "project_name": name}, 200

@app.get("/api/project")
def get_project():
    """Get the project name and serialized EudoxaManager."""
    name = session.get("project_name")
    serialized_mgr = session.get("manager")

    if not name or not serialized_mgr:
        return {"error": "No active project"}, 404

    return {
        "project_name": name,
        "manager": serialized_mgr
    }, 200


@app.delete("/api/project")
def delete_project():
    """Delete the project and manager from the session."""
    session.pop("project_name", None)
    session.pop("manager", None)
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

    prefix = "|ASP| "
    aspect_sheets = [name for name in wb.sheetnames if name.startswith(prefix)]

    if not aspect_sheets:
        return {"error": "No aspect worksheets found in the file."}, 400

    imported = []
    try:
        for sheet_name in aspect_sheets:
            ws = wb[sheet_name]
            rows = mgr.import_aspect_from_worksheet(ws)
            # rows[0] = ["Aspect:", name], rows[1] = ["Type:", ...], rows[2] = ["Description:", ...]
            # rows[3:] = [level, description] pairs
            aspect_name = rows[0][1]
            level_count = len(rows) - 3
            # Import level relations if present (column 5, row 2 is the first relation column header)
            has_relations = ws.cell(row=2, column=5).value is not None
            if has_relations:
                mgr.import_aspect_level_relations_from_worksheet(ws)
            imported.append({"name": aspect_name, "level_count": level_count, "has_relations": has_relations})
    except Exception:
        logger.exception("Failed to import aspects from workbook")
        return {"error": "An error occurred while importing aspects."}, 500

    save_manager(mgr)
    return {"imported": imported}, 200


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

    try:
        adds, colls = mgr.set_aspect_level_relation(aspect_name, la, lb, rel)
    except ValueError as e:
        return {"error": str(e)}, 404

    save_manager(mgr)

    def fmt_add(entry):
        origin_type, origin_detail, add = entry
        vd1, new_rel, vd2 = add
        return f"{repr(vd1)} {new_rel} {repr(vd2)}"

    def fmt_coll(entry):
        origin_type, origin_detail, coll = entry
        vd1, old_rel, vd2, new_rel = coll
        return f"{repr(vd1)} {new_rel} {repr(vd2)} collides with {repr(vd1)} {old_rel} {repr(vd2)}"

    return {
        "message": "Relation updated",
        "adds":  [fmt_add(e)  for e in adds],
        "colls": [fmt_coll(e) for e in colls]
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