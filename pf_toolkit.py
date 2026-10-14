# -*- coding: utf-8 -*-
import nuke
import os
import importlib
import subprocess
import shutil
import stat
import tempfile

# --- VERSION DE LA SUITE PERFECT FRAME ---
SUITE_VERSION = "1.0.8"

NUKE_DIR = os.path.expanduser("~/.nuke").replace("\\", "/")


def _find_git_repo():
    candidate = os.path.join(NUKE_DIR, "perfect-frame-nuke").replace("\\", "/")
    if os.path.exists(os.path.join(candidate, ".git")):
        return candidate
    try:
        for item in os.listdir(NUKE_DIR):
            item_path = os.path.join(NUKE_DIR, item).replace("\\", "/")
            if os.path.isdir(item_path) and os.path.exists(os.path.join(item_path, ".git")):
                return item_path
    except Exception:
        pass
    return candidate


def _get_toolsets_dir():
    repo_dir = _find_git_repo()
    ts_dir = os.path.join(repo_dir, "PF_ToolSets").replace("\\", "/")
    if not os.path.exists(ts_dir):
        try:
            os.makedirs(ts_dir)
        except Exception:
            pass
    return ts_dir


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
        nuke.message("Selecciona primero un nodo Read con un archivo EXR multicanal.")
        return
    read_node = sel[0]
    layers = list(set([c.split(".")[0] for c in read_node.channels()]))
    skip = ["rgba", "rgb", "alpha", "depth"]
    aovs = [l for l in layers if l not in skip]
    if not aovs:
        nuke.message("Este Read solo contiene canales estandar (RGBA). No se detectaron AOVs 3D.")
        return

    base_x = read_node.xpos()
    base_y = read_node.ypos() + 140
    prev_merge = None

    for idx, layer in enumerate(sorted(aovs)):
        shuf = nuke.nodes.Shuffle(label=layer, inputs=[read_node])
        shuf["in"].setValue(layer)
        shuf.setXpos(base_x + (idx * 140))
        shuf.setYpos(base_y)

        if prev_merge is None:
            prev_merge = shuf
        else:
            m = nuke.nodes.Merge2(operation="plus", inputs=[prev_merge, shuf], label="Plus " + layer)
            m.setXpos(base_x + (idx * 140))
            m.setYpos(base_y + 100)
            prev_merge = m

    nuke.message("Se desplegaron {0} pases AOV desde {1}.".format(len(aovs), read_node.name()))


# ==============================================================================
# 4. PF EXPO GLOW (Glow optico exponencial)
# ==============================================================================
def create_pf_expoglow():
    tcl = """Group {
 name PF_ExpoGlow
 tile_color 0xff5500ff
 note_font_size 14
 selected true
 addUserKnob {20 pf_glow_tab l "PF ExpoGlow"}
 addUserKnob {26 info l "Perfect Frame" T "Glow exponencial con caida fisica realista"}
 addUserKnob {7 intensity l "Intensidad Global" R 0 5}
 intensity 1
 addUserKnob {7 threshold l "Umbral de Altas Luces (Threshold)" R 0 2}
 threshold 0.5
 addUserKnob {7 radius l "Radio Base" R 1 50}
 radius 4
 addUserKnob {18 tint l "Tinte de Color"}
 tint {1 1 1}
 addUserKnob {6 glow_only l "Ver Solo el Glow" +STARTLINE}
}
 Input {
  inputs 0
  name Input1
  xpos 0
  ypos -250
 }
set N_in [stack 0]
 Keyer {
  operation "luminance key"
  range {{parent.threshold} {parent.threshold+0.5} 1 1}
  name Keyer_Threshold
  xpos 180
  ypos -250
 }
 Premult {
  name Premult1
  xpos 180
  ypos -200
 }
set N_key [stack 0]
 Blur {
  channels rgba
  size {{parent.radius}}
  name Blur_1x
  xpos 100
  ypos -120
 }
push $N_key
 Blur {
  channels rgba
  size {{parent.radius*4}}
  name Blur_4x
  xpos 200
  ypos -120
 }
push $N_key
 Blur {
  channels rgba
  size {{parent.radius*16}}
  name Blur_16x
  xpos 300
  ypos -120
 }
push $N_key
 Blur {
  channels rgba
  size {{parent.radius*64}}
  name Blur_64x
  xpos 400
  ypos -120
 }
 Merge2 {
  inputs 2
  operation plus
  name Plus1
  xpos 300
  ypos -50
 }
 Merge2 {
  inputs 2
  operation plus
  name Plus2
  xpos 200
  ypos -10
 }
 Merge2 {
  inputs 2
  operation plus
  name Plus3
  xpos 100
  ypos 30
 }
 Multiply {
  channels rgb
  value {{parent.tint.r*parent.intensity*0.25} {parent.tint.g*parent.intensity*0.25} {parent.tint.b*parent.intensity*0.25} 1}
  name Multiply_Tint
  xpos 100
  ypos 80
 }
set N_glow [stack 0]
push $N_in
 Merge2 {
  inputs 2
  operation plus
  bbox B
  name Merge_Final
  xpos 0
  ypos 80
 }
 Switch {
  inputs 2
  which {{parent.glow_only}}
  name Switch_View
  xpos 0
  ypos 140
 }
 Output {
  name Output1
  xpos 0
  ypos 210
 }
end_group"""
    _paste_tcl_node(tcl)


