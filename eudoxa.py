from typing import Dict, List, Tuple, Type

import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

console_handler = logging.StreamHandler()
file_handler = logging.FileHandler('eudoxa.log', 'w', 'utf-8')

console_handler.setLevel(logging.DEBUG)
file_handler.setLevel(logging.DEBUG)

formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)
file_handler.setFormatter(formatter)

logger.addHandler(console_handler)
logger.addHandler(file_handler)


ASP = "|ASP| "
CONS = "|CONS|"
DOM = "|DOM|"
VDCM = "|VDCM|"

TRUE = "⊒"
FALSE = "⋣"
UNDEFINED = ""

BT = "≻"
BTE = "⪰"
EQ = "∼"
WTE = "⪯"
WT = "≺"

AL_RELATION_OPTIONS = [UNDEFINED, BT, BTE, EQ, WTE, WT]

DELTA = "Δ"
ZDIFF_TUPLE = ('*', '*')
ZDIFF_STR = str(ZDIFF_TUPLE)

GT = "⊐"
GTE = "⊒"
DEQ = "≜"
LTE = "⊑"
LT = "⊏"

VDIFF_RELATION_OPTIONS = [UNDEFINED, GT, GTE, DEQ, LTE, LT]

class Aspect:
    def __init__(self, name: str, data_type: Type, description: str = None):
        self.name = name
        self.data_type = data_type
        self.description = description
        self.levels: Dict[str, str] = {}
        self.vdiffs: List[VDiff] = [VDiff(name, None, None)]
        
    def add_level(self, level: str, description: str):
        logger.info(f"Adding level '{level}' to aspect '{self.name}'")
        try:
            parse_type(level, self.data_type)
        except (ValueError, TypeError) as e:
            raise ValueError(
                f"Level '{level}' is not valid for aspect '{self.name}' "
                f"with data_type '{self.data_type.__name__}': {e}"
            )
        for l_key in self.levels.keys():
            vd = VDiff(self.name, l_key, level)
            self.vdiffs.append(vd)
            vd_inv = VDiff(self.name, level, l_key)
            self.vdiffs.append(vd_inv)
        self.levels[level] = description

    def add_description(self, description: str):
        self.description = description

    def set_level_description(self, level: str, description: str):
        if level not in self.levels:
            raise ValueError(f"Level '{level}' does not exist in aspect '{self.name}'.")
        self.levels[level] = description

    def __repr__(self):
        return (f"Aspect(name='{self.name}', data_type='{self.data_type.__name__}', "
                f"description='{self.description}', levels={list(self.levels.keys())})")
    
    def to_dict(self):
        return {
            "name": self.name,
            "data_type": self.data_type.__name__,
            "description": self.description,
            "levels": self.levels,  # dict[str, str]
            "vdiffs": [
                {
                    "from_level": vd.from_level,
                    "to_level": vd.to_level
                }
                for vd in self.vdiffs
            ]
        }

    @classmethod
    def from_dict(cls, data):
        asp = cls(
            name=data["name"],
            data_type=str_to_type(data["data_type"]),
            description=data.get("description")
        )
    
        # Restore levels
        asp.levels = dict(data.get("levels", {}))
    
        # Restore vdiffs (replaces default)
        asp.vdiffs = [
            VDiff(
                aspect_name=data["name"],
                from_level=vd["from_level"],
                to_level=vd["to_level"]
            )
            for vd in data.get("vdiffs", [])
        ]
    
        return asp

class Consequence:
    def __init__(self, aspect_levels=None):
        self.aspect_levels: Dict[str, str] = aspect_levels if aspect_levels is not None else {}

    def __eq__(self, other):
        if not isinstance(other, Consequence):
            return NotImplemented
        return self.aspect_levels == other.aspect_levels

    def __getitem__(self, aspect_name: str) -> str:
        return self.aspect_levels.get(aspect_name, None)
    
    def __setitem__(self, aspect_name: str, level: str):
        self.aspect_levels[aspect_name] = level
    
    def __repr__(self):
        return "⟨" + ", ".join(f"{v}" for v in self.aspect_levels.values()) + "⟩"
    
    def to_dict(self):
        """Serialize Consequence to a plain dict."""
        return {
            "aspect_levels": self.aspect_levels
        }
    
    @classmethod
    def from_dict(cls, data):
        """Create a Consequence object from a dict with key 'aspect_levels'."""
        # Guard against None or missing key — fall back to empty dict
        aspect_levels = data.get("aspect_levels", {}) if isinstance(data, dict) else {}
        # Ensure all values are str or None
        cleaned = {}
        for k, v in aspect_levels.items():
            cleaned[str(k)] = None if v is None else str(v)
        return cls(cleaned)

class VDiff:
    
    def __init__(self, aspect_name: str, from_level: str, to_level: str):
        self.aspect_name = aspect_name
        self.from_level = from_level
        self.to_level = to_level
        
    def __eq__(self, other):
        if not isinstance(other, VDiff):
            return NotImplemented
        return (self.aspect_name == other.aspect_name and
                self.from_level == other.from_level and
                self.to_level == other.to_level)
    
    def __ne__(self, other):
        return not self.__eq__(other)
    
    def inv(self):
        return VDiff(self.aspect_name, self.to_level, self.from_level)

    def equals(self, other):
        if self.natural_zero() and other.natural_zero():
            return True
        return (self == other)

    def natural_zero(self):
        return self.from_level == self.to_level

    def __repr__(self):
        from_level = self.from_level if self.from_level is not None else '*'
        to_level = self.to_level if self.to_level is not None else '*'
        return f"Δ({from_level},{to_level})"
    
def str_to_vdiff(aspect_name: str, vdiff_str: str) -> VDiff:
    levels = eval(vdiff_str[1:])
    if levels[0] == '*' and levels[1] == '*':
        return VDiff(aspect_name, None, None)
    return VDiff(aspect_name, levels[0], levels[1])

