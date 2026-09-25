from bettertoolbox.qt_compat import QToolButton, QPalette, QColor, QSize, QEvent
from krita import *
from bettertoolbox.json_class import json_class
def krita_display_name(actionName, fallbackName):
    try:
        action = Application.action(actionName)
        if action:
            text = action.text().replace("&", "").strip()
            if text:
                return text
    except Exception:
        pass
    return i18n(fallbackName)
class ToolButton(QToolButton):
    def __init__(self, actionName, toolName, icon, category, isMain):
        super().__init__()
        self.actionName = actionName
        self.toolName = toolName
        self.iconName = icon
        self.category = category
        self.isMain = isMain
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Button, QColor(74, 108, 134))
        self.setPalette(palette)
        self.updateIconSize()
        self.setCheckable(True)
        self.setAutoRaise(True)
        self._load_icon()
        self.setObjectName(self.actionName)
        self.updateToolTip()
    def displayName(self):
        return krita_display_name(self.actionName, self.toolName)
    def updateToolTip(self, showShortcut=None):
        if showShortcut is None:
            showShortcut = json_class().loadJSON().get("showShortcuts", True)
        name = self.displayName()
        if showShortcut:
            try:
                action = Application.action(self.actionName)
                if action:
                    shortcut = action.shortcut().toString()
                    if shortcut:
                        self.setToolTip(f"{name}  [{shortcut}]")
                        return
            except Exception:
                pass
        self.setToolTip(name)
    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.Type.LanguageChange:
            self.updateToolTip()
    def _load_icon(self):
        import os
        from bettertoolbox.qt_compat import QIcon
        if os.path.isabs(self.iconName) and os.path.exists(self.iconName):
            self.setIcon(QIcon(self.iconName))
        else:
            icon = Application.icon(self.iconName)
            if icon and not icon.isNull():
                self.setIcon(icon)
                return
                
            act = Application.action(self.iconName)
            if act and not act.icon().isNull():
                self.setIcon(act.icon())
                return
                
            action = Application.action(self.actionName)
            if action and not action.icon().isNull():
                self.setIcon(action.icon())
    def showEvent(self, event):
        super().showEvent(event)
        if self.icon().isNull():
            self._load_icon()
    def updateIconSize(self, iconSize=None, btnSize=None):
        if iconSize is None or btnSize is None:
            jm = json_class()
            data = jm.loadJSON()
            if iconSize is None:
                iconSize = data.get("iconSize", 18)
            if btnSize is None:
                btnSize = data.get("btnSize", 28)
                
        self.setFixedSize(QSize(btnSize, btnSize))
        self.setIconSize(QSize(iconSize, iconSize))
        self.repaint()
