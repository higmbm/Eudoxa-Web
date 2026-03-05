import os
from flask import Flask, session, request, jsonify, abort
from flask import render_template
from eudoxa import EudoxaManager

app = Flask(__name__)

# -----------------------------------------------------------
#  SESSION / CONFIG
# -----------------------------------------------------------
# Viktigt: hemlighet för att kunna använda Flask-sessioner
app.secret_key = os.getenv("SECRET_KEY") or "dev-secret-change-me"


# -----------------------------------------------------------
#  HJÄLPFUNKTIONER
# -----------------------------------------------------------
def load_manager_or_400():
    """Läs EudoxaManager från sessionen eller returnera 400."""
    serialized_mgr = session.get("manager")
    if not serialized_mgr:
        abort(400, description="No active project")
    return EudoxaManager.from_dict(serialized_mgr)


def save_manager(mgr: EudoxaManager):
    """Spara manager i sessionen."""
    session["manager"] = mgr.to_dict()


# -----------------------------------------------------------
#  UI – valfritt (används om du vill köra index.html)
# -----------------------------------------------------------
@app.get("/")
def index():
    return render_template("index.html", project_name=session.get("project_name"))

# -----------------------------------------------------------
#  REST: PROJECT
# -----------------------------------------------------------

@app.post("/api/project")
def create_project():
    """Skapa nytt projekt (endast om inget projekt redan finns)."""
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
    """Byt namn på ett befintligt projekt."""
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
    """Hämta projektets namn + serialiserad EudoxaManager."""
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
    """Radera projekt + manager ur sessionen."""
    session.pop("project_name", None)
    session.pop("manager", None)
    return "", 204


# -----------------------------------------------------------
#  REST: ASPECTS
# -----------------------------------------------------------
@app.get("/aspects")
def aspects_html():
    """Renderar en HTML-tabell med alla aspekter."""
    mgr = load_manager_or_400()

    aspects = mgr.aspects or {}

    # Bygg rader åt HTML-tabellen
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
    Returnerar en tabell över alla aspekter som JSON:
    { "headers": [...], "rows": [[...], ...] }
    Kolumner: Namn, Datatyp, Beskrivning, Nivåer, #Δ
    """
    # 1) Läs manager från session (400 om inget projekt)
    mgr = load_manager_or_400()

    # 2) Förbered kolumnrubriker
    headers = ["Namn", "Datatyp", "Beskrivning", "Nivåer", "#Δ"]

    # 3) Iterera över alla aspekter i dict[str, Aspect]
    rows = []
    for name, aspect in (mgr.aspects or {}).items():
        # Datatypnamn (hanterar både typer och ev. str)
        dtype = getattr(aspect.data_type, "__name__", str(aspect.data_type))
        # Lista nivånamn (kommaseparerade)
        level_names = ", ".join(str(lvl) for lvl in aspect.levels.keys())
        # Antal VDiff (kan inkludera "naturliga nollor")
        n_vdiffs = len(aspect.vdiffs) if getattr(aspect, "vdiffs", None) is not None else 0

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

    # Hämta aspekt
    aspect = mgr.aspects.get(aspect_name)
    if not aspect:
        abort(404, f"Aspekt '{aspect_name}' finns inte")

    # Bygg tabellrader (anpassa efter hur ditt Level-objekt ser ut)
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
    for level_name, level_obj in levels.items():
        rows.append([
            level_name,
            "" if level_obj.description is None else str(level_obj.description)
        ])

    return {
        "headers": ["Nivå", "Beskrivning"],
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
@app.get("/api/consequences")
def get_consequences():
    # 1) Läs manager från session (400 om inget projekt)
    mgr = load_manager_or_400()

    # 2) Hämta aspekter och konsekvenser
    aspects = getattr(mgr, "aspects", []) or []
    consequences = getattr(mgr, "consequences", []) or []

    # 3) Kolumnrubriker: "Konsekvens" + en kolumn per aspekt
    #    OBS: Byt aspect.type -> aspect.data_type om din Aspect-klass använder det namnet
    def dtype(a):
        return getattr(a, "type", None) or getattr(a, "data_type", "")

    headers = ["Konsekvens"] + [f"{a.name} ({dtype(a)})" for a in aspects]

    # 4) Rader: short_name + nivå per aspekt
    rows = []
    for cons in consequences:
        short = getattr(cons, "short_name", "") or getattr(cons, "short", "") or ""
        # cons.aspect_levels antas vara en dict: { aspect_name: level }
        aspect_levels = getattr(cons, "aspect_levels", {}) or {}
        row = [short]
        for a in aspects:
            level = aspect_levels.get(a.name, "")
            # säkerställ sträng (om nivåer kan vara andra typer)
            row.append("" if level is None else str(level))
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
#  TESTPANEL
# -----------------------------------------------------------
@app.get("/testpanel")
def testpanel():
    return render_template("testpanel.html")


# -----------------------------------------------------------
#  STARTA SERVERN
# -----------------------------------------------------------
if __name__ == "__main__":
    app.run(debug=True)