def str_to_type(data_type_str: str) -> Type:
    if data_type_str == 'int':
        return int
    elif data_type_str == 'float':
        return float
    return str

def parse_type(data_str: str, data_type: Type):
    if data_type == str:
        return str(data_str)
    elif data_type == int:
        return int(data_str)
    elif data_type == float:
        return float(data_str)
    return str(data_str)

def get_vdiff_relation(vdcm, vd1: VDiff, vd2: VDiff) -> str:
    an1 = vd1.aspect_name
    an2 = vd2.aspect_name
    vdc12 = vdcm[(an1, an2)]
    d1 = (vd1.from_level, vd1.to_level)
    if vd1.natural_zero():
        d1 = ZDIFF_TUPLE
    d2 = (vd2.from_level, vd2.to_level)
    if vd2.natural_zero():
        d2 = ZDIFF_TUPLE
    return vdc12[(d1, d2)]

def set_vdiff_relation(vdcm, vd1: VDiff, vd2: VDiff, new_rel: str) -> Tuple:
    an1 = vd1.aspect_name
    an2 = vd2.aspect_name
    vdc12 = vdcm[(an1, an2)]
    d1 = (vd1.from_level, vd1.to_level)
    if vd1.natural_zero():
        d1 = ZDIFF_TUPLE
    d2 = (vd2.from_level, vd2.to_level)
    if vd2.natural_zero():
        d2 = ZDIFF_TUPLE
    old_rel = vdc12[(d1, d2)]
    add, coll = None, None
    if new_rel == old_rel:      # Same relation — no change
        pass
    elif new_rel == UNDEFINED:  # Unset (clear) relation
        add = [an1, d1, an2, d2, new_rel]
        vdc12[(d1, d2)] = new_rel
    elif old_rel == UNDEFINED:  # Set new relation
        add = [vd1, new_rel, vd2]
        vdc12[(d1, d2)] = new_rel
    else:                       # Collision: TRUE >> FALSE or FALSE >> TRUE
        coll = [vd1, old_rel, vd2, new_rel]
    return (add, coll)

def pos(vd: VDiff, aspect: Aspect, vdcm) -> bool:
    an = aspect.name
    for vd2 in aspect.vdiffs:
        if vd2.natural_zero():
            d = (str(vd.from_level), str(vd.to_level))
            z = ZDIFF_TUPLE
            rel_dz = vdcm[(an, an)][(d, z)]
            rel_zd = vdcm[(an, an)][(z, d)]
            if (rel_dz == TRUE and rel_zd == FALSE):
                return True
    return False

def non_neg(vd: VDiff, aspect: Aspect, vdcm) -> bool:
    an = aspect.name
    for vd2 in aspect.vdiffs:
        if vd2.natural_zero():
            d = (str(vd.from_level), str(vd.to_level))
            z = ZDIFF_TUPLE
            rel_dz = vdcm[(an, an)][(d, z)]
            if (rel_dz == TRUE):
                return True
    return False

def zero(vd: VDiff, aspect: Aspect, vdcm) -> bool:
    if vd.natural_zero():
        return True
    an = aspect.name
    for vd2 in aspect.vdiffs:
        if vd2.natural_zero():
            d = (str(vd.from_level), str(vd.to_level))
            z = ZDIFF_TUPLE
            rel_dz = vdcm[(an, an)][(d, z)]
            rel_zd = vdcm[(an, an)][(z, d)]
            if (rel_dz == TRUE and rel_zd == TRUE):
                return True
    return False

def non_pos(vd: VDiff, aspect: Aspect, vdcm) -> bool:
    an = aspect.name
    for vd2 in aspect.vdiffs:
        if vd2.natural_zero():
            d = (str(vd.from_level), str(vd.to_level))
            z = ZDIFF_TUPLE
            rel_zd = vdcm[(an, an)][(z, d)]
            if (rel_zd == TRUE):
                return True
    return False

def neg(vd: VDiff, aspect: Aspect, vdcm) -> bool:
    an = aspect.name
    for vd2 in aspect.vdiffs:
        if vd2.natural_zero():
            d = (str(vd.from_level), str(vd.to_level))
            z = ZDIFF_TUPLE
            rel_dz = vdcm[(an, an)][(d, z)]
            rel_zd = vdcm[(an, an)][(z, d)]
            if (rel_dz == FALSE and rel_zd == TRUE):
                return True
    return False


def app_ac(origin: List, ac: Tuple, adds: List, colls: List) -> Tuple:
    (add, coll) = ac
    if add:
        adds.append([origin[0], origin[1], add])
    if coll:
        colls.append([origin[0], origin[1], coll])
    return (adds, colls)

from itertools import product

import openpyxl

