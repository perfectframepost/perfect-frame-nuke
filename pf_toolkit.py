# -*- coding: utf-8 -*-
import nuke
import os
import importlib
import subprocess

# --- VERSION DE LA SUITE PERFECT FRAME ---
SUITE_VERSION = "1.0.0"

NUKE_DIR = os.path.expanduser("~/.nuke").replace("\\", "/")
TOOLSETS_DIR = os.path.join(NUKE_DIR, "PF_ToolSets").replace("\\", "/")

def _paste_tcl_node(tcl_script):
    for n in nuke.selectedNodes():
        n.setSelected(False)
    nuke.nodePaste(tcl_script)

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
    ctrl.addKnob(btn_bake)
    return ctrl

# ==============================================================================
# 2. PF SLATE BURN-IN (Con Artista Responsable)
# ==============================================================================
def create_pf_slate():
    tcl = """Group {
 name PF_Slate_BurnIn
 tile_color 0xff5500ff
 note_font_size 14
 label "Artista: \\[value artist_name]\\nEstado: \\[value shot_status]"
 selected true
 addUserKnob {20 pf_slate_tab l "PF Slate Burn-In"}
 addUserKnob {26 info_header l "PERFECT FRAME v1.0.0" T "Generador de Burn-In para revision y control de planos"}
 addUserKnob {26 div_id l "Identificacion del Plano"}
 addUserKnob {1 artist_name l "Artista Responsable"}
 artist_name "SIN ASIGNAR"
 addUserKnob {22 btn_os_user l "Usar Usuario del Sistema" -STARTLINE T "import nuke, getpass\\nnuke.thisNode().knob('artist_name').setValue(getpass.getuser())"}
 addUserKnob {1 custom_shot l "Nombre del Shot"}
 custom_shot "\\[file rootname \\[file tail \\[value root.name]]]"
 addUserKnob {22 btn_auto_shot l "Tomar del Archivo .nk" -STARTLINE T "import nuke\\nnuke.thisNode().knob('custom_shot').setValue('\\[file rootname \\[file tail \\[value root.name]]]')"}
 addUserKnob {4 shot_status l "Estado del Plano" M {"WIP" "PARA REVISION" "CORRECCION QC" "FINAL"}}
 addUserKnob {1 shot_notes l "Notas / Version"}
 shot_notes "v001 - Comp Preliminar"
 addUserKnob {26 div_style l "Apariencia Visual"}
 addUserKnob {1 studio_title l "Titulo del Estudio"}
 studio_title "PERFECT FRAME | v1.0.0"
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
    _save_and_paste_tcl(tcl)

# ==============================================================================
# 3. PF SMART WRITE
# ==============================================================================
def create_pf_smart_write():
    w = nuke.createNode("Write", inpanel=True)
    w.setName("PF_SmartWrite1")
    w['tile_color'].setValue(0xffaa00ff)
    w['note_font_size'].setValue(14)
    w['label'].setValue("PERFECT FRAME RENDER (v" + SUITE_VERSION + ")\\n[file tail [value file]]")
    w['beforeRender'].setValue("import os, nuke; d = os.path.dirname(nuke.filename(nuke.thisNode())); os.makedirs(d) if d and not os.path.exists(d) else None")

    tab = nuke.Tab_Knob("pf_write_tab", "PF SmartWrite")
    w.addKnob(tab)
    w.addKnob(nuke.Text_Knob("pf_info", "PERFECT FRAME v" + SUITE_VERSION, "Crea carpetas automaticamente al dar Render."))

    auto_path_code = "import nuke, os\\nn = nuke.thisNode()\\nroot_name = nuke.root().name()\\nif not root_name or root_name == 'Root':\\n    nuke.message('Guarda primero el proyecto .nk.')\\nelse:\\n    proj_dir = os.path.dirname(root_name).replace(chr(92), '/')\\n    shot_base = os.path.splitext(os.path.basename(root_name))[0]\\n    render_path = '{0}/renders/{1}/{1}.%04d.exr'.format(proj_dir, shot_base)\\n    n['file'].setValue(render_path)\\n    n['file_type'].setValue('exr')"
    btn_auto = nuke.PyScript_Knob("btn_auto_path", "1. Autocompletar Ruta EXR", auto_path_code)
    btn_auto.setFlag(nuke.STARTLINE)
    w.addKnob(btn_auto)

    read_from_write_code = "import nuke\\nw = nuke.thisNode()\\npath = w['file'].getValue()\\nif not path:\\n    nuke.message('El nodo Write no tiene ruta.')\\nelse:\\n    r = nuke.createNode('Read', inpanel=False)\\n    r['file'].setValue(path)\\n    r['first'].setValue(int(nuke.root()['first_frame'].getValue()))\\n    r['last'].setValue(int(nuke.root()['last_frame'].getValue()))\\n    r.setXpos(w.xpos())\\n    r.setYpos(w.ypos() + 90)"
    btn_read = nuke.PyScript_Knob("btn_read_write", "2. Crear Nodo Read desde Render", read_from_write_code)
    btn_read.setFlag(nuke.STARTLINE)
    w.addKnob(btn_read)
    return w

# ==============================================================================
# 4. FUNCION DE ACTUALIZACION DESDE GITHUB (GIT PULL)
# ==============================================================================
def update_suite_from_github():
    try:
        process = subprocess.Popen(["git", "pull"], cwd=NUKE_DIR, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        stdout, stderr = process.communicate()
        
        if process.returncode == 0:
            import pf_toolkit
            importlib.reload(pf_toolkit)
            pf_toolkit.build_pf_menus()
            output_msg = stdout.decode('utf-8', errors='ignore').strip()
            if not output_msg:
                output_msg = "La suite ya estaba en su version mas reciente."
            nuke.message("¡Actualizacion exitosa desde GitHub! (v" + SUITE_VERSION + ")\\n\\n" + output_msg)
        else:
            err_msg = stderr.decode('utf-8', errors='ignore').strip()
            nuke.message("Error al sincronizar con GitHub:\\n" + err_msg)
    except Exception as e:
        nuke.message("No se pudo ejecutar Git Pull:\\n" + str(e))

# ==============================================================================
# CONSTRUCCION DE MENUS
# ==============================================================================
def _save_and_paste_tcl(tcl_string):
    import tempfile
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".nk", mode="w")
    tmp.write(tcl_string)
    tmp.close()
    nuke.nodePaste(tmp.name)
    os.remove(tmp.name)

def build_pf_menus():
    for bar_name in ["Nuke", "Nodes"]:
        menubar = nuke.menu(bar_name)
        pf_menu = menubar.addMenu("PERFECT FRAME")
        pf_menu.clearMenu()

        # Pipeline
        pipe = pf_menu.addMenu("1. Pipeline y Rutas")
        pipe.addCommand("RUTAS PERFECT FRAME (Relink Master)", "import pf_toolkit; pf_toolkit.create_rutas_pf()")
        pipe.addCommand("PF SmartWrite (Auto-Folders)", "import pf_toolkit; pf_toolkit.create_pf_smart_write()")

        # QC y Entregas
        qc = pf_menu.addMenu("2. QC y Entregas")
        qc.addCommand("PF Slate Burn-In (Con Artista)", "import pf_toolkit; pf_toolkit.create_pf_slate()")

        # ToolSets personalizados locales
        custom_menu = pf_menu.addMenu("3. ToolSets del Estudio")
        if os.path.exists(TOOLSETS_DIR):
            for root, dirs, files in os.walk(TOOLSETS_DIR):
                for f in sorted(files):
                    if f.endswith(".nk"):
                        full_p = os.path.join(root, f).replace("\\\\", "/")
                        rel_p = os.path.relpath(full_p, TOOLSETS_DIR).replace("\\\\", "/")[:-3]
                        custom_menu.addCommand(rel_p, "nuke.nodePaste('{0}')".format(full_p))

        pf_menu.addSeparator()
        pf_menu.addCommand("🔄 Sincronizar / Actualizar desde GitHub (v" + SUITE_VERSION + ")", "import pf_toolkit; pf_toolkit.update_suite_from_github()")