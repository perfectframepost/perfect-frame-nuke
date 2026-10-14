# -*- coding: utf-8 -*-
import nuke
import os
import importlib
import subprocess
import shutil
import stat
import tempfile

# --- VERSION DE LA SUITE PERFECT FRAME ---
SUITE_VERSION = "1.0.7"

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
    for n in nuke.selectedNodes():
        n.setSelected(False)
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".nk", mode="w", encoding="utf-8")
    tmp.write(tcl_script)
    tmp.close()
    nuke.nodePaste(tmp.name)
    os.remove(tmp.name)


# ==============================================================================
# 1. RUTAS PERFECT FRAME (Relink Dinamico + Funciones Auxiliares)
# ==============================================================================
def rutas_reload_all():
    count = 0
    for r in nuke.allNodes():
        if r.knob("reload") and r.Class() != "Write":
            r.knob("reload").execute()
            count += 1
    nuke.message("Se recargaron " + str(count) + " nodos correctamente.")


def rutas_detect_prefix(n):
    paths = []
    for r in nuke.allNodes("Read"):
        val = r.knob("file").getEvaluatedValue()
        if val:
            paths.append(val.replace("\\", "/"))
    if not paths:
        nuke.message("No se encontraron nodos Read con rutas.")
        return
    common = os.path.commonprefix(paths)
    if "/" in common:
        common = os.path.dirname(common).rstrip("/") + "/"
    n.knob("old_prefix").setValue(common)
    if not n.knob("base_path").getValue():
        n.knob("base_path").setValue(common)


def rutas_link_nodes(n):
    old_p = n.knob("old_prefix").getValue().replace("\\", "/").rstrip("/")
    base_p = n.knob("base_path").getValue().replace("\\", "/").rstrip("/")
    if not old_p:
        nuke.message("Define primero la Raiz Actual a Reemplazar.")
        return
    if not base_p:
        base_p = old_p
    n.knob("base_path").setValue(base_p + "/")

    if n.knob("include_extra").getValue():
        tc = (
            "Read", "DeepRead", "ReadGeo", "ReadGeo2",
            "Camera", "Camera2", "Camera3", "Axis2",
            "Vectorfield", "OCIOFileTransform", "AudioRead"
        )
    else:
        tc = ("Read", "DeepRead")

    count = 0
    for node in nuke.allNodes():
        if node.Class() in tc and node.knob("file"):
            raw_p = node.knob("file").getValue().replace("\\", "/")
            eval_p = node.knob("file").getEvaluatedValue().replace("\\", "/")
            tp = raw_p if raw_p.startswith(old_p) else (eval_p if eval_p.startswith(old_p) else None)
            if tp:
                rel_p = tp.replace(old_p, "", 1).lstrip("/")
                expr = "[value " + n.name() + ".base_path]" + rel_p
                node.knob("file").setValue(expr)
                count += 1
    nuke.message("Se vincularon " + str(count) + " nodos al controlador " + n.name() + ".")


def rutas_bake_nodes(n):
    token = "[value " + n.name() + ".base_path]"
    count = 0
    for node in nuke.allNodes():
        if node.knob("file") and node.Class() != "Write":
            val = node.knob("file").getValue()
            if token in val:
                baked = node.knob("file").getEvaluatedValue().replace("\\", "/")
                node.knob("file").setValue(baked)
                count += 1
    nuke.message("Se hornearon " + str(count) + " nodos a rutas fijas.")


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
    ctrl["tile_color"].setValue(0xff5500ff)
    ctrl["note_font_size"].setValue(18)
    ctrl["label"].setValue("RUTA ACTIVA (v" + SUITE_VERSION + "):\n[value base_path]")

    tab = nuke.Tab_Knob("path_ctrl_tab", "RUTAS PERFECT FRAME")
    ctrl.addKnob(tab)
    ctrl.addKnob(nuke.Text_Knob(
        "info_artist",
        "Perfect Frame v" + SUITE_VERSION,
        "Cambia esta carpeta para reconectar todo el proyecto a tu disco local:"
    ))
    ctrl.addKnob(nuke.File_Knob("base_path", "Ruta Base del Proyecto"))

    btn_reload = nuke.PyScript_Knob(
        "btn_reload",
        "Recargar Todos los Reads (Reload)",
        "import pf_toolkit; pf_toolkit.rutas_reload_all()"
    )
    btn_reload.setFlag(nuke.STARTLINE)
    ctrl.addKnob(btn_reload)

    ctrl.addKnob(nuke.Text_Knob("div1", "Configuracion Inicial (Vincular)", ""))
    ctrl.addKnob(nuke.File_Knob("old_prefix", "Raiz Actual a Reemplazar"))
    inc_extra = nuke.Boolean_Knob("include_extra", "Incluir Geo, Camaras y LUTs (OCIO/Vectorfield)", True)
    inc_extra.setFlag(nuke.STARTLINE)
    ctrl.addKnob(inc_extra)

    btn_detect = nuke.PyScript_Knob(
        "btn_detect",
        "1. Auto-detectar Raiz Comun",
        "import pf_toolkit; pf_toolkit.rutas_detect_prefix(nuke.thisNode())"
    )
    btn_detect.setFlag(nuke.STARTLINE)
    ctrl.addKnob(btn_detect)

    btn_link = nuke.PyScript_Knob(
        "btn_link",
        "2. Vincular Nodos al Controlador",
        "import pf_toolkit; pf_toolkit.rutas_link_nodes(nuke.thisNode())"
    )
    ctrl.addKnob(btn_link)

    ctrl.addKnob(nuke.Text_Knob("div2", "Entrega / Desvinculacion", ""))
    btn_bake = nuke.PyScript_Knob(
        "btn_bake",
        "Hornear Rutas (Convertir a Texto Fijo)",
        "import pf_toolkit; pf_toolkit.rutas_bake_nodes(nuke.thisNode())"
    )
    btn_bake.setFlag(nuke.STARTLINE)
    ctrl.addKnob(btn_bake)
    return ctrl


