from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import *
from krita import *
import json
from os import path
from bettertoolbox.json_class import json_class
from bettertoolbox.toolbuttons import ToolList
from bettertoolbox.tool_categories import CategoryDict, category_dictionary

class IconSelectorDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(i18n("Select Icon"))
        self.setMinimumSize(450, 400)
        self.layout = QVBoxLayout(self)
        
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.grid_widget = QWidget()
        self.grid = QGridLayout(self.grid_widget)
        self.grid.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.scroll.setWidget(self.grid_widget)
        self.layout.addWidget(self.scroll)
        
        btn_layout = QHBoxLayout()
        self.custom_btn = QPushButton(i18n("Custom Icon..."))
        self.custom_btn.setIcon(Application.icon("document-open"))
        self.custom_btn.clicked.connect(self.select_custom_icon)
        btn_layout.addWidget(self.custom_btn)
        
        self.reset_btn = QPushButton(i18n("Reset to Default"))
        self.reset_btn.clicked.connect(self.reset_icon)
        btn_layout.addWidget(self.reset_btn)
        
        self.layout.addLayout(btn_layout)
        
        self.selected_icon_name = None
        self.populate_icons()
        
    def populate_icons(self):
        main_window = Krita.instance().activeWindow()
        actions = []
        if main_window:
            actions = main_window.qwindow().findChildren(QAction)
            
        known_names = [
            "krita_tool_transform", "krita_tool_move", "tool_crop", "select", "draw-text", "shape_handling", "calligraphy",
            "krita_tool_freehand", "krita_tool_dyna", "krita_tool_multihand", "krita_tool_smart_patch", "krita_tool_freehandvector",
            "krita_tool_color_fill", "krita_tool_color_sampler", "krita_tool_lazybrush", "krita_tool_gradient",
            "krita_tool_rectangle", "krita_tool_line", "krita_tool_ellipse", "krita_tool_polygon", "polyline", "krita_draw_path",
            "tool_rect_selection", "tool_elliptical_selection", "tool_polygonal_selection", "tool_path_selection",
            "tool_outline_selection", "tool_contiguous_selection", "tool_similar_selection", "tool_magnetic_selection",
            "krita_tool_reference_images", "krita_tool_assistant", "krita_tool_measure", "tool_pan", "tool_zoom",
            "object-locked", "object-unlocked", "list-add", "edit-delete", "configure", "format-justify-fill",
            "view-sidetree", "view-list-icons", "view-list-details", "system-settings", "applications-system"
        ]
        
        icon_set = set(known_names)
        for a in actions:
            if not a.icon().isNull() and a.objectName():
                icon_set.add(a.objectName())
                
        sorted_icons = sorted(list(icon_set))
        
        row = 0
        col = 0
        max_cols = 10
        for name in sorted_icons:
            icon = Application.icon(name)
            if icon.isNull():
                action = Application.action(name)
                if action and not action.icon().isNull():
                    icon = action.icon()
                    
            if not icon.isNull():
                btn = QToolButton()
                btn.setIcon(icon)
                btn.setIconSize(QSize(24, 24))
                btn.setToolTip(name)
                btn.clicked.connect(lambda checked, n=name: self.icon_selected(n))
                self.grid.addWidget(btn, row, col)
                col += 1
                if col >= max_cols:
                    col = 0
                    row += 1
                    
    def icon_selected(self, name):
        self.selected_icon_name = name
        self.accept()
        
    def select_custom_icon(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            i18n("Select Custom Icon"),
            "",
            i18n("Images (*.png *.jpg *.jpeg *.svg *.xpm)")
        )
        if file_path:
            self.selected_icon_name = file_path
            self.accept()
            
    def reset_icon(self):
        self.selected_icon_name = "DEFAULT"
        self.accept()