# ==============================================================================
# 5. PF SLATE BURN-IN (Con Artista Responsable)
# ==============================================================================
def create_pf_slate():
    tcl = """Group {
 name PF_Slate_BurnIn
 tile_color 0xff5500ff
 note_font_size 14
 label "Artista: \\[value artist_name]\\nEstado: \\[value shot_status]"
 selected true
 addUserKnob {20 pf_slate_tab l "PF Slate Burn-In"}
 addUserKnob {26 info_header l "Perfect Frame v1.0.8" T "Generador de Burn-In para revision y control de planos"}
 addUserKnob {26 div_id l "Identificacion del Plano"}
 addUserKnob {1 artist_name l "Artista Responsable"}
 artist_name "SIN ASIGNAR"
 addUserKnob {22 btn_os_user l "Usar Usuario del Sistema" -STARTLINE T "import nuke, getpass; nuke.thisNode().knob('artist_name').setValue(getpass.getuser())"}
 addUserKnob {1 custom_shot l "Nombre del Shot"}
 custom_shot "\\[file rootname \\[file tail \\[value root.name]]]"
 addUserKnob {22 btn_auto_shot l "Tomar del Archivo .nk" -STARTLINE T "import nuke; nuke.thisNode().knob('custom_shot').setValue('\\[file rootname \\[file tail \\[value root.name]]]')"}
 addUserKnob {4 shot_status l "Estado del Plano" M {"WIP" "PARA REVISION" "CORRECCION QC" "FINAL"}}
 addUserKnob {1 shot_notes l "Notas / Version"}
 shot_notes "v001 - Comp Preliminar"
 addUserKnob {26 div_style l "Apariencia Visual"}
 addUserKnob {1 studio_title l "Titulo del Estudio"}
 studio_title "Perfect Frame | v1.0.8"
 addUserKnob {7 bar_height l "Altura de Barras (px)" R 25 120}
 bar_height 55
 addUserKnob {7 bar_opacity l "Opacidad de Barras" R 0 1}
 bar_opacity 0.75
 addUserKnob {7 text_size l "Tamano de Fuente" R 12 60}
 text_size 24
}
 Input {
  inputs 0
  name Input1
  xpos 0
  ypos -200
 }
 Rectangle {
  area {{0} {input.height-parent.bar_height} {input.width} {input.height}}
  color {0 0 0 1}
  opacity {{parent.bar_opacity}}
  name Top_Bar
  xpos 0
  ypos -140
 }
 Rectangle {
  area {{0} {0} {input.width} {parent.bar_height}}
  color {0 0 0 1}
  opacity {{parent.bar_opacity}}
  name Bottom_Bar
  xpos 0
  ypos -90
 }
 Text {
  message "\\[value parent.studio_title]"
  font "\\[python nuke.defaultFontPathname()]"
  size {{parent.text_size}}
  xjustify left
  yjustify center
  box {{30} {input.height-parent.bar_height} {input.width*0.4} {input.height}}
  color {1 0.45 0.1 1}
  name Text_Studio
  xpos 0
  ypos -40
 }
 Text {
  message "\\[value parent.custom_shot]"
  font "\\[python nuke.defaultFontPathname()]"
  size {{parent.text_size*1.1}}
  xjustify center
  yjustify center
  box {{0} {input.height-parent.bar_height} {input.width} {input.height}}
  color {1 1 1 1}
  name Text_ShotName
  xpos 0
  ypos 10
 }
 Text {
  message "\\[value parent.shot_status]  |  \\[date %Y-%m-%d]"
  font "\\[python nuke.defaultFontPathname()]"
  size {{parent.text_size}}
  xjustify right
  yjustify center
  box {{input.width*0.6} {input.height-parent.bar_height} {input.width-30} {input.height}}
  color {0.9 0.9 0.9 1}
  name Text_Status_Date
  xpos 0
  ypos 60
 }
 Text {
  message "ARTISTA: \\[value parent.artist_name]"
  font "\\[python nuke.defaultFontPathname()]"
  size {{parent.text_size}}
  xjustify left
  yjustify center
  box {{30} {0} {input.width*0.4} {parent.bar_height}}
  color {1 1 1 1}
  name Text_Artist
  xpos 0
  ypos 110
 }
 Text {
  message "\\[value parent.shot_notes]"
  font "\\[python nuke.defaultFontPathname()]"
  size {{parent.text_size*0.95}}
  xjustify center
  yjustify center
  box {{0} {0} {input.width} {parent.bar_height}}
  color {0.8 0.8 0.8 1}
  name Text_Notes
  xpos 0
  ypos 160
 }
 Text {
  message "FRAME: \\[format %04d \\[frame]]  (\\[value root.first_frame]-\\[value root.last_frame])"
  font "\\[python nuke.defaultFontPathname()]"
  size {{parent.text_size}}
  xjustify right
  yjustify center
  box {{input.width*0.6} {0} {input.width-30} {parent.bar_height}}
  color {0.9 0.9 0.9 1}
  name Text_Frames
  xpos 0
  ypos 210
 }
 Output {
  name Output1
  xpos 0
  ypos 280
 }
end_group"""
    _paste_tcl_node(tcl)