# ==============================================================================
# 2. PF SMART WRITE (Auto-Carpetas + Read desde Write)
# ==============================================================================
def smartwrite_before_render():
    d = os.path.dirname(nuke.filename(nuke.thisNode()))
    if d and not os.path.exists(d):
        os.makedirs(d)


def smartwrite_autopath(n):
    root_name = nuke.root().name()
    if not root_name or root_name == "Root":
        nuke.message("Guarda primero el proyecto .nk.")
        return
    proj_dir = os.path.dirname(root_name).replace("\\", "/")
    shot_base = os.path.splitext(os.path.basename(root_name))[0]
    render_path = "{0}/renders/{1}/{1}.%04d.exr".format(proj_dir, shot_base)
    n["file"].setValue(render_path)
    n["file_type"].setValue("exr")


def smartwrite_read_from_write(w):
    path = w["file"].getValue()
    if not path:
        nuke.message("El nodo Write no tiene ruta.")
        return
    r = nuke.createNode("Read", inpanel=False)
    r["file"].setValue(path)
    r["first"].setValue(int(nuke.root()["first_frame"].getValue()))
    r["last"].setValue(int(nuke.root()["last_frame"].getValue()))
    r.setXpos(w.xpos())
    r.setYpos(w.ypos() + 90)


def create_pf_smart_write():
    w = nuke.createNode("Write", inpanel=True)
    w.setName("PF_SmartWrite1")
    w["tile_color"].setValue(0xffaa00ff)
    w["note_font_size"].setValue(14)
    w["label"].setValue("PERFECT FRAME RENDER (v" + SUITE_VERSION + ")\n[file tail [value file]]")
    w["beforeRender"].setValue("import pf_toolkit; pf_toolkit.smartwrite_before_render()")

    tab = nuke.Tab_Knob("pf_write_tab", "PF SmartWrite")
    w.addKnob(tab)
    w.addKnob(nuke.Text_Knob("pf_info", "Perfect Frame v" + SUITE_VERSION, "Crea carpetas automaticamente al dar Render."))

    btn_auto = nuke.PyScript_Knob(
        "btn_auto_path",
        "1. Autocompletar Ruta EXR",
        "import pf_toolkit; pf_toolkit.smartwrite_autopath(nuke.thisNode())"
    )
    btn_auto.setFlag(nuke.STARTLINE)
    w.addKnob(btn_auto)

    btn_read = nuke.PyScript_Knob(
        "btn_read_write",
        "2. Crear Nodo Read desde Render",
        "import pf_toolkit; pf_toolkit.smartwrite_read_from_write(nuke.thisNode())"
    )
    btn_read.setFlag(nuke.STARTLINE)
    w.addKnob(btn_read)
    return w


# ==============================================================================
# 3. PF EXR SPLITTER (Desglose automatico Multipass AOV)
# ==============================================================================
def split_selected_exr():
    sel = nuke.selectedNodes("Read")
    if not sel:
        nuke.message("Selecciona primero un nodo Read