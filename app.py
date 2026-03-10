import os
from flask import Flask, session, request, jsonify, abort
from flask import render_template
from eudoxa import EudoxaManager

app = Flask(__name__)

# -----------------------------------------------------------
#  SESSION / CONFIG
# -----------------------------------------------------------
app.secret_key = os.getenv("SECRET_KEY") or "dev-secret-change-me"


# -----------------------------------------------------------
#  HELPERS
# -----------------------------------------------------------
def load_manager_or_400():
    """Load EudoxaManager from the session, or return 400 if no active project."""
    serialized_mgr = session.get("manager")
    if not serialized_mgr:
        abort(400, description="No active project")
    return EudoxaManager.from_dict(serialized_mgr)


def save_manager(mgr: EudoxaManager):
    """Save the manager to the session."""
    session["manager"] = mgr.to_dict()


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


# -----------------------------------------------------------
#  REST: ASPECTS
# -----------------------------------------------------------
@app.get("/aspects")
def aspects_html():
    """Render an HTML table of all aspects."""
    try:
        mgr = load_manager_or_400()
    except:
        mgr = None
    
    aspects = mgr.aspects if mgr else {}

    # Build rows for the HTML table
    table_rows = []
    for name, aspect in aspects.items():
        dtype = getattr(aspect.data_type, "__name__", str(aspect.data_type))
        level_names = ", ".join(str(lvl) for lvl in aspect.levels.keys())
        n_vdiffs = len(aspect.vdiffs)
        table_rows.append({
            "name": name,
            "dtype": dtype,
            "description": aspect.description or "",
            "levels": level_names,
            "vdiffs": n_vdiffs
        })

    return render_template("aspects.html", rows=table_rows)

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
            "description": getattr(level_obj, "description", "")
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

# -----------------------------------------------------------
#  REST: CONSEQUENCES
# -----------------------------------------------------------
@app.get("/consequences")
def consequences_html():
    """Render an HTML table of all consequences."""
    try:
        mgr = load_manager_or_400()
    except:
        mgr = None

    aspects = list(mgr.aspects.values()) if mgr else []
    consequences = mgr.consequences if mgr else {}

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
    mgr = load_manager_or_400()

    aspects = getattr(mgr, "aspects", []) or []
    consequences = getattr(mgr, "consequences", []) or []

    def dtype(a):
        return getattr(a, "type", None) or getattr(a, "data_type", "")

    headers = ["Consequence"] + [f"{a.name} ({dtype(a)})" for a in aspects]

    rows = []
    for cons in consequences:
        short = getattr(cons, "short_name", "") or getattr(cons, "short", "") or ""
        aspect_levels = getattr(cons, "aspect_levels", {}) or {}
        row = [short]
        for a in aspects:
            level = aspect_levels.get(a.name, "")
            row.append("" if level is None else str(level))
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
        mgr.add_consequence(short, levels)
    except Exception as e:
        return {"error": str(e)}, 400

    save_manager(mgr)
    return {"message": "Consequence added"}, 201


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