# ==============================================================================
# 6. PF QC INSPECTOR (Auditor tecnico, NaNs/Negativos, Diferencia y Grano)
# ==============================================================================
def create_pf_qc_inspector():
    tcl = """Group {
 name PF_QC_Inspector
 tile_color 0x00aaffff
 note_font_size 14
 label "Modo: \\[value qc_mode]"
 selected true
 addUserKnob {20 pf_qc_tab l "PF QC Inspector"}
 addUserKnob {26 info l "Perfect Frame QC" T "Inspector tecnico antes de exportar. Input 1: Comp | Input 2: Plate Original"}
 addUserKnob {4 qc_mode l "Modo de Inspeccion" M {"Pass-Through (Comp Final)" "Diferencia Extrema vs Plate" "Mapa de Grano / Nitidez (High-Pass)" "Detector de Pixeles Rotos (NaN / Negativos)"}}
 addUserKnob {6 fix_nans l "Reparar NaNs y Negativos Automaticamente en la Salida" +STARTLINE}
 fix_nans true
 addUserKnob {7 diff_gain l "Multiplicador de Diferencia" R 1 100}
 diff_gain 25
}
 Input {
  inputs 0
  name Plate_Ref
  xpos 260
  ypos -220
  number 1
 }
 Input {
  inputs 0
  name Comp_In
  xpos 0
  ypos -220
 }
 Expression {
  expr0 "isnan(r) || isinf(r) ? 0 : (parent.fix_nans ? max(0, r) : r)"
  expr1 "isnan(g) || isinf(g) ? 0 : (parent.fix_nans ? max(0, g) : g)"
  expr2 "isnan(b) || isinf(b) ? 0 : (parent.fix_nans ? max(0, b) : b)"
  name Sanitize_Pixels
  xpos 0
  ypos -150
 }
set N_clean [stack 0]
 Expression {
  expr0 "isnan(r) || isinf(r) || r < 0 ? 1 : r*0.15"
  expr1 "isnan(g) || isinf(g) || g < 0 ? 0 : g*0.15"
  expr2 "isnan(b) || isinf(b) || b < 0 ? 1 : b*0.15"
  name NaN_Neg_Visualizer
  xpos 380
  ypos -60
 }
push $N_clean
 Blur {
  channels rgba
  size 6
  name Blur_HighPass
  xpos 200
  ypos -100
 }
push $N_clean
 Merge2 {
  inputs 2
  operation minus
  name Merge_HighPass
  xpos 200
  ypos -50
 }
 Multiply {
  channels rgb
  value 15
  name Boost_Grain
  xpos 200
  ypos -10
 }
 Add {
  channels rgb
  value 0.5
  name Offset_MidGrey
  xpos 200
  ypos 30
 }
push 0
push $N_clean
 Merge2 {
  inputs 2
  operation difference
  name Diff_Plate
  xpos 80
  ypos -50
 }
 Multiply {
  channels rgb
  value {{parent.diff_gain}}
  name Boost_Diff
  xpos 80
  ypos 10
 }
push $N_clean
 Switch {
  inputs 4
  which {{parent.qc_mode}}
  name Switch_QC_Mode
  xpos 0
  ypos 120
 }
 Output {
  name Output1
  xpos 0
  ypos 200
 }
end_group"""
    _paste_tcl_node(tcl)