class CategorySelect(QWidget):
    tools_changed = pyqtSignal()
    def __init__(self):
        super().__init__()
        self.setWindowModality(Qt.ApplicationModal)
        self.setLayout(QVBoxLayout())
        self.preset_layout = QHBoxLayout()
        self.preset_label = QLabel(i18n("Active Preset:"))
        self.preset_dropbox = QComboBox()
        self.refresh_presets()
        self.preset_dropbox.currentTextChanged.connect(self.on_preset_changed)
        self.save_preset_btn = QPushButton(i18n("Save Preset"))
        self.save_preset_btn.clicked.connect(self.save_preset)
        self.remove_preset_btn = QPushButton(i18n("Remove Preset"))
        self.remove_preset_btn.clicked.connect(self.remove_preset)
        self.preset_layout.addWidget(self.preset_label)
        self.preset_layout.addWidget(self.preset_dropbox)
        self.preset_layout.addWidget(self.save_preset_btn)
        self.preset_layout.addWidget(self.remove_preset_btn)
        self.layout().addLayout(self.preset_layout)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll_content = QWidget()
        self.scroll_content.setAcceptDrops(True)
        self.scroll_content.dragEnterEvent = self.rowDragEnterEvent
        self.scroll_content.dragMoveEvent = self.rowDragEnterEvent
        self.scroll_content.dropEvent = self.rowDropEvent
        self.subtool_column = QVBoxLayout(self.scroll_content)
        self.subtool_column.setAlignment(Qt.AlignTop)
        self.scroll.setWidget(self.scroll_content)
        self.layout().addWidget(self.scroll)
        self.config_layout = QHBoxLayout()
        self.layout().addLayout(self.config_layout)
        self.containers = {}
        self.rebuild_rows()
        self.add_category_btn = QPushButton(i18n("+ Add New Group"))
        self.add_category_btn.clicked.connect(self.add_new_category)
        self.config_layout.addWidget(self.add_category_btn)
    def refresh_presets(self):
        jm = json_class()
        data = jm.loadJSON()
        presets = data.get("presets", {})
        active = data.get("active_preset", "Default")
        self.preset_dropbox.blockSignals(True)
        self.preset_dropbox.clear()
        self.preset_dropbox.addItem("Default")
        for p in presets.keys():
            if p != "Default":
                self.preset_dropbox.addItem(p)
        index = self.preset_dropbox.findText(active)
        if index >= 0:
            self.preset_dropbox.setCurrentIndex(index)
        else:
            self.preset_dropbox.setCurrentText(active)
        self.preset_dropbox.blockSignals(False)
    def rebuild_rows(self):
        while self.subtool_column.count():
            item = self.subtool_column.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        from bettertoolbox.toolbuttons import ToolList
        from bettertoolbox.tool_categories import category_dictionary, ToolCategory
        ordered_categories = []
        for t in ToolList:
            if t.category not in ordered_categories:
                ordered_categories.append(t.category)
        self.containers = {}
        for category in ordered_categories:
            container = Container(category)
            self.containers[category] = container
            row = GroupRow(category, container, self.subtool_column, self.open_add_tool_dialog, self.remove_category)
            self.subtool_column.addWidget(row)
        for ToolBtn in ToolList:
            tool_panel = ToolPanel(ToolBtn)
            if ToolBtn.category in self.containers:
                if ToolBtn.isMain == "1":
                    self.containers[ToolBtn.category].layout().addWidget(tool_panel)
                    self.containers[ToolBtn.category].layout().addWidget(QVSeparationLine())
                else:
                    self.containers[ToolBtn.category].layout().addWidget(tool_panel)
    def on_preset_changed(self, index=None):
        preset_name = self.preset_dropbox.currentText()
        if not preset_name: return
        jm = json_class()
        jm.update_dict({"active_preset": preset_name})
        jm.dumpJSON()
        from bettertoolbox import toolbuttons
        toolbuttons.ToolList = toolbuttons.load_tool_list()
        self.rebuild_rows()
        self.tools_changed.emit()
    def save_preset(self, show_msg=True):
        preset_name = self.preset_dropbox.currentText()
        if not preset_name:
            if show_msg:
                QMessageBox.warning(self, "No Name", "Please enter a preset name.")
            return
        new_tool_data = []
        for i in range(self.subtool_column.count()):
            row = self.subtool_column.itemAt(i).widget()
            if isinstance(row, GroupRow):
                category = row.category
                container = row.container
                for j in range(container.layout().count()):
                    w = container.layout().itemAt(j).widget()
                    if isinstance(w, ToolPanel):
                        is_main = "1"
                        if j + 1 < container.layout().count():
                            next_w = container.layout().itemAt(j+1).widget()
                            if not isinstance(next_w, QVSeparationLine):
                                is_main = "0"
                        else:
                            is_main = "0"
                        new_tool_data.append({
                            "actionName": w.tool_btn.actionName,
                            "toolName": w.tool_btn.toolName,
                            "icon": w.tool_btn.iconName,
                            "category": category,
                            "isMain": is_main
                        })
        jm = json_class()
        data = jm.loadJSON()
        presets = data.get("presets", {})
        presets[preset_name] = new_tool_data
        jm.update_dict({"presets": presets, "active_preset": preset_name})
        jm.dumpJSON()
        self.refresh_presets()
        self.tools_changed.emit()
        if show_msg:
            QMessageBox.information(self, "Saved", f"Preset '{preset_name}' saved.")
    def remove_preset(self):
        preset_name = self.preset_dropbox.currentText()
        if not preset_name or preset_name == "Default":
            QMessageBox.warning(self, i18n("Cannot Remove"), i18n("You cannot remove the 'Default' preset."))
            return
        reply = QMessageBox.question(self, i18n("Confirm Delete"), 
                                     i18n(f"Are you sure you want to delete the preset '{preset_name}'?"), 
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            jm = json_class()
            data = jm.loadJSON()
            presets = data.get("presets", {})
            if preset_name in presets:
                del presets[preset_name]
                jm.update_dict({"presets": presets, "active_preset": "Default"})
                jm.dumpJSON()
                self.refresh_presets()
                self.on_preset_changed()
                QMessageBox.information(self, i18n("Deleted"), i18n(f"Preset '{preset_name}' has been deleted."))
    def add_new_category(self):
        text, ok = QInputDialog.getText(self, i18n("New Group"), i18n("Enter new group name:"))
        if ok and text and text not in self.containers:
            new_container = Container(text)
            self.containers[text] = new_container
            row = GroupRow(text, new_container, self.subtool_column, self.open_add_tool_dialog, self.remove_category)
            self.subtool_column.addWidget(row)
    def remove_category(self, category):
        if category in self.containers:
            del self.containers[category]
    def open_add_tool_dialog(self, target_group=None):
        self.save_preset(show_msg=False)
        from bettertoolbox.add_tool import AddToolDialog
        from bettertoolbox.toolbuttons import ToolButton
        dialog = AddToolDialog(self, default_group=target_group)
        if dialog.exec_() == QDialog.Accepted:
            from bettertoolbox import toolbuttons
            toolbuttons.ToolList = toolbuttons.load_tool_list()
            self.rebuild_rows()
            self.tools_changed.emit()
        dialog.deleteLater()
    def rowDragEnterEvent(self, event):
        if event.mimeData().hasFormat("application/x-grouprow"):
            event.accept()
    def rowDropEvent(self, event):
        source = event.source()
        if isinstance(source, GroupRow):
            pos = event.pos()
            index = 0
            for i in range(self.subtool_column.count()):
                w = self.subtool_column.itemAt(i).widget()
                if w and pos.y() > w.y() + w.height() / 2:
                    index = i + 1
            self.subtool_column.insertWidget(index, source)
            event.setDropAction(Qt.MoveAction)
            event.accept()
class DragHandle(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setPixmap(Application.icon("format-justify-fill").pixmap(16, 16))
        self.setCursor(Qt.SizeVerCursor)
        self.setFixedSize(24, 40)
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet("background: rgba(255,255,255,10); border-radius: 4px;")
    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton:
            drag = QDrag(self.parent())
            mimeData = QMimeData()
            mimeData.setData("application/x-grouprow", b"1")
            drag.setMimeData(mimeData)
            pixmap = self.parent().grab()
            drag.setPixmap(pixmap)
            drag.setHotSpot(event.pos())
            self.parent().setOpacity(0.5)
            drag.exec_(Qt.MoveAction)
            self.parent().setOpacity(1.0)
class GroupRow(QFrame):
    def __init__(self, category, container, parent_layout, add_callback, remove_callback=None):
        super().__init__()
        self.category = category
        self.container = container
        self.parent_layout = parent_layout
        self.remove_callback = remove_callback
        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet("GroupRow { background: rgba(0,0,0,20); border-radius: 6px; margin-bottom: 2px; }")
        self.main_layout = QHBoxLayout(self)
        self.main_layout.setContentsMargins(4, 4, 4, 4)
        self.handle = DragHandle(self)
        self.main_layout.addWidget(self.handle)
        self.main_layout.addWidget(container)
        self.add_btn = QToolButton()
        self.add_btn.setIcon(Application.icon("list-add"))
        self.add_btn.setToolTip(i18n("Add tool to this group"))
        self.add_btn.clicked.connect(lambda: add_callback(self.category))
        self.main_layout.addWidget(self.add_btn)
        self.remove_btn = QToolButton()
        self.remove_btn.setIcon(Application.icon("edit-delete"))
        self.remove_btn.setToolTip(i18n("Remove entire group"))
        self.remove_btn.clicked.connect(self.remove_group)
        self.main_layout.addWidget(self.remove_btn)
    def remove_group(self):
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Warning)
        msg.setWindowTitle(i18n("Remove Group"))
        msg.setText(i18n("Are you sure you want to remove the group '%s'?") % self.category)
        msg.setInformativeText(i18n("This will remove all tools within this group from the current preset."))
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg.setDefaultButton(QMessageBox.No)
        if msg.exec_() == QMessageBox.Yes:
            if self.remove_callback:
                self.remove_callback(self.category)
            self.setParent(None)
            self.deleteLater()
    def setOpacity(self, opacity):
        self.setWindowOpacity(opacity) 
        if opacity < 1.0:
            self.setStyleSheet("GroupRow { background: rgba(255,255,255,20); border: 1px dashed gray; }")
        else:
            self.setStyleSheet("GroupRow { background: rgba(0,0,0,20); border-radius: 6px; margin-bottom: 2px; }")
class Container(QFrame):
    def __init__(self, name):
        super().__init__()
        self.name = name
        self.setFrameShape(QFrame.StyledPanel)
        self.setFrameShadow(QFrame.Sunken)
        self.setLayout(QHBoxLayout())
        self.layout().setAlignment(Qt.AlignLeft)
        self.setAcceptDrops(True)
    def dragEnterEvent(self, event):
        event.accept()
    def dropEvent(self, event):
        source = event.source()
        if isinstance(source, ToolPanel):
            pos = event.pos()
            layout = self.layout()
            tools = []
            separator = None
            for i in range(layout.count()):
                w = layout.itemAt(i).widget()
                if isinstance(w, ToolPanel):
                    if w != source: 
                        tools.append(w)
                elif isinstance(w, QVSeparationLine):
                    separator = w
            insertion_idx = 0
            for i, tool in enumerate(tools):
                if pos.x() > tool.x() + tool.width() / 2:
                    insertion_idx = i + 1
            tools.insert(insertion_idx, source)
            source.setParent(self)
            while layout.count():
                layout.takeAt(0)
            if tools:
                layout.addWidget(tools[0])
                if not separator:
                    separator = QVSeparationLine()
                layout.addWidget(separator)
                for tool in tools[1:]:
                    layout.addWidget(tool)
            event.setDropAction(Qt.MoveAction)
            event.accept()
    def normalize_layout(self):
        layout = self.layout()
        tools = []
        separator = None
        for i in range(layout.count()):
            w = layout.itemAt(i).widget()
            if isinstance(w, ToolPanel):
                tools.append(w)
            elif isinstance(w, QVSeparationLine):
                separator = w
        while layout.count():
            layout.takeAt(0)
        if tools:
            layout.addWidget(tools[0])
            if not separator:
                separator = QVSeparationLine()
            layout.addWidget(separator)
            for tool in tools[1:]:
                layout.addWidget(tool)
        elif separator:
            separator.deleteLater()
class QVSeparationLine(QFrame):
    def __init__(self):
        super().__init__()
        self.setFixedWidth(20)
        self.setFrameShape(QFrame.VLine)
        self.setFrameShadow(QFrame.Sunken)
class ToolPanel(QToolButton):
    def __init__(self, tool_btn):
        super().__init__()
        self.tool_btn = tool_btn
        self.setIcon(tool_btn.icon())
        self.setToolTip(tool_btn.toolName)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
    def showEvent(self, event):
        super().showEvent(event)
        if self.icon().isNull() or self.iconSize().width() < 16:
            if not self.tool_btn.icon().isNull():
                self.setIcon(self.tool_btn.icon())
            else:
                self.tool_btn.showEvent(None)
                self.setIcon(self.tool_btn.icon())
    def show_context_menu(self, pos):
        menu = QMenu(self)
        remove_action = menu.addAction(i18n("Remove Tool"))
        custom_icon_action = menu.addAction(i18n("Change icon"))
        action = menu.exec_(self.mapToGlobal(pos))
        if action == remove_action:
            container = self.parentWidget()
            self.setParent(None)
            self.deleteLater()
            if isinstance(container, Container):
                container.normalize_layout()
        elif action == custom_icon_action:
            dialog = IconSelectorDialog(self)
            if dialog.exec_() == QDialog.Accepted:
                if dialog.selected_icon_name:
                    if dialog.selected_icon_name == "DEFAULT":
                        from bettertoolbox.toolbuttons import get_default_tools
                        defaults = get_default_tools()
                        original = next((t["icon"] for t in defaults if t["actionName"] == self.tool_btn.actionName), None)
                        if original:
                            self.tool_btn.iconName = original
                        else:
                            self.tool_btn.iconName = self.tool_btn.actionName
                    else:
                        self.tool_btn.iconName = dialog.selected_icon_name
                        
                    self.tool_btn.setIcon(QIcon())
                    self.tool_btn._load_icon()
                    self.setIcon(self.tool_btn.icon())
        menu.deleteLater()
    def mouseMoveEvent(self, event):
        if event.buttons() != Qt.LeftButton:
            return
        drag = QDrag(self)
        mimeData = QMimeData()
        drag.setMimeData(mimeData)
        container = self.parentWidget()
        drag.exec_(Qt.MoveAction)
        if isinstance(container, Container):
            container.normalize_layout()