class EudoxaManager:
    
    def __init__(self):
        logger.info('Initializing EudoxaManager')
        self.aspects: Dict[str, Aspect] = {}
        self.consequence_space: List[Consequence] = [Consequence()]
        self.consequences : Dict[str, Consequence]  = {}
        self.vdiff_comparison_matrix: Dict[Tuple[str, str], Dict[Tuple[Tuple[str, str], Tuple[str, str]], str]] = {}

    def has_aspect(self, aspect_name: str) -> bool:
        return aspect_name in self.aspects

    def add_aspect(self, name: str, data_type_str: str, description = None) -> Aspect:
        logger.info(f"Adding aspect '{name}'")
        if name in self.aspects:
            raise ValueError(f"Aspect '{name}' already exists.")
        self.vdiff_comparison_matrix[(name, name)] = {}
        for a_name in self.aspects.keys():
            self.vdiff_comparison_matrix[(a_name, name)] = {}
            self.vdiff_comparison_matrix[(name, a_name)] = {}
        data_type = str_to_type(data_type_str)
        self.aspects[name] = Aspect(name, data_type, description)
        # Add a None entry for this aspect in every existing consequence
        for consequence in self.consequence_space:
            consequence.__setitem__(name, None)
        for (_, consequence) in self.consequences.items():
            consequence.__setitem__(name, None)
        return self.aspects[name]

    def get_aspect(self, name: str) -> Aspect:
        return self.aspects[name]

    def create_aspect_level_relations_graph(self, aspect_name: str):
        import networkx as nx
        nxdg = nx.DiGraph()
        aspect = self.get_aspect(aspect_name)
        # TODO: Equivalence classes
        for al in aspect.levels:
            nxdg.add_node(al)
        for al1 in aspect.levels:
            for al2 in aspect.levels:
                rel = self.get_aspect_level_relation(aspect_name, al1, al2)
                if rel in [BT, BTE]:
                    nxdg.add_edge(al1,al2)
        return nx.transitive_reduction(nxdg)

    def show_aspect_level_relations_graph(self, aspect_name, nxdg):
        import networkx as nx
        import matplotlib as mpl
        import matplotlib.pyplot as plt
        for layer, nodes in enumerate(nx.topological_generations(nxdg)):
            for node in nodes:
                nxdg.nodes[node]["layer"] = layer
        pos = nx.multipartite_layout(nxdg, subset_key="layer", align="horizontal")
        fig, ax = plt.subplots()
        nx.draw_networkx(nxdg, pos=pos, ax=ax, node_size = 800)
        ax.set_title("Aspect level relations graph for " + aspect_name)
        plt.show()
        
    def add_consequence(self, short_name: str, aspect_levels: Dict[str,str]) -> List:
        added_aspect_levels = []
        if short_name in self.consequences:
            raise ValueError(f"A consequence named '{short_name}' already exists.")

        if not aspect_levels.keys() == self.aspects.keys():
            raise ValueError("Aspect keys do not match.")

        # Normalise to strings for comparison (mirrors what is stored)
        normalised = {k: str(v) for k, v in aspect_levels.items()}
        for existing_name, existing_cons in self.consequences.items():
            if all(existing_cons[a] == normalised[a] for a in self.aspects):
                raise ValueError(
                    f"Consequence '{short_name}' is identical to "
                    f"existing consequence '{existing_name}'."
                )

        c = Consequence(aspect_levels)
        logger.debug(f"Adding '{short_name}' to consequence set.")
        for aspect_name, level in aspect_levels.items():
            aspect = self.get_aspect(aspect_name)
            level_str = str(level)
            if level_str not in aspect.levels:
                self.add_aspect_level(aspect_name, level_str, None)
                added_aspect_levels.append(aspect_name + ":" + level_str)
            c.__setitem__(aspect_name, level_str)

        self.consequences[short_name] = c
        return added_aspect_levels

    def remove_consequence(self, short_name: str):
        if short_name in self.consequences:
            del self.consequences[short_name]

    def dom(self, ca: Consequence, cb: Consequence) -> bool:
        # TODO: Error handling
        n_bt = 0
        n_bte = 0
        for an in self.aspects:
            la = ca.__getitem__(an)
            lb = cb.__getitem__(an)
            rel = self.get_aspect_level_relation(an, la, lb)
            if rel == WT:
                return False
            if rel == WTE:
                pass
            elif rel == EQ:
                n_bte += 1
            elif rel == BTE:
                n_bte += 1
            elif rel == BT:
                n_bt += 1
            else: # Undefined
                return NotImplemented
        if n_bt + n_bte == len(self.aspects) and n_bt>0:
            return True
        return None

    def show_dominance_graph(self, nxdg, html_file: str):
        import networkx as nx
        import matplotlib as mpl
        import matplotlib.pyplot as plt
        for layer, nodes in enumerate(nx.topological_generations(nxdg)):
            for node in nodes:
                nxdg.nodes[node]["layer"] = layer
        pos = nx.multipartite_layout(nxdg, subset_key="layer", align="horizontal")
        fig, ax = plt.subplots()
        nx.draw_networkx(nxdg, pos=pos, ax=ax, node_size = 4000)
        ax.set_title("Consequence dominance graph")
        plt.show()

    def create_dominance_graph(self):
        import networkx as nx        
        nxdg = nx.DiGraph()
        for c in self.consequences.values():
            nxdg.add_node(str(c))
        for ca in self.consequences.values():
            for cb in self.consequences.values():
                dom_tf = self.dom(ca, cb)
                if dom_tf:
                    nxdg.add_edge(str(ca), str(cb))
        return nx.transitive_reduction(nxdg)

    def create_dominance_table(self) -> Dict[Tuple[str, str], bool]:
        dom_table = {}
        for ca in self.consequences.values():
            for cb in self.consequences.values():
                dom_tf = self.dom(ca, cb)
                if dom_tf:
                    cacb = (str(ca), str(cb))
                    dom_table[cacb] = dom_tf
        return dom_table

    def export_dominance_table_to_excel(self,
                                        dom_table: Dict[Tuple[str, str], bool],
                                        filename: str):
        import openpyxl
        title = DOM
        try:
            wb = openpyxl.load_workbook(filename)
        except: # Create new workbook if file does not exist
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = title
        try:
            ws = wb[title]
        except: # Create new sheet if it does not exist
            ws = wb.create_sheet(title=title)
        self.export_dominance_table_to_worksheet(dom_table, ws)
        wb.save(filename)
        
    def export_dominance_table_to_worksheet(self, dom_table: Dict[Tuple[str, str], bool], ws):
        # Row 1: headers
        ws["A1"] = 'From Type'
        ws["B1"] = 'From Name'
        ws["C1"] = 'Edge Type'
        ws["D1"] = 'To Type'
        ws["E1"] = 'To Name'
        row_index = 2
        for ((c1, c2), v) in dom_table.items():
            ws.cell(row=row_index, column=1).value='Consequence'
            ws.cell(row=row_index, column=2).value=c1
            ws.cell(row=row_index, column=3).value='DOM'
            ws.cell(row=row_index, column=4).value='Consequence'
            ws.cell(row=row_index, column=5).value=c2
            row_index += 1

    def set_level_description(self, aspect_name: str, level_name: str, description: str):
        logger.debug(f"Setting description for level '{level_name}' in aspect '{aspect_name}'.")
        if aspect_name not in self.aspects:
            raise ValueError(f"Aspect '{aspect_name}' does not exist.")
        self.aspects[aspect_name].set_level_description(level_name, description)

    def add_aspect_level(self, aspect_name: str, level, description: str):
        logger.debug(f"Adding level '{level}' to aspect '{aspect_name}'.")
        if aspect_name not in self.aspects:
            raise ValueError(f"Aspect '{aspect_name}' does not exist.")
        aspect = self.get_aspect(aspect_name)
        level_str = str(level)
        # If the level already exists, do nothing
        if level_str in aspect.levels:
            return
        # Add the new level
        aspect.add_level(level_str, description)
        # Update the value-difference comparison matrix
        self.expand_vdiff_comparison_matrix(aspect_name)
        # Update the consequence space
        self.expand_consequence_space(aspect_name, level_str, description)

    def set_aspect_level_relation(self, aspect: str, la, lb, rel: str) -> Tuple:
        adds, colls = [], []
        a = self.get_aspect(aspect)
        a_type = a.data_type
        la_str, lb_str = str(la), str(lb)
        if a is None:
            raise ValueError(f"Aspect '{aspect}' does not exist.")
        if not la_str in a.levels:
            raise ValueError(f"Aspect level '{la}' [{a_type}] does not exist.")
        if not lb_str in a.levels:
            raise ValueError(f"Aspect level '{lb}' [{a_type}] does not exist.")
        zero = VDiff(aspect, None, None)
        vd_ab = VDiff(aspect, la_str, lb_str)
        vd_ba = VDiff(aspect, lb_str, la_str)

        origin = ['SETAL', [aspect, la_str, rel, lb_str]]
        if rel == UNDEFINED:
            app_ac(origin, self.set_vdiff_relation(vd_ab, zero, UNDEFINED), adds, colls)
            app_ac(origin, self.set_vdiff_relation(vd_ba, zero, UNDEFINED), adds, colls)
            app_ac(origin, self.set_vdiff_relation(zero, vd_ab, UNDEFINED), adds, colls)
            app_ac(origin, self.set_vdiff_relation(zero, vd_ba, UNDEFINED), adds, colls)
        elif rel == BT:
            app_ac(origin, self.set_vdiff_relation(vd_ab, zero, TRUE), adds, colls)
            app_ac(origin, self.set_vdiff_relation(vd_ba, zero, FALSE), adds, colls)
            app_ac(origin, self.set_vdiff_relation(zero, vd_ab, FALSE), adds, colls)
            app_ac(origin, self.set_vdiff_relation(zero, vd_ba, TRUE), adds, colls)
        elif rel == BTE:
            app_ac(origin, self.set_vdiff_relation(vd_ab, zero, TRUE), adds, colls)
            app_ac(origin, self.set_vdiff_relation(zero, vd_ba, TRUE), adds, colls)
        elif rel == EQ:
            app_ac(origin, self.set_vdiff_relation(vd_ab, zero, TRUE), adds, colls)
            app_ac(origin, self.set_vdiff_relation(vd_ba, zero, TRUE), adds, colls)
            app_ac(origin, self.set_vdiff_relation(zero, vd_ab, TRUE), adds, colls)
            app_ac(origin, self.set_vdiff_relation(zero, vd_ba, TRUE), adds, colls)
        elif rel == WTE:
            app_ac(origin, self.set_vdiff_relation(vd_ba, zero, TRUE), adds, colls)
            app_ac(origin, self.set_vdiff_relation(zero, vd_ab, TRUE), adds, colls)
        elif rel == WT:
            app_ac(origin, self.set_vdiff_relation(vd_ba, zero, TRUE), adds, colls)
            app_ac(origin, self.set_vdiff_relation(vd_ab, zero, FALSE), adds, colls)
            app_ac(origin, self.set_vdiff_relation(zero, vd_ba, FALSE), adds, colls)
            app_ac(origin, self.set_vdiff_relation(zero, vd_ab, TRUE), adds, colls)
        return (adds, colls)

    def get_aspect_level_relation(self, aspect: str, la, lb) -> str:
        a = self.get_aspect(aspect)
        a_type = a.data_type
        la_str, lb_str = str(la), str(lb)
        if a is None:
            raise ValueError(f"Aspect '{aspect}' does not exist.")
        if not la_str in a.levels:
            raise ValueError(f"Aspect level '{la}' [{a_type}] does not exist.")
        if not lb_str in a.levels:
            raise ValueError(f"Aspect level '{lb}' [{a_type}] does not exist.")
        zero = VDiff(aspect, None, None)
        vd_ab = VDiff(aspect, la_str, lb_str)
        rel_ab_z = self.get_vdiff_relation(vd_ab, zero)
        rel_z_ab = self.get_vdiff_relation(zero, vd_ab)
        if rel_ab_z == TRUE and rel_z_ab == FALSE:
            return BT
        elif rel_ab_z == TRUE and rel_z_ab == UNDEFINED:
            return BTE
        elif rel_ab_z == TRUE and rel_z_ab == TRUE:
            return EQ
        elif rel_ab_z == UNDEFINED and rel_z_ab == TRUE:
            return WTE
        elif rel_ab_z == FALSE and rel_z_ab == TRUE:
            return WT
        elif rel_ab_z == UNDEFINED and rel_z_ab == UNDEFINED:
            return UNDEFINED
        else:
            return NotImplemented

    def get_vdiff_relation(self, vd1: VDiff, vd2: VDiff) -> str:
        return get_vdiff_relation(self.vdiff_comparison_matrix, vd1, vd2)
    
    def set_vdiff_relation(self, vd1: VDiff, vd2: VDiff, new_rel: str) -> Tuple:
        return set_vdiff_relation(self.vdiff_comparison_matrix, vd1, vd2, new_rel)

    def set_rel(self, a1: str, l1a, l1b, a2, l2a, l2b, rel: str) -> Tuple:
        adds, colls = [], []
        a1_ab = VDiff(a1, l1a, l1b)
        a1_ba = VDiff(a1, l1b, l1a)
        a2_ab = VDiff(a2, l2a, l2b)
        a2_ba = VDiff(a2, l2b, l2a)
        origin = ['SETREL', [a1_ab, rel, a2_ab]]
        if rel == GT:
            app_ac(origin, self.set_vdiff_relation(a1_ab, a2_ab, TRUE), adds, colls)
            app_ac(origin, self.set_vdiff_relation(a2_ab, a1_ab, FALSE), adds, colls)
        elif rel == GTE:
            app_ac(origin, self.set_vdiff_relation(a1_ab, a2_ab, TRUE), adds, colls)
        elif rel == DEQ:
            app_ac(origin, self.set_vdiff_relation(a1_ab, a2_ab, TRUE), adds, colls)
            app_ac(origin, self.set_vdiff_relation(a2_ab, a1_ab, TRUE), adds, colls)
            app_ac(origin, self.set_vdiff_relation(a1_ba, a2_ba, TRUE), adds, colls)
            app_ac(origin, self.set_vdiff_relation(a2_ba, a1_ba, TRUE), adds, colls)
        elif rel == LTE:
            app_ac(origin, self.set_vdiff_relation(a2_ab, a1_ab, TRUE), adds, colls)
        elif rel == LT:
            app_ac(origin, self.set_vdiff_relation(a2_ab, a1_ab, TRUE), adds, colls)
            app_ac(origin, self.set_vdiff_relation(a1_ab, a2_ab, FALSE), adds, colls)
        return (adds, colls)

    def pos(self, an: str, la, lb) -> bool:
        # TODO: Error handling
        return pos(VDiff(an, la, lb), self.aspects[an], self.vdiff_comparison_matrix)

    def non_neg(self, an: str, la, lb) -> bool:
        # TODO: Error handling
        return non_neg(VDiff(an, la, lb), self.aspects[an], self.vdiff_comparison_matrix)

    def zero(self, an: str, la, lb) -> bool:
        # TODO: Error handling
        return zero(VDiff(an, la, lb), self.aspects[an], self.vdiff_comparison_matrix)

    def non_pos(self, an: str, la, lb) -> bool:
        # TODO: Error handling
        return non_pos(VDiff(an, la, lb), self.aspects[an], self.vdiff_comparison_matrix)

    def neg(self, an: str, la, lb) -> bool:
        # TODO: Error handling
        return neg(VDiff(an, la, lb), self.aspects[an], self.vdiff_comparison_matrix)
    
    def vd_enum_verbose(self):
        for a in self.aspects.values():
            for l_from in a.levels:
                for l_to in a.levels:
                    yield VDiff(a.name, l_from, l_to)

    def vd_enum_brief(self):
        for a in self.aspects.values():
            for vd in a.vdiffs:
                yield vd

    def vdc_enum(self):
        for an1 in self.aspects:
            for an2 in self.aspects:
                vdcm12 = self.vdiff_comparison_matrix[(an1, an2)]
                for (d1, d2), rel in vdcm12.items():
                    yield (an1, d1, an2, d2, rel)

    def closure(self):
        # Dict[Tuple[str, str], Dict[Tuple[Tuple[str, str], Tuple[str, str]], str]]
        closure = {}
        adds, colls = [], []
        # Initialize
        for asp1 in self.aspects:
            for asp2 in self.aspects:
                closure[(asp1, asp2)] = {}
        for (asp1, d_str1, asp2, d_str2, rel) in self.vdc_enum():
            closure[(asp1, asp2)][(d_str1, d_str2)] = rel
        # Compute closure
        for vd in self.vd_enum_verbose():
            for ab in self.vd_enum_verbose():
                an1 = ab.aspect_name
                for cd in self.vd_enum_verbose():
                    an2 = cd.aspect_name
                    for ef in self.vd_enum_verbose():
                        an3 = ef.aspect_name
                        rel_cd_ef = get_vdiff_relation(closure, cd, ef)
                        if (an2 == an3): # Same aspect? Check difference property
                            if rel_cd_ef == TRUE: # cdRef => ceRdf
                                c, d = cd.from_level, cd.to_level
                                e, f = ef.from_level, ef.to_level
                                ce = VDiff(an2, c, e)
                                df = VDiff(an2, d, f)
                                origin = ['DiffP', [cd, rel_cd_ef, ef]]
                                app_ac(origin, set_vdiff_relation(closure, ce, df, TRUE), adds, colls)
                            elif rel_cd_ef == FALSE: # cdSef => fdSec
                                c, d = cd.from_level, cd.to_level
                                e, f = ef.from_level, ef.to_level
                                fd = VDiff(an2, f, d)
                                ec = VDiff(an2, e, c)
                                origin = ['NegDiffP', [fd, rel_cd_ef, ec]]
                                app_ac(origin, set_vdiff_relation(closure, fd, ec, FALSE), adds, colls)
                        if colls: # A collision has occurred — abort
                            return (closure, adds, colls)                            
                        rel_ab_cd = get_vdiff_relation(closure, ab, cd)
                        if rel_ab_cd == TRUE: # abRcd
                            rel_cd_ef = get_vdiff_relation(closure, cd, ef)
                            if rel_cd_ef == TRUE: # abRcd & cdRef ==> abRef
                                origin = ['TransP', [ab, rel_ab_cd, cd, rel_cd_ef, ef]]
                                app_ac(origin, set_vdiff_relation(closure, ab, ef, TRUE), adds, colls)
                                if ef.natural_zero(): # abRcd & cdRxx ==> dcRba
                                    ba = ab.inv()
                                    dc = cd.inv()
                                    origin = ['InvP', [ab, rel_ab_cd, cd, rel_cd_ef, ef]]
                                    app_ac(origin, set_vdiff_relation(closure, dc, ba, TRUE), adds, colls)                            
                            elif rel_cd_ef == FALSE: # abRcd & cdSef
                                rel_cd_ab = get_vdiff_relation(closure, cd, ab)
                                if (rel_cd_ab == TRUE): # ab DEQ cdSef ==> abSef 
                                    origin = ['TransP2', [ab, DEQ, cd, FALSE, ef]]
                                    app_ac(origin, set_vdiff_relation(closure, ab, ef, FALSE), adds, colls)
                        elif rel_ab_cd == FALSE:
                            rel_cd_ef = get_vdiff_relation(closure, cd, ef)
                            if rel_cd_ef == TRUE: # abScd & cdRef
                                rel_ef_cd = get_vdiff_relation(closure, ef, cd)
                                if rel_ef_cd == TRUE: # abScd & cd DEQ ef
                                    origin = ['NegTransP2', [ab, FALSE, cd, DEQ, ef]]
                                    app_ac(origin, set_vdiff_relation(closure, ab, ef, FALSE), adds, colls)
                            elif rel_cd_ef == FALSE: # abScd & cdSef
                                origin = ['NegTransP', ab, rel_ab_cd, cd, rel_cd_ef, ef]
                                app_ac(origin, set_vdiff_relation(closure, ab, ef, FALSE), adds, colls)
                                if ab.natural_zero(): # xxScd & cdRef ==> feRdc
                                    dc = cd.inv()
                                    fe = ef.inv()
                                    origin = ['NegInvP', [ab, rel_ab_cd, cd, rel_cd_ef, ef]]
                                    app_ac(origin, set_vdiff_relation(closure, fe, dc, FALSE), adds, colls)                            
                                if ef.natural_zero(): # abScd & cdSxx ==> dcSba
                                    ba = ab.inv()
                                    dc = cd.inv()
                                    origin = ['NegInvP', [ab, rel_ab_cd, cd, rel_cd_ef, ef]]
                                    app_ac(origin, set_vdiff_relation(closure, dc, ba, FALSE), adds, colls)
                                if ab.natural_zero() and ef.natural_zero(): # xxScd & cdSxx
                                    fe = ef.inv()
                                    origin = ['NegInvP', [ab, rel_ab_cd, cd, rel_cd_ef, ef]]
                                    app_ac(origin, set_vdiff_relation(closure, fe, dc, FALSE), adds, colls)                            
                        if colls: # A collision has occurred — abort
                            return (closure, adds, colls)
        return (closure, adds, colls)

    def expand_vdiff_comparison_matrix(self, an2: str):
        for (an1, a1) in self.aspects.items():
            vdcm12 = self.vdiff_comparison_matrix[(an1, an2)]
            vdcm21 = self.vdiff_comparison_matrix[(an2, an1)]
            for vd1 in a1.vdiffs:
                for vd2 in self.aspects[an2].vdiffs:
                    d1 = (vd1.from_level, vd1.to_level)
                    if vd1.natural_zero():
                        d1 = ZDIFF_TUPLE
                    d2 = (vd2.from_level, vd2.to_level)
                    if vd2.natural_zero():
                        d2 = ZDIFF_TUPLE
                    rel = UNDEFINED
                    if (d1 == d2):
                        if (an1 == an2): # Same aspect?
                            rel = TRUE                            
                        elif vd1.natural_zero() and vd2.natural_zero(): # Both zero?
                            rel = TRUE
                    if not (d1, d2) in vdcm12:
                        logger.debug(f"Initialising ({d1[0]},{d1[1]})?({d2[0]},{d2[1]}): {rel}")
                        vdcm12[(d1, d2)] = rel
                    if not (d2, d1) in vdcm21:
                        logger.debug(f"Initialising ({d2[0]},{d2[1]})?({d1[0]},{d1[1]}): {rel}")
                        vdcm21[(d2, d1)] = rel
    
    def expand_consequence_space(self, aspect_name: str, level_str: str, description: str):
        aspect = self.get_aspect(aspect_name)
        # If this is the only level for the aspect, assign it to all existing consequences
        if len(aspect.levels) == 1:
            for consequence in self.consequence_space:
                consequence.__setitem__(aspect_name, level_str)
        else:
            # Collect levels from all other aspects
            other_aspects = [a for a in self.aspects.values() if a.name != aspect_name]
            other_levels = []
            for a in other_aspects:
                if not a.levels:
                    other_levels.append([(a.name, None)])
                else:
                    other_levels.append([(a.name, level) for level in a.levels.keys()])
            # Create new consequences for each combination
            for combo in product(*other_levels):
                aspect_levels = {name: lvl for name, lvl in combo}
                aspect_levels[aspect_name] = level_str
                c = Consequence(aspect_levels)
                self.consequence_space.append(c)

    def export_aspect_to_excel(self, aspect_name: str, filename: str) -> int:
        import openpyxl
        title = ASP + aspect_name
        try:
            wb = openpyxl.load_workbook(filename)
        except: # Create new workbook if file does not exist
            wb = openpyxl.Workbook()
            ws_a = wb.active
            ws_a.title = title
        try:
            ws_a = wb[title]
        except: # Create new sheet if it does not exist
            ws_a = wb.create_sheet(title=title)
        aspect = self.aspects[aspect_name]
        n_levels = self.export_aspect_to_worksheet(aspect, ws_a)
        wb.save(filename)
        return n_levels

    def export_aspect_level_relations_to_excel(self, aspect_name: str, filename: str):
        import openpyxl
        title = ASP + aspect_name
        try:
            wb = openpyxl.load_workbook(filename)
        except: # Create new workbook if file does not exist
            wb = openpyxl.Workbook()
            ws_a = wb.active
            ws_a.title = title
        try:
            ws_a = wb[title]
        except: # Create new sheet if it does not exist
            ws_a = wb.create_sheet(title=title)
        aspect = self.aspects[aspect_name]
        self.export_aspect_level_relations_to_worksheet(aspect, ws_a)
        wb.save(filename)

    def export_consequences_to_excel(self, filename: str):
        import openpyxl
        try:
            wb = openpyxl.load_workbook(filename)
        except: # Create new workbook if file does not exist
            wb = openpyxl.Workbook()
            ws_c = wb.active
            ws_c.title = CONS
        try:
            ws_c = wb[CONS]
        except: # Create new sheet if it does not exist
            ws_c = wb.create_sheet(title=CONS)
        self.export_consequences_to_worksheet(ws_c)
        wb.save(filename)

    def export_aspect_to_worksheet(self, aspect, ws) -> int:
        start_row = 3
        # Row 1: aspect name and data type
        ws["A1"] = aspect.name
        ws["B1"] = aspect.data_type.__name__

        # Row 2: aspect description
        ws["A2"] = aspect.description

        # From row 3: levels (name and description)
        # TODO: Handle data types
        row_index = start_row
        for level_str, description in aspect.levels.items():
            level = parse_type(level_str, aspect.data_type)
            ws.cell(row=row_index, column=1).value=level
            ws.cell(row=row_index, column=2).value=description
            row_index += 1
        return row_index-start_row

    def export_aspect_level_relations_to_worksheet(self, aspect, ws):
        # Clear all non-empty cells from column 5 onwards
        max_row = ws.max_row
        max_col = ws.max_column
        for col in range(5, max_col + 1):
            for row in range(1, max_row + 1):
                ws.cell(row=row, column=col).value=None
        # Row 2: column headers
        col_index = 5
        for level_str in aspect.levels:
            level = parse_type(level_str, aspect.data_type)
            ws.cell(row=2, column=col_index).value=level
            col_index += 1
      
        # From row 3: row headers and values
        row_index = 3
        for ls_row in aspect.levels:
            l_row = parse_type(ls_row, aspect.data_type)
            ws.cell(row=row_index, column=4).value=l_row
            col_index = 5
            for ls_col in aspect.levels:
                rel = self.get_aspect_level_relation(aspect.name, ls_row, ls_col)
                rel = None if rel == UNDEFINED else rel
                logger.debug(f"Exporting {ls_row} {rel} {ls_col} in '{aspect.name}'")
                ws.cell(row=row_index, column=col_index).value=rel
                col_index +=1
            row_index += 1

    def export_vdiff_comparison_matrix_to_worksheet(self, vdcm, ws):
        ws.cell(row=3, column=3).value="Δ\Δ"
        # Rows 2-3: column headers
        col_index = 4
        for an in self.aspects:
            ws.cell(row=2, column=col_index).value=an
            aspect = self.aspects[an]
            for vd in aspect.vdiffs:
                if vd.natural_zero():
                    col_header = ZDIFF_STR
                else:
                    col_header = "(" + str(vd.from_level) + "," + str(vd.to_level) + ")"
                ws.cell(row=3, column=col_index).value=col_header
                col_index += 1
        # Row 4+: row headers and values
        row_index = 4
        for an in self.aspects:
            col_index = 2
            ws.cell(row=row_index, column=col_index).value=an
            aspect = self.aspects[an]
            for vd in aspect.vdiffs:
                col_index = 3
                row_header = "(" + str(vd.from_level) + "," + str(vd.to_level) + ")"
                ws.cell(row=row_index, column=col_index).value=row_header
                row_index += 1
        
    def export_vdiff_comparison_matrix_to_excel(self, filename: str):
        import openpyxl
        title = VDCM
        try:
            wb = openpyxl.load_workbook(filename)
        except: # Create new workbook if file does not exist
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = title
        try:
            ws = wb[title]
        except: # Create new sheet if it does not exist
            ws = wb.create_sheet(title=title)
        self.export_vdiff_comparison_matrix_to_worksheet(self.vdiff_comparison_matrix, ws)
        wb.save(filename)
                
    def export_consequences_to_worksheet(self, ws):
        # Row 1: headers, Row 2: data types
        for col_index, aspect_name in enumerate(self.aspects.keys(), start=2):
            ws.cell(row=1, column=col_index).value=aspect_name
            aspect_type = self.aspects[aspect_name].data_type
            ws.cell(row=2, column=col_index).value=aspect_type.__name__

        # Consequences (from row 3)
        for row_index, (short_name, consequence) in enumerate(self.consequences.items(), start=3):
            ws.cell(row=row_index, column=1).value=short_name
            for col_index, aspect_name in enumerate(self.aspects.keys(), start=2):
                aspect_type = self.aspects[aspect_name].data_type
                level = parse_type(consequence[aspect_name], aspect_type)
                ws.cell(row=row_index, column=col_index).value=level

    def import_aspect_from_excel(self, aspect_name: str, filename: str):
        import openpyxl
        wb = openpyxl.load_workbook(filename, data_only=True)
        ws = wb[ASP + aspect_name]
        return self.import_aspect_from_worksheet(ws)

    def import_aspect_level_relations_from_excel(self, aspect_name: str, filename: str):
        import openpyxl
        wb = openpyxl.load_workbook(filename, data_only=True)
        ws = wb[ASP + aspect_name]
        return self.import_aspect_level_relations_from_worksheet(ws)

    def import_consequences_from_excel(self, filename: str):
        import openpyxl
        wb = openpyxl.load_workbook(filename, data_only=True)
        ws = wb[CONS]
        self.import_consequences_from_worksheet(ws)

    def import_aspect_from_worksheet(self, ws) -> List:
        aspect_name = ws["A1"].value
        data_type_str = ws["B1"].value
        description = ws["A2"].value
        logger.info(f"Importing aspect '{aspect_name}'")
        # Create aspect and add levels
        self.add_aspect(aspect_name, data_type_str, description)
        rows = [["Aspect:", aspect_name], ["Type:", data_type_str], ["Description:", description]]
        # Read levels from row 3 onwards
        for row in ws.iter_rows(min_row=3, values_only=True):
            level = row[0]
            if level is None:
                break
            description = row[1] if len(row) > 1 else None
            self.add_aspect_level(aspect_name, level, description)
            rows.append([level, description])
        return rows

    def import_aspect_level_relations_from_worksheet(self, ws) -> Tuple:
        aspect_name = ws["A1"].value
        aspect = self.get_aspect(aspect_name)
        col_heads = []
        for col in ws.iter_cols(min_col=5, values_only=True):
            key_c = col[1]
            col_heads.append(key_c)
        adds, colls = [], []
        for row in ws.iter_rows(min_row=3, values_only=True):
            key_r = row[3]
            col_index = 4
            for key_c in col_heads:
                rel = row[col_index] if row[col_index] else UNDEFINED
                (a, c) = self.set_aspect_level_relation(aspect_name, key_r, key_c, rel)
                adds += a
                colls += c
                col_index += 1
        logger.debug(str(adds) + " " + str(colls))
        return (adds, colls)
    
    def import_consequences_from_worksheet(self, ws):
        aspect_names = []
        for col_index in range(2, ws.max_column + 1):
            aspect_name = ws.cell(row=1, column=col_index).value
            aspect_type_str = ws.cell(row=2, column=col_index).value
            if not aspect_name:
                break
            else:
                if not self.has_aspect(aspect_name):
                    aspect_type_str = aspect_type_str if aspect_type_str else "str"
                    added_aspect = self.add_aspect(aspect_name, aspect_type_str, None)
                    logger.debug(str(added_aspect))
                aspect_names.append(aspect_name)
        for row in ws.iter_rows(min_row=3, values_only=True):
            short_name = row[0]
            if not short_name:
                break
            aspect_levels = {}
            for col_index, aspect_name in enumerate(aspect_names, start=1):
                level_str = str(row[col_index])
                aspect_levels[aspect_name] = level_str
            self.add_consequence(short_name, aspect_levels)

    def vdiff_comparison_matrix_str(self, vdcm):
        result = ""
        for a1_name in self.aspects.keys():
            a1 = self.get_aspect(a1_name)
            for a2_name in self.aspects.keys():
                a1a2 = vdcm[(a1_name, a2_name)]
                result += a1_name + "|" + a2_name + "[" + str(len(a1a2)) + "]:\n"
                a2 = self.get_aspect(a2_name)
                for ((d1, d2), rel) in a1a2.items():
                    result += "   " + DELTA + str(d1) + " " + GTE + " " + DELTA + str(d2) + " " + str(rel) + "\n"
        return result

    def __repr__(self):
        result = "Aspects:\n"
        for aspect in self.aspects.values():
            result += "- " + str(aspect) + "\n"
        result += "\nConsequence space:\n"
        for consequence in self.consequence_space:
            result += " - " + str(consequence) + "\n"

        result += "\nConsequences:\n"
        for (short_name, c) in self.consequences.items():
            result += " - " + short_name + ":" + str(c) + "\n"
        result += "\nValue-difference relations:\n"
        result += self.vdiff_comparison_matrix_str(self.vdiff_comparison_matrix)
        return result

    def to_dict(self):
        """Full JSON-serialization of the entire EudoxaManager."""
        # Serialize vdiff_comparison_matrix with string keys
        vdcm_out = {}
        for (a1, a2), relation_map in self.vdiff_comparison_matrix.items():
            key = f"{a1}|||{a2}"
            vdcm_out[key] = {}
            for (d1, d2), rel in relation_map.items():
                d1s = f"{d1[0]}::{d1[1]}"
                d2s = f"{d2[0]}::{d2[1]}"
                pair_key = f"{d1s}>>{d2s}"
                vdcm_out[key][pair_key] = rel
    
        return {
            "__schema__": 1,
            "aspects": { 
                name: aspect.to_dict()
                for name, aspect in self.aspects.items()
            },
            "consequences": {
                short: c.to_dict()
                for short, c in self.consequences.items()
            },
            "consequence_space": [
                c.to_dict() for c in self.consequence_space
            ],
            "vdiff_comparison_matrix": vdcm_out
        }

    @classmethod
    def from_dict(cls, data):
        mgr = cls()
    
        # Clear auto-generated initial values
        mgr.aspects = {}
        mgr.consequences = {}
        mgr.consequence_space = []
        mgr.vdiff_comparison_matrix = {}
    
        # ---- Aspects ----
        for name, asp_data in data.get("aspects", {}).items():
            mgr.aspects[name] = Aspect.from_dict(asp_data)
    
        # ---- Consequences ----
        for short, cons_data in data.get("consequences", {}).items():
            mgr.consequences[short] = Consequence.from_dict(cons_data)
    
        # ---- Consequence space ----
        cs_list = data.get("consequence_space", [])
        for cdata in cs_list:
            mgr.consequence_space.append(Consequence.from_dict(cdata))
    
        # ---- VDiff comparison matrix ----
        vdcm_in = data.get("vdiff_comparison_matrix", {})
        for key, relation_map in vdcm_in.items():
            a1, a2 = key.split("|||")
            mgr.vdiff_comparison_matrix[(a1, a2)] = {}
    
            for pair_key, rel in relation_map.items():
                d1s, d2s = pair_key.split(">>")
                f1, t1 = d1s.split("::")
                f2, t2 = d2s.split("::")
    
                # None is represented as '' in VDiff
                f1 = None if f1 == "" else f1
                t1 = None if t1 == "" else t1
                f2 = None if f2 == "" else f2
                t2 = None if t2 == "" else t2
    
                mgr.vdiff_comparison_matrix[(a1, a2)][((f1, t1), (f2, t2))] = rel
    
        return mgr