# ==============================================================================
# 7. GESTOR DE TOOLSETS DEL ESTUDIO (Guardar, Cargar y Explorar)
# ==============================================================================
def save_selected_as_toolset():
    sel = nuke.selectedNodes()
    if not sel:
        nuke.message("Selecciona primero en el Node Graph los nodos que deseas guardar como ToolSet.")
        return

    panel = nuke.Panel("Guardar Nuevo ToolSet - Perfect Frame")
    panel.addSingleLineInput("Categoria (Subcarpeta):", "General")
    panel.addSingleLineInput("Nombre del ToolSet:", "")
    if not panel.show():
        return

    category = panel.value("Categoria (Subcarpeta):").strip().replace("\\", "/")
    name = panel.value("Nombre del ToolSet:").strip()

    if not name:
        nuke.message("Debes asignar un nombre al ToolSet.")
        return

    # Limpiar caracteres especiales no deseados en nombres de archivo
    invalid_chars = '<>:"|?*'
    for ch in invalid_chars:
        category = category.replace(ch, "")
        name = name.replace(ch, "")

    if name.lower().endswith(".nk"):
        name = name[:-3]

    ts_base_dir = _get_toolsets_dir()
    target_dir = os.path.join(ts_base_dir, category).replace("\\", "/") if category else ts_base_dir

    if not os.path.exists(target_dir):
        os.makedirs(target_dir)

    file_path = os.path.join(target_dir, name + ".nk").replace("\\", "/")

    if os.path.exists(file_path):
        overwrite = nuke.ask("El ToolSet '" + name + "' ya existe en esa categoria.\n¿Deseas sobrescribirlo?")
        if not overwrite:
            return

    nuke.nodeCopy(file_path)
    build_pf_menus()

    nuke.message(
        "¡ToolSet guardado con exito!\n\n"
        "Ubicacion: " + file_path + "\n\n"
        "Ya aparece disponible en el menu '4. ToolSets del Estudio'.\n"
        "Recuerda hacer Commit y Push en GitHub Desktop para compartirlo con todos los artistas."
    )


def open_toolsets_folder():
    ts_dir = _get_toolsets_dir()
    try:
        if os.name == "nt":
            os.startfile(ts_dir.replace("/", "\\"))
        else:
            subprocess.Popen(["open", ts_dir])
    except Exception as e:
        nuke.message("Ruta de ToolSets:\n" + ts_dir + "\n\nError al abrir ventana: " + str(e))


def load_pf_toolset(file_path):
    if os.path.exists(file_path):
        nuke.nodePaste(file_path)
    else:
        nuke.message("No se encontro el archivo de ToolSet:\n" + file_path)


