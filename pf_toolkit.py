# -*- coding: utf-8 -*-
import nuke
import os
import importlib
import subprocess
import shutil
import stat

# --- VERSION DE LA SUITE PERFECT FRAME ---
SUITE_VERSION = "1.0.6"

NUKE_DIR = os.path.expanduser("~/.nuke").replace("\\", "/")
TOOLSETS_DIR = os.path.join(NUKE_DIR, "PF_ToolSets").replace("\\", "/")

def _find_git_repo():
    candidate = os.path.join(NUKE_DIR, "perfect-frame-nuke")
    if os.path.exists(os.path.join(candidate, ".git")):
        return candidate
    try:
        for item in os.listdir(NUKE_DIR):
            item_path = os.path.join(NUKE_DIR, item)
            if os.path.isdir(item_path) and os.path.exists(os.path.join(item_path, ".git")):
                return item_path
    except Exception:
        pass
    return candidate

def _paste_tcl_node(tcl_script):
    import tempfile
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".nk", mode="w")
    tmp.write(tcl_script)
    tmp.close()
    nuke.nodePaste(tmp.name)
    os.remove(tmp.name)

# ==============================================================================
# 1. RUTAS PERFECT FRAME (Relink Dinamico)
# ==============================================================================
def create_rutas_pf():
    node_name = "RUTAS_PERFECT_FRAME"
    existing = nuke.toNode(node_name)
    if existing:
        existing.setSelected(True)
        nuke.zoom(1.5, [existing.xpos(), existing.ypos()])
        existing.showControlPanel()
        nuke.message("El nodo RUTAS_PERFECT_FRAME ya existe en este script.")
        return existing

    ctrl = nuke.createNode("NoOp", inpanel=True)
    ctrl.setName(node_name)
    ctrl['tile_color'].setValue(0xff5500ff)
    ctrl['note_font_size'].setValue(18)
    ctrl['label'].setValue("RUTA ACTIVA (v" + SUITE_VERSION + "):\n[value base_path]")

    tab = nuke.Tab_Knob("path_ctrl_tab", "RUTAS PERFECT FRAME")
    ctrl.addKnob(tab)
    ctrl.addKnob(nuke.Text_Knob("info_artist", "RUTAS PERFECT FRAME v" + SUITE_VERSION, "Cambia esta carpeta para reconectar todo el proyecto a tu disco local:"))
    ctrl.addKnob(nuke.File_Knob("base_path", "Ruta Base del Proyecto"))

    reload_code = "import nuke\\ncount = 0\\nfor r in nuke.allNodes():\\n    if r.knob('reload') and r.Class() != 'Write':\\n        r.knob('reload').execute()\\n        count += 1\\nnuke.message('Se recargaron ' + str(count) + ' nodos correctamente.')"
    btn_reload = nuke.PyScript_Knob("btn_reload", "Recargar Todos los Reads (Reload)", reload_code)
    btn_reload.setFlag(nuke.STARTLINE)
    ctrl.addKnob(btn_reload)

    ctrl.addKnob(nuke.Text_Knob("div1", "Configuracion Inicial (Vincular)", ""))
    ctrl.addKnob(nuke.File_Knob("old_prefix", "Raiz Actual a Reemplazar"))
    inc_extra = nuke.Boolean_Knob("include_extra", "Incluir Geo, Camaras y LUTs (OCIO/Vectorfield)", True)
    inc_extra.setFlag(nuke.STARTLINE)
    ctrl.addKnob(inc_extra)

    detect_code = "import nuke, os\\nn = nuke.thisNode()\\npaths = list()\\nfor r in nuke.allNodes('Read'):\\n    val = r.knob('file').getEvaluatedValue()\\n    if val:\\n        paths.append(val.replace(chr(92), '/'))\\nif not paths:\\n    nuke.message('No se encontraron nodos Read con rutas.')\\nelse:\\n    common = os.path.commonprefix(paths)\\n    if '/' in common:\\n        common = os.path.dirname(common).rstrip('/') + '/'\\n    n.knob('old_prefix').setValue(common)\\n    if not n.knob('base_path').getValue():\\n        n.knob('base_path').setValue(common)"
    btn_detect = nuke.PyScript_Knob("btn_detect", "1. Auto-detectar Raiz Comun", detect_code)
    btn_detect.setFlag(nuke.STARTLINE)
    ctrl.addKnob(btn_detect)

    link_code = "import nuke\\nn = nuke.thisNode()\\nold_p = n.knob('old_prefix').getValue().replace(chr(92), '/').rstrip('/')\\nbase_p = n.knob('base_path').getValue().replace(chr(92), '/').rstrip('/')\\nif not old_p:\\n    nuke.message('Define primero la Raiz Actual a Reemplazar.')\\nelse:\\n    if not base_p:\\n        base_p = old_p\\n    n.knob('base_path').setValue(base_p + '/')\\n    tc = ('Read', 'DeepRead', 'ReadGeo', 'ReadGeo2', 'Camera', 'Camera2', 'Camera3', 'Axis2', 'Vectorfield', 'OCIOFileTransform', 'AudioRead') if n.knob('include_extra').getValue() else ('Read', 'DeepRead')\\n    count = 0\\n    for node in nuke.allNodes():\\n        if node.Class() in tc and node.knob('file'):\\n            raw_p = node.knob('file').getValue().replace(chr(92), '/')\\n            eval_p = node.knob('file').getEvaluatedValue().replace(chr(92), '/')\\n            tp = raw_p if raw_p.startswith(old_p) else (eval_p if eval_p.startswith(old_p) else None)\\n            if tp:\\n                rel_p = tp.replace(old_p, '', 1).lstrip('/')\\n                expr = chr(91) + 'value ' + n.name() + '.base_path' + chr(93) + rel_p\\n                node.knob('file').setValue(expr)\\n                count += 1\\n    nuke.message('Se vincularon ' + str(count) + ' nodos al controlador ' + n.name() + '.')"
    ctrl.addKnob(nuke.PyScript_Knob("btn_link", "2. Vincular Nodos al Controlador", link_code))

    ctrl.addKnob(nuke.Text_Knob("div2", "Entrega / Desvinculacion", ""))
    bake_code = "import nuke\\nn = nuke.thisNode()\\ntoken = chr(91) + 'value ' + n.name() + '.base_path' + chr(93)\\ncount = 0\\nfor node in nuke.allNodes():\\n    if node.knob('file') and node.Class() != 'Write':\\n        val = node.knob('file').getValue()\\n        if token in val:\\n            baked = node.knob('file').getEvaluatedValue().replace(chr(92), '/')\\n            node.knob('file').setValue(baked)\\n            count += 1\\nnuke.message('Se hornearon ' + str(count) + ' nodos a rutas fijas.')"
    btn_bake = nuke.PyScript_Knob("btn_bake", "Hornear Rutas (Convertir a Texto Fijo)", bake_code)
    btn_bake.setFlag(nuke.STARTLINE)
    ctrl.addKnob(btn