from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import *
from krita import *
from bettertoolbox.json_class import json_class
class AddToolDialog(QDialog):
    def __init__(self, parent=None, default_group=None):
        super().__init__(parent)
        self.setWindowTitle(i18n("Add Custom Tool"))
        self.setMinimumSize(400, 500)
        self.layout = QVBoxLayout(self)
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText(i18n("Search action by name or description..."))
        self.search_bar.textChanged.connect(self.filter_actions)
        self.layout.addWidget(self.search_bar)
        self.list_widget = QListWidget()
        self.layout.addWidget(self.list_widget)
        self.group_layout = QHBoxLayout()
        self.group_label = QLabel(i18n("Assign to Group:"))
        self.group_input = QComboBox()
        self.group_input.setEditable(True)
        from bettertoolbox.tool_categories import CategoryDict
        for cat in CategoryDict().categories.keys():
            self.group_input.addItem(cat)
        if default_group:
            self.group_input.setCurrentText(default_group)
        self.group_layout.addWidget(self.group_label)
        self.group_layout.addWidget(self.group_input)
        self.layout.addLayout(self.group_layout)
        self.show_no_icon_checkbox = QCheckBox(i18n("Show all tools"))
        self.show_no_icon_checkbox.setChecked(False)
        self.show_no_icon_checkbox.stateChanged.connect(self.populate_actions)
        self.layout.addWidget(self.show_no_icon_checkbox)
        self.button_layout = QHBoxLayout()
        self.save_button = QPushButton(i18n("Add Tool"))
        self.save_button.clicked.connect(self.save_tool)
        self.cancel_button = QPushButton(i18n("Cancel"))
        self.cancel_button.clicked.connect(self.reject)
        self.button_layout.addWidget(self.save_button)
        self.button_layout.addWidget(self.cancel_button)
        self.layout.addLayout(self.button_layout)
        self.actions_data = []
        self.populate_actions()
    def populate_actions(self):
        self.list_widget.clear()
        self.actions_data.clear()
        show_all = self.show_no_icon_checkbox.isChecked()
        for action in Application.actions():
            if not action.objectName():
                continue
            icon = action.icon()
            if not show_all and icon.isNull():
                continue
            name = action.text().replace("&", "")
            desc = action.toolTip()
            self.actions_data.append({
                "actionName": action.objectName(),
                "name": name,
                "desc": desc,
                "icon": icon,
            })
            item = QListWidgetItem()
            item.setIcon(icon)
            text = f"{name}"
            if desc and desc != name:
                text += f" - {desc}"
            item.setText(text)
            item.setData(Qt.UserRole, action.objectName())
            self.list_widget.addItem(item)
    def filter_actions(self, text):
        text = text.lower()
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            action_id = item.data(Qt.UserRole)
            action_info = next((a for a in self.actions_data if a["actionName"] == action_id), None)
            if action_info:
                match = text in action_info["name"].lower() or text in action_info["desc"].lower()
                item.setHidden(not match)
    def save_tool(self):
        selected = self.list_widget.selectedItems()
        if not selected:
            QMessageBox.warning(self, i18n("No Action Selected"), i18n("Please select an action from the list."))
            return
        item = selected[0]
        action_name = item.data(Qt.UserRole)
        action_info = next(a for a in self.actions_data if a["actionName"] == action_name)
        group = self.group_input.currentText().strip()
        if not group:
            QMessageBox.warning(self, i18n("No Group"), i18n("Please specify a group."))
            return
        jm = json_class()
        disk_data = jm.loadJSON()
        custom_tools = disk_data.get("custom_tools", [])
        icon_name = action_info["icon"].name()
        if not icon_name:
            icon_name = action_name
        from bettertoolbox.toolbuttons import ToolList
        has_main = any(t.category == group and t.isMain == "1" for t in ToolList)
        is_main = "0" if has_main else "1"
        new_tool = {
            "actionName": action_name,
            "toolName": action_info["name"],
            "icon": icon_name,
            "category": group,
            "isMain": is_main
        }
        custom_tools = [ct for ct in custom_tools if ct["actionName"] != action_name]
        custom_tools.append(new_tool)
        updates = {"custom_tools": custom_tools}
        active_preset = disk_data.get("active_preset", "Default")
        presets = disk_data.get("presets", {})
        if active_preset in presets:
            preset_tools = presets[active_preset]
            preset_tools = [pt for pt in preset_tools if pt["actionName"] != action_name]
            preset_tools.append(new_tool)
            presets[active_preset] = preset_tools
            updates["presets"] = presets
        jm.update_dict(updates)
        jm.dumpJSON()
        self.accept()