# ==============================================================================
# FUNCION DE ACTUALIZACION DESDE GITHUB (Sin shell=True)
# ==============================================================================
def update_suite_from_github():
    try:
        repo_path = _find_git_repo()
        git_dir = os.path.join(repo_path, ".git")

        if not os.path.exists(git_dir):
            nuke.message("Error: No se encontro un repositorio Git valido en:\n" + repo_path)
            return

        process = subprocess.Popen(
            ["git", "pull"],
            cwd=repo_path,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        stdout, stderr = process.communicate()

        if process.returncode == 0:
            import pf_toolkit
            importlib.reload(pf_toolkit)
            pf_toolkit.build_pf_menus()
            output_msg = stdout.decode("utf-8", errors="ignore").strip()
            if not output_msg:
                output_msg = "La suite ya estaba en su version mas reciente."
            nuke.message("¡Actualizacion exitosa desde GitHub! (v" + pf_toolkit.SUITE_VERSION + ")\n\n" + output_msg)
        else:
            err_msg = stderr.decode("utf-8", errors="ignore").strip()
            nuke.message("Error al sincronizar con GitHub:\n" + err_msg)
    except Exception as e:
        nuke.message("No se pudo ejecutar Git Pull:\n" + str(e))


# ==============================================================================
# FUNCION DE DESINSTALACION ROBUSTA (Blindada contra WinError 5)
# ==============================================================================
def _remove_readonly(func, path, excinfo):
    os.chmod(path, stat.S_IWRITE)
    func(path)


def uninstall_perfect_frame():
    confirm = nuke.ask(
        "¿Estás seguro de que deseas desinstalar la suite Perfect Frame de este equipo?\n"
        "Se eliminarán los ganchos de configuración y los archivos locales."
    )
    if not confirm:
        return

    try:
        init_path = os.path.join(NUKE_DIR, "init.py").replace("\\", "/")
        menu_path = os.path.join(NUKE_DIR, "menu.py").replace("\\", "/")
        repo_path = _find_git_repo()

        if os.path.exists(init_path):
            with open(init_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            clean_lines = [l for l in lines if "perfect-frame-nuke" not in l and "PERFECT FRAME" not in l]
            with open(init_path, "w", encoding="utf-8") as f:
                f.writelines(clean_lines)

        if os.path.exists(menu_path):
            with open(menu_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            clean_lines = [l for l in lines if "pf_toolkit" not in l and "PERFECT FRAME" not in l]
            with open(menu_path, "w", encoding="utf-8") as f:
                f.writelines(clean_lines)

        if os.path.exists(repo_path) and ".nuke" in repo_path:
            shutil.rmtree(repo_path, onerror=_remove_readonly)

        nuke.message("Desinstalación completada con éxito.\nReinicia Nuke para finalizar la limpieza del sistema.")
    except Exception as e:
        nuke.message("Ocurrió un error durante la desinstalación: " + str(e))


# ==============================================================================
# CONSTRUCCION DE MENUS
# ==============================================================================
def build_pf_menus():
    ts_dir = _get_toolsets_dir()

    for bar_name in ["Nuke", "Nodes"]:
        menubar = nuke.menu(bar_name)
        pf_menu = menubar.addMenu("Perfect Frame")
        pf_menu.clearMenu()

        pipe = pf_menu.addMenu("1. Pipeline y Rutas")
        pipe.addCommand("RUTAS PERFECT FRAME (Relink Master)", "import pf_toolkit; pf_toolkit.create_rutas_pf()")
        pipe.addCommand("PF SmartWrite (Auto-Folders)", "import pf_toolkit; pf_toolkit.create_pf_smart_write()")
        pipe.addCommand("PF EXR Multipass Splitter", "import pf_toolkit; pf_toolkit.split_selected_exr()")

        comp = pf_menu.addMenu("2. Lookdev y Comp")
        comp.addCommand("PF ExpoGlow (Glow Optico)", "import pf_toolkit; pf_toolkit.create_pf_expoglow()")

        qc = pf_menu.addMenu("3. QC y Entregas")
        qc.addCommand("PF Slate Burn-In (Con Artista)", "import pf_toolkit; pf_toolkit.create_pf_slate()")
        qc.addCommand("PF QC Inspector (NaNs, Diff y Grano)", "import pf_toolkit; pf_toolkit.create_pf_qc_inspector()")

        custom_menu = pf_menu.addMenu("4. ToolSets del Estudio")
        custom_menu.addCommand(
            "➕ Guardar Seleccion como ToolSet...",
            "import pf_toolkit; pf_toolkit.save_selected_as_toolset()"
        )
        custom_menu.addCommand(
            "📂 Abrir Carpeta de ToolSets",
            "import pf_toolkit; pf_toolkit.open_toolsets_folder()"
        )
        custom_menu.addSeparator()

        found_any = False
        if os.path.exists(ts_dir):
            for root, dirs, files in os.walk(ts_dir):
                for f in sorted(files):
                    if f.endswith(".nk"):
                        found_any = True
                        full_p = os.path.join(root, f).replace("\\", "/")
                        rel_p = os.path.relpath(full_p, ts_dir).replace("\\", "/")[:-3]
                        custom_menu.addCommand(
                            rel_p,
                            "import pf_toolkit; pf_toolkit.load_pf_toolset('{0}')".format(full_p)
                        )

        if not found_any:
            custom_menu.addCommand("(Sin ToolSets guardados aun)", "pass")

        pf_menu.addSeparator()
        pf_menu.addCommand(
            "🔄 Sincronizar / Actualizar desde GitHub (v" + SUITE_VERSION + ")",
            "import pf_toolkit; pf_toolkit.update_suite_from_github()"
        )
        pf_menu.addCommand(
            "🗑️ Desinstalar Suite",
            "import pf_toolkit; pf_toolkit.uninstall_perfect_frame()"
        )