def get_default_tools():
    return [
        {"actionName": "KritaTransform/KisToolMove", "toolName": "Move Tool", "icon": "krita_tool_move", "category": "Move", "isMain": "1"},
        {"actionName": "KisToolTransform", "toolName": "Transform Tool", "icon": "krita_tool_transform", "category": "Move", "isMain": "0"},
        {"actionName": "KisToolSelectRectangular", "toolName": "Rectangular Selection", "icon": "tool_rect_selection", "category": "Marquee", "isMain": "1"},
        {"actionName": "KisToolSelectElliptical", "toolName": "Elliptical Selection", "icon": "tool_elliptical_selection", "category": "Marquee", "isMain": "0"},
        {"actionName": "KisToolSelectOutline", "toolName": "Outline Selection", "icon": "tool_outline_selection", "category": "Lasso", "isMain": "1"},
        {"actionName": "KisToolSelectPolygonal", "toolName": "Polygonal Selection", "icon": "tool_polygonal_selection", "category": "Lasso", "isMain": "0"},
        {"actionName": "KisToolSelectMagnetic", "toolName": "Magnetic Selection", "icon": "tool_magnetic_selection", "category": "Lasso", "isMain": "0"},
        {"actionName": "KisToolSelectContiguous", "toolName": "Contiguous Selection", "icon": "tool_contiguous_selection", "category": "Wand", "isMain": "1"},
        {"actionName": "KisToolSelectSimilar", "toolName": "Similar Selection", "icon": "tool_similar_selection", "category": "Wand", "isMain": "0"},
        {"actionName": "KisToolCrop", "toolName": "Crop Tool", "icon": "tool_crop", "category": "Crop", "isMain": "1"},
        {"actionName": "KritaSelected/KisToolColorSampler", "toolName": "Color Sampler", "icon": "krita_tool_color_sampler", "category": "Eyedropper", "isMain": "1"},
        {"actionName": "KritaShape/KisToolMeasure", "toolName": "Measure Tool", "icon": "krita_tool_measure", "category": "Eyedropper", "isMain": "0"},
        {"actionName": "KritaShape/KisToolSmartPatch", "toolName": "Smart Patch Tool", "icon": "krita_tool_smart_patch", "category": "Healing", "isMain": "1"},
        {"actionName": "KritaShape/KisToolBrush", "toolName": "Freehand Brush", "icon": "krita_tool_freehand", "category": "Brush", "isMain": "1"},
        {"actionName": "KritaShape/KisToolDyna", "toolName": "Dynamic Brush", "icon": "krita_tool_dyna", "category": "Brush", "isMain": "0"},
        {"actionName": "KritaShape/KisToolMultiBrush", "toolName": "Multibrush", "icon": "krita_tool_multihand", "category": "Brush", "isMain": "0"},
        {"actionName": "KisToolPencil", "toolName": "Freehand Path", "icon": "krita_tool_freehandvector", "category": "Brush", "isMain": "0"},
        {"actionName": "erase_action", "toolName": "Set eraser mode", "icon": "erase_action", "category": "Erase", "isMain": "1"},
        {"actionName": "KritaFill/KisToolFill", "toolName": "Fill Tool", "icon": "krita_tool_color_fill", "category": "Fill", "isMain": "1"},
        {"actionName": "KritaFill/KisToolGradient", "toolName": "Gradient Tool", "icon": "krita_tool_gradient", "category": "Fill", "isMain": "0"},
        {"actionName": "KritaShape/KisToolLazyBrush", "toolName": "Colorize Brush", "icon": "krita_tool_lazybrush", "category": "Fill", "isMain": "0"},
        {"actionName": "KisToolPath", "toolName": "Bezier Tool", "icon": "krita_draw_path", "category": "Pen", "isMain": "1"},
        {"actionName": "KisToolSelectPath", "toolName": "Bezier Selection", "icon": "tool_path_selection", "category": "Pen", "isMain": "0"},
        {"actionName": "SvgTextTool", "toolName": "Text Tool", "icon": "draw-text", "category": "Text", "isMain": "1"},
        {"actionName": "KarbonCalligraphyTool", "toolName": "Calligraphy", "icon": "calligraphy", "category": "Text", "isMain": "0"},
        {"actionName": "InteractionTool", "toolName": "Select Shape", "icon": "select", "category": "PathSelect", "isMain": "1"},
        {"actionName": "PathTool", "toolName": "Edit Shape Tool", "icon": "shape_handling", "category": "PathSelect", "isMain": "0"},
        {"actionName": "KritaShape/KisToolRectangle", "toolName": "Rectangle Tool", "icon": "krita_tool_rectangle", "category": "Shape", "isMain": "1"},
        {"actionName": "KritaShape/KisToolEllipse", "toolName": "Ellipse Tool", "icon": "krita_tool_ellipse", "category": "Shape", "isMain": "0"},
        {"actionName": "KisToolPolygon", "toolName": "Polygon Tool", "icon": "krita_tool_polygon", "category": "Shape", "isMain": "0"},
        {"actionName": "KritaShape/KisToolLine", "toolName": "Line Tool", "icon": "krita_tool_line", "category": "Shape", "isMain": "0"},
        {"actionName": "KisToolPolyline", "toolName": "Polyline Tool", "icon": "polyline", "category": "Shape", "isMain": "0"},
        {"actionName": "PanTool", "toolName": "Pan", "icon": "tool_pan", "category": "Navigation", "isMain": "1"},
        {"actionName": "ToolReferenceImages", "toolName": "Reference Image Tool", "icon": "krita_tool_reference_images", "category": "Reference", "isMain": "1"},
        {"actionName": "KisAssistantTool", "toolName": "Assistant Tool", "icon": "krita_tool_assistant", "category": "Reference", "isMain": "0"},
        {"actionName": "ZoomTool", "toolName": "Zoom Tool", "icon": "tool_zoom", "category": "Zoom", "isMain": "1"},
    ]
def normalize_tools(tools):
    """Drop malformed/duplicate entries and give every group exactly one main (visible) tool."""
    keys = ("actionName", "toolName", "icon", "category", "isMain")
    seen = set()
    result = []
    for t in tools:
        if not isinstance(t, dict) or not all(k in t for k in keys) or t["actionName"] in seen:
            continue
        seen.add(t["actionName"])
        result.append(dict(t))
    has_main = set()
    for t in result:
        if t["isMain"] == "1":
            if t["category"] in has_main:
                t["isMain"] = "0"
            else:
                has_main.add(t["category"])
    for t in result:
        if t["category"] not in has_main:
            t["isMain"] = "1"
            has_main.add(t["category"])
    return result
ToolList = []
def load_tool_list():
    global ToolList
    jm = json_class()
    data = jm.loadJSON()
    active_preset = data.get("active_preset", "Default")
    presets = data.get("presets", {})
    tools_to_load = []
    if active_preset in presets:
        tools_to_load = presets[active_preset]
    else:
        tools_to_load = get_default_tools()
        custom_tools = data.get("custom_tools", [])
        tools_to_load.extend(custom_tools)
    tools_to_load = normalize_tools(tools_to_load)
    ToolList.clear()
    ToolList.extend([ToolButton(t["actionName"], t["toolName"], t["icon"], t["category"], t["isMain"]) for t in tools_to_load])
    return ToolList
