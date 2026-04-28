import json
from os import path
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import *
from krita import *
from bettertoolbox.json_class import json_class
from bettertoolbox import toolbuttons
from bettertoolbox.toolbuttons import ToolButton
from bettertoolbox.tool_categories import CategoryDict, ToolCategory, category_dictionary
from bettertoolbox.flow_layout import FlowLayout
from bettertoolbox.category_select import CategorySelect
from bettertoolbox.add_tool import AddToolDialog
DOCKER_actionName = "BetterToolbox"
DOCKER_ID = "pykrita_bettertoolbox"
jsonMethod = json_class()
menu_delayValue = jsonMethod.loadJSON().get("delayValue", 200)
menu_iconSizeValue = jsonMethod.loadJSON().get("iconSize", 18)

class TKStyle(QProxyStyle):
    def styleHint(self, element, option, widget, returnData):
        if element == QStyle.SH_ToolButton_PopupDelay:
            return 100
        return super().styleHint(element, option, widget, returnData)
    def drawPrimitive(self, element, option, painter, widget):
        if element == QStyle.PE_IndicatorArrowDown:
            adjusted_point = QPoint(0, 5)
            triangle = QPainterPath()
            startPoint = option.rect.bottomRight() - adjusted_point
            triangle.moveTo(startPoint)
            triangle.lineTo(startPoint + QPoint(0, 5))
            triangle.lineTo(startPoint + QPoint(-5, 5))
            painter.fillPath(triangle, Qt.white)
        else:
            super().drawPrimitive(element, option, painter, widget)

_tk_style = None

class Menu(QMenu):
    def __init__(self, parent_btn):
        super().__init__(parent_btn)
        self.parent_btn = parent_btn
        self.setMouseTracking(True)
    def showEvent(self, event):
        super().showEvent(event)
        wh = self.parent_btn.windowHandle()
        if wh:
            self.windowHandle().setScreen(wh.screen())
        
        ideal_pos = self.parent_btn.mapToGlobal(QPoint(self.parent_btn.width(), 0))
        screen = QApplication.screenAt(ideal_pos)
        if not screen and wh:
            screen = wh.screen()
            
        if screen:
            screen_rect = screen.availableGeometry()
            menu_size = self.sizeHint()
            
            if ideal_pos.x() + menu_size.width() > screen_rect.right():
                ideal_pos.setX(self.parent_btn.mapToGlobal(QPoint(0, 0)).x() - menu_size.width())
                
            if ideal_pos.y() + menu_size.height() > screen_rect.bottom():
                ideal_pos.setY(screen_rect.bottom() - menu_size.height())
                
        self.move(ideal_pos)
    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)
        buttonTLC = self.parent_btn.mapToGlobal(QPoint(0, 0))
        menuSize = QSize(self.geometry().size())
        buttonColumn = QRect(buttonTLC, menuSize)
        bounds = self.geometry().united(buttonColumn)
        if not bounds.contains(QCursor.pos()):
            self.close()

class ActionButton(QToolButton):
    def __init__(self, icon_names, tooltip, callback):
        super().__init__()
        self.icon_names = icon_names if isinstance(icon_names, list) else [icon_names]
        self.setToolTip(tooltip)
        self.clicked.connect(callback)

    def showEvent(self, event):
        super().showEvent(event)
        if self.icon().isNull():
            for name in self.icon_names:
                icon = Application.icon(name)
                if not icon.isNull():
                    self.setIcon(icon)
                    return
            if "Toolbox" in self.toolTip():
                self.setIcon(Application.icon("format-justify-fill"))
            else:
                self.setIcon(Application.icon("configure"))

class SettingsWidget(QWidget):
    def __init__(self, parent, docker):
        super(SettingsWidget, self).__init__(parent)
        self.docker = docker
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        self.original_data = jsonMethod.loadJSON().copy()

        self.tabs = QTabWidget()
        self.tab1 = QWidget()
        self.tab2 = QWidget()
        self.tab1.layout = QVBoxLayout(self.tab1)
        self.tab1.layout.setContentsMargins(6, 6, 6, 6)
        self.tab2.layout = QVBoxLayout(self.tab2)
        self.tab2.layout.setContentsMargins(10, 10, 10, 10)
        self.tab2.layout.setSpacing(6)
        self.tabs.addTab(self.tab1, "Tools")
        self.tabs.addTab(self.tab2, "Layout")
        self.category_select = CategorySelect()
        self.tab1.layout.addWidget(self.category_select)

        data = self.original_data

        # ── Size Section ──
        size_header = QLabel("Size")
        size_header.setStyleSheet("font-weight: bold; font-size: 11px; color: #aaa; padding: 2px 0;")
        self.tab2.layout.addWidget(size_header)

        size_grid = QGridLayout()
        size_grid.setContentsMargins(0, 0, 0, 0)
        size_grid.setVerticalSpacing(4)
        size_grid.setHorizontalSpacing(6)

        icon_lbl = QLabel(i18n("Icon"))
        icon_lbl.setStyleSheet("font-size: 11px;")
        self.iconSizeSlider = QSlider(Qt.Horizontal)
        self.iconSizeSlider.setRange(10, 64)
        self.iconSizeSlider.setValue(data.get("iconSize", 18))
        self.iconSizeLabel = QLabel(f'{self.iconSizeSlider.value()}px')
        self.iconSizeLabel.setMinimumWidth(28)
        self.iconSizeLabel.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.iconSizeLabel.setStyleSheet("font-size: 10px; color: #888;")

        btn_lbl = QLabel(i18n("Button"))
        btn_lbl.setStyleSheet("font-size: 11px;")
        self.btnSizeSlider = QSlider(Qt.Horizontal)
        self.btnSizeSlider.setRange(10, 80)
        self.btnSizeSlider.setValue(data.get("btnSize", 28))
        self.btnSizeLabel = QLabel(f'{self.btnSizeSlider.value()}px')
        self.btnSizeLabel.setMinimumWidth(28)
        self.btnSizeLabel.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.btnSizeLabel.setStyleSheet("font-size: 10px; color: #888;")

        self.lockBtn = QToolButton()
        self.lockBtn.setFixedSize(24, 24)
        icon = Application.icon("object-locked")
        if icon.isNull():
            self.lockBtn.setText("🔒")
        else:
            self.lockBtn.setIcon(icon)
        self.lockBtn.setCheckable(True)
        self.lockBtn.setChecked(data.get("sizeLocked", True))
        self.lockBtn.setToolTip(i18n("Lock icon/button size ratio"))
        self.size_offset = self.btnSizeSlider.value() - self.iconSizeSlider.value()

        self.iconSizeSlider.valueChanged.connect(self.on_icon_size_changed)
        self.btnSizeSlider.valueChanged.connect(self.on_btn_size_changed)
        self.lockBtn.toggled.connect(self.on_lock_toggled)

        size_grid.addWidget(icon_lbl, 0, 0)
        size_grid.addWidget(self.iconSizeSlider, 0, 1)
        size_grid.addWidget(self.iconSizeLabel, 0, 2)
        size_grid.addWidget(self.lockBtn, 0, 3, 2, 1, Qt.AlignCenter)
        size_grid.addWidget(btn_lbl, 1, 0)
        size_grid.addWidget(self.btnSizeSlider, 1, 1)
        size_grid.addWidget(self.btnSizeLabel, 1, 2)
        size_grid.setColumnStretch(1, 1)
        self.tab2.layout.addLayout(size_grid)

        # ── Separator ──
        sep1 = QFrame()
        sep1.setFrameShape(QFrame.HLine)
        sep1.setStyleSheet("color: rgba(255,255,255,15);")
        self.tab2.layout.addWidget(sep1)

        # ── Floating Section ──
        float_header = QLabel("Floating Layout")
        float_header.setStyleSheet("font-weight: bold; font-size: 11px; color: #aaa; padding: 2px 0;")
        self.tab2.layout.addWidget(float_header)
        self.float_header = float_header

        # Spacing
        spacing_row = QHBoxLayout()
        spacing_row.setContentsMargins(0, 0, 0, 0)
        spacing_lbl = QLabel(i18n("Spacing"))
        spacing_lbl.setStyleSheet("font-size: 11px;")
        self.spacingSlider = QSlider(Qt.Horizontal)
        self.spacingSlider.setRange(0, 30)
        self.spacingSlider.setValue(data.get("spacing", 6))
        self.spacingLabel = QLabel(f'{self.spacingSlider.value()}px')
        self.spacingLabel.setMinimumWidth(28)
        self.spacingLabel.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.spacingLabel.setStyleSheet("font-size: 10px; color: #888;")
        self.spacingSlider.valueChanged.connect(self.on_spacing_changed)
        spacing_row.addWidget(spacing_lbl)
        spacing_row.addWidget(self.spacingSlider, 1)
        spacing_row.addWidget(self.spacingLabel)
        self.spacingWidget = QWidget()
        self.spacingWidget.setLayout(spacing_row)
        self.tab2.layout.addWidget(self.spacingWidget)

        # Orientation
        orient_row = QHBoxLayout()
        orient_row.setContentsMargins(0, 0, 0, 0)
        orient_lbl = QLabel(i18n("Direction"))
        orient_lbl.setStyleSheet("font-size: 11px;")

        self.orientationGroup = QButtonGroup(self)
        self.horizontalRadio = QRadioButton(i18n("Horizontal"))
        self.verticalRadio = QRadioButton(i18n("Vertical"))
        self.horizontalRadio.setStyleSheet("font-size: 11px;")
        self.verticalRadio.setStyleSheet("font-size: 11px;")
        self.orientationGroup.addButton(self.horizontalRadio)
        self.orientationGroup.addButton(self.verticalRadio)

        orientation = data.get("orientation", "Horizontal")
        if orientation == "Vertical":
            self.verticalRadio.setChecked(True)
        else:
            self.horizontalRadio.setChecked(True)

        orient_row.addWidget(orient_lbl)
        orient_row.addStretch()
        orient_row.addWidget(self.horizontalRadio)
        orient_row.addWidget(self.verticalRadio)
        self.orientationWidget = QWidget()
        self.orientationWidget.setLayout(orient_row)
        self.tab2.layout.addWidget(self.orientationWidget)

        self.floatingNotice = QLabel(i18n("⬆ Floating options appear when the toolbar is undocked."))
        self.floatingNotice.setStyleSheet("color: #666; font-size: 10px; font-style: italic; padding: 4px 0;")
        self.floatingNotice.setWordWrap(True)
        self.tab2.layout.addWidget(self.floatingNotice)

        self.tab2.layout.addStretch()

        self.layout.addWidget(self.tabs)

        # ── Footer ──
        footer = QHBoxLayout()
        footer.setContentsMargins(10, 6, 10, 8)
        footer.addStretch()
        self.cancelButton = QPushButton(i18n("Cancel"))
        self.cancelButton.setFixedWidth(80)
        self.cancelButton.clicked.connect(self.cancelSettings)
        self.acceptButton = QPushButton(i18n("OK"))
        self.acceptButton.setFixedWidth(80)
        self.acceptButton.setDefault(True)
        self.acceptButton.clicked.connect(self.updateSettingsAccept)
        footer.addWidget(self.cancelButton)
        footer.addWidget(self.acceptButton)
        self.layout.addLayout(footer)
        self.setLayout(self.layout)

    def cancelSettings(self):
        from bettertoolbox import toolbuttons
        toolbuttons.ToolList = toolbuttons.load_tool_list()
        self.parentWidget().close()
        QTimer.singleShot(0, self.docker.setupLayout)

    def on_spacing_changed(self, value):
        self.spacingLabel.setText(f"{value}px")

    def on_lock_toggled(self, checked):
        if checked:
            icon = Application.icon("object-locked")
            if icon.isNull(): self.lockBtn.setText("🔒")
            else: self.lockBtn.setIcon(icon)
            self.size_offset = self.btnSizeSlider.value() - self.iconSizeSlider.value()
        else:
            icon = Application.icon("object-unlocked")
            if icon.isNull(): self.lockBtn.setText("🔓")
            else: self.lockBtn.setIcon(icon)

    def on_icon_size_changed(self, value):
        self.iconSizeLabel.setText(f"{value}px")
        if self.lockBtn.isChecked():
            self.btnSizeSlider.blockSignals(True)
            new_btn = max(self.btnSizeSlider.minimum(), min(self.btnSizeSlider.maximum(), value + self.size_offset))
            self.btnSizeSlider.setValue(new_btn)
            self.btnSizeLabel.setText(f"{new_btn}px")
            self.btnSizeSlider.blockSignals(False)

    def on_btn_size_changed(self, value):
        self.btnSizeLabel.setText(f"{value}px")
        if self.lockBtn.isChecked():
            self.iconSizeSlider.blockSignals(True)
            new_icon = max(self.iconSizeSlider.minimum(), min(self.iconSizeSlider.maximum(), value - self.size_offset))
            self.iconSizeSlider.setValue(new_icon)
            self.iconSizeLabel.setText(f"{new_icon}px")
            self.iconSizeSlider.blockSignals(False)

    def update_visibility(self):
        is_float = self.docker.isFloating()
        show_float = is_float
        self.float_header.setVisible(show_float)
        self.orientationWidget.setVisible(show_float)
        self.spacingWidget.setVisible(show_float)
        self.floatingNotice.setVisible(not show_float)
        self.btnSizeSlider.setEnabled(show_float)
        self.lockBtn.setEnabled(show_float)
        if not show_float:
            self.btnSizeLabel.setText("auto")

    def updateSettingsAccept(self):
        self.category_select.save_preset(show_msg=False)
        jsonMethod.update_dict({
            "iconSize": self.iconSizeSlider.value(),
            "btnSize": self.btnSizeSlider.value(),
            "sizeLocked": self.lockBtn.isChecked(),
            "spacing": self.spacingSlider.value(),
            "orientation": "Vertical" if self.verticalRadio.isChecked() else "Horizontal"
        })
        from bettertoolbox import toolbuttons
        toolbuttons.load_tool_list()
        self.parentWidget().close()
        QTimer.singleShot(0, self.docker.setupLayout)

DIALOG_STYLE = """
QDialog {
    background: #2b2b2b;
}
QTabWidget::pane {
    border: 1px solid #3a3a3a;
    border-radius: 4px;
    background: #2b2b2b;
}
QTabBar::tab {
    background: #333;
    color: #aaa;
    padding: 6px 18px;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    margin-right: 2px;
}
QTabBar::tab:selected {
    background: #2b2b2b;
    color: #ddd;
    border-bottom: 2px solid #5599dd;
}
QSlider::groove:horizontal {
    height: 4px;
    background: #444;
    border-radius: 2px;
}
QSlider::handle:horizontal {
    background: #5599dd;
    width: 12px;
    height: 12px;
    margin: -4px 0;
    border-radius: 6px;
}
QSlider::handle:horizontal:hover {
    background: #66aaee;
}
QPushButton {
    background: #3a3a3a;
    color: #ccc;
    border: 1px solid #4a4a4a;
    border-radius: 4px;
    padding: 4px 12px;
}
QPushButton:hover {
    background: #454545;
    border-color: #5599dd;
}
QPushButton:default {
    background: #3a5577;
    border-color: #5599dd;
    color: #eee;
}
QPushButton:default:hover {
    background: #4a6688;
}
QRadioButton {
    spacing: 4px;
}
QRadioButton::indicator {
    width: 12px;
    height: 12px;
}
QComboBox {
    background: #333;
    border: 1px solid #4a4a4a;
    border-radius: 3px;
    padding: 3px 6px;
    color: #ccc;
}
QComboBox:hover {
    border-color: #5599dd;
}
QScrollArea {
    border: 1px solid #3a3a3a;
    border-radius: 4px;
}
QToolButton {
    background: transparent;
    border: 1px solid transparent;
    border-radius: 3px;
    padding: 2px;
}
QToolButton:hover {
    background: rgba(255,255,255,15);
    border-color: #4a4a4a;
}
"""

class SDialog(QDialog):
    def __init__(self, docker):
        super().__init__()
        self.docker = docker
        self.setWindowTitle("BetterToolBox Settings")
        self.setWindowModality(Qt.ApplicationModal)
        self.setMinimumSize(680, 540)
        self.setStyleSheet(DIALOG_STYLE)
        SLayout = QVBoxLayout(self)
        SLayout.setContentsMargins(6, 6, 6, 0)
        self.settings_widget = SettingsWidget(self, docker)
        SLayout.addWidget(self.settings_widget)

    def exec_(self):
        self.settings_widget.update_visibility()
        return super().exec_()

class bettertoolbox(QDockWidget):
    activate_layout = pyqtSignal()
    def __init__(self):
        super().__init__()
        
        global _tk_style
        if _tk_style is None:
            _tk_style = TKStyle("fusion")
        
        self.setFloating(False)
        self.setWindowTitle('BetterToolBox')
        self.mainToolButtons = QButtonGroup()
        self.mainToolButtons.setExclusive(True)
        self.widget = QWidget()
        self.widget.setObjectName("MainContainer")
        self.widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.title_label = QLabel(" ")
        self.title_label.setFrameShape(QFrame.StyledPanel)
        self.title_label.setFrameShadow(QFrame.Raised)
        self.title_label.setFrameStyle(QFrame.Panel | QFrame.Raised)
        self.title_label.setMinimumWidth(16)
        self.title_label.setFixedHeight(12)
        self.setWidget(self.widget)
        self.setTitleBarWidget(self.title_label)
        self.main_layout = QBoxLayout(QBoxLayout.TopToBottom, self.widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        self.toolbox_btn = ActionButton(
            ["view-list-icons", "view-sidetree", "view-list-details", "format-justify-fill"],
            i18n("Toggle Krita Toolbox"),
            self.toggle_standard_toolbox
        )
        self.toolbox_btn.setStyle(_tk_style)

        self.settings_btn = ActionButton(
            ["settings-configure", "preferences-system", "system-settings", "applications-system", "system-run", "configure"],
            i18n("BetterToolBox Settings"),
            self.open_settings
        )
        self.settings_btn.setStyle(_tk_style)

        self.tools_container = QWidget()
        self.tools_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.tools_layout = FlowLayout(spacing=6)
        self.tools_container.setLayout(self.tools_layout)
        self.main_layout.addWidget(self.tools_container)
        self.main_layout.addStretch()

        self._drag_start_pos = None
        self._drag_timer = QTimer(self)
        self._drag_timer.setSingleShot(True)
        self._drag_timer.setInterval(200)
        self._drag_timer.timeout.connect(self._start_drag)
        self._is_dragging = False
        self._applying_styles = False

        self.installEventFilter(self)

        if not toolbuttons.ToolList:
            toolbuttons.load_tool_list()

        for tb in toolbuttons.ToolList:
            if tb.category not in category_dictionary.categories:
                category_dictionary.categories[tb.category] = ToolCategory(tb.category)
            category_dictionary.categories[tb.category].addTool(tb)
            tb.setParent(self)
            tb.setStyle(_tk_style)
            tb.clicked.connect(self.activateTool)
        self.activate_layout.connect(self.setupLayout)
        self.topLevelChanged.connect(self.on_float_changed)
        self.dockLocationChanged.connect(self.on_dock_location_changed)
        QTimer.singleShot(0, self.activate_layout.emit)

    def on_dock_location_changed(self, area):
        self.setupLayout()

    def is_horizontal_dock(self):
        if self.isFloating():
            return False
        main_window = Krita.instance().activeWindow()
        if main_window and main_window.qwindow():
            area = main_window.qwindow().dockWidgetArea(self)
            return area in (Qt.TopDockWidgetArea, Qt.BottomDockWidgetArea)
        return False

    def on_float_changed(self, is_float):
        if is_float:
            jsonMethod.update_dict({"modern": True})
        else:
            jsonMethod.update_dict({"modern": False, "orientation": "Vertical"})
            # Immediately reset floating-mode state before Krita settles dock geometry
            self.setAttribute(Qt.WA_TranslucentBackground, False)
            self.widget.setStyleSheet("")
            self.widget.layout().setSizeConstraint(QLayout.SetDefaultConstraint)
            self.title_label.setFixedHeight(12)
            self.title_label.setFrameShape(QFrame.StyledPanel)
            self.title_label.setFrameStyle(QFrame.Panel | QFrame.Raised)
            self.title_label.setStyleSheet("")
            for btn in self.tools_container.findChildren(QToolButton):
                btn.setStyleSheet("")
        self.setupLayout()

    def eventFilter(self, obj, event):
        if self.isFloating() and isinstance(obj, QToolButton) and self.tools_container.isAncestorOf(obj):
            if event.type() == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
                self._drag_start_pos = event.globalPos()
                self._drag_timer.start()
                self._is_dragging = False
            elif event.type() == QEvent.MouseMove and self._drag_start_pos is not None:
                if self._is_dragging:
                    delta = event.globalPos() - self._drag_start_pos
                    self.move(self.pos() + delta)
                    self._drag_start_pos = event.globalPos()
                    return True
            elif event.type() == QEvent.MouseButtonRelease:
                was_dragging = self._is_dragging
                self._drag_timer.stop()
                self._drag_start_pos = None
                self._is_dragging = False
                if was_dragging:
                    self._check_dock_proximity()
                    return True
        return super().eventFilter(obj, event)

    def _start_drag(self):
        if self._drag_start_pos is not None:
            self._is_dragging = True

    def _check_dock_proximity(self):
        cursor = QCursor.pos()
        main_window = Krita.instance().activeWindow()
        if not main_window:
            return
        qwin = main_window.qwindow()
        win_rect = qwin.geometry()
        dock_margin = 40
        if cursor.x() <= win_rect.left() + dock_margin or cursor.x() >= win_rect.right() - dock_margin:
            self.setFloating(False)

    def open_settings(self):
        dialog = SDialog(self)
        dialog.exec_()

    def activateTool(self):
        sender = self.sender()
        if not sender:
            return
        actionName = sender.objectName()
        ac = Application.action(actionName)
        if ac:
            ac.trigger()

    def linkMenu(self):
        subMenu = self.sender()
        if not subMenu:
            return
        if subMenu.isEmpty():
            categoryName = subMenu.parent_btn.category
            if categoryName not in category_dictionary.categories:
                return
            category = category_dictionary.categories[categoryName]
            for key in category.ToolButtons:
                toolBtn = category.ToolButtons[key]
                toolIcon = toolBtn.icon()
                toolText = toolBtn.toolName
                toolName = toolBtn.actionName
                if toolIcon.isNull():
                    action = Application.action(toolName)
                    if action and not action.icon().isNull():
                        toolIcon = action.icon()
                        toolBtn.setIcon(toolIcon)
                    else:
                        toolIcon = Application.icon(toolBtn.iconName)
                        if not toolIcon.isNull():
                            toolBtn.setIcon(toolIcon)
                toolAction = QAction(toolIcon, toolText, self)
                try:
                    krita_action = Application.action(toolName)
                    if krita_action:
                        toolShortcut = krita_action.shortcut().toString()
                        toolAction.setShortcut(toolShortcut)
                except Exception:
                    pass
                toolAction.setObjectName(toolName)
                toolAction.setParent(subMenu.parent_btn)
                toolAction.triggered.connect(self.activateTool)
                toolAction.triggered.connect(self.swapToolButton)
                subMenu.addAction(toolAction)
        else:
            for action in subMenu.actions():
                if action.icon().isNull():
                    actionName = action.objectName()
                    krita_action = Application.action(actionName)
                    if krita_action and not krita_action.icon().isNull():
                        action.setIcon(krita_action.icon())
        for action in subMenu.actions():
            action.setIconVisibleInMenu(True)

    def swapToolButton(self):
        sender = self.sender()
        if not sender:
            return
        from bettertoolbox import toolbuttons
        subtool_actionName = sender.objectName()
        for tb in toolbuttons.ToolList:
            if tb.actionName == subtool_actionName:
                mainToolButton = sender.parent()
                if hasattr(mainToolButton, 'isMain') and mainToolButton.isMain != tb.isMain:
                    mainToolButton.isMain = "0"
                    tb.isMain = "1"
                    tb.setChecked(True)
                    self.activate_layout.emit()
                else:
                    tb.setChecked(True)

    def toggle_standard_toolbox(self):
        for docker in Krita.instance().dockers():
            if docker.objectName() == "ToolBox":
                docker.setVisible(not docker.isVisible())
                break

    def apply_floating_styles(self):
        if self._applying_styles:
            return
        self._applying_styles = True
        try:
            self._apply_floating_styles_impl()
        finally:
            self._applying_styles = False

    def _apply_floating_styles_impl(self):
        is_float = self.isFloating()
        data = jsonMethod.loadJSON()
        modern = data.get("modern", False)
        spacing = data.get("spacing", 6)

        self.tools_layout.setSpacing(spacing if is_float else 6)

        if is_float and modern:
            self.title_label.setFixedHeight(4)
            self.title_label.setFrameShape(QFrame.NoFrame)
            self.title_label.setStyleSheet("background: transparent;")
            self.title_label.setCursor(Qt.SizeAllCursor)
            self.setFeatures(QDockWidget.DockWidgetClosable | QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable)

            self.widget.setStyleSheet("QWidget#MainContainer { background-color: transparent; }")
            self.setAttribute(Qt.WA_TranslucentBackground, True)
            self.widget.layout().setSizeConstraint(QLayout.SetFixedSize)

            btn_style = """
                QToolButton {
                    background-color: rgba(50, 50, 50, 220);
                    border-radius: 4px;
                    border: 1px solid rgba(20, 20, 20, 150);
                    margin: 0px;
                }
                QToolButton:hover {
                    background-color: rgba(70, 70, 70, 255);
                }
                QToolButton:checked {
                    background-color: rgba(30, 30, 30, 255);
                }
            """
            for btn in self.tools_container.findChildren(QToolButton):
                btn.setStyleSheet(btn_style)
            self.toolbox_btn.setStyleSheet(btn_style)
            self.settings_btn.setStyleSheet(btn_style)
        else:
            self.title_label.setFrameShape(QFrame.StyledPanel)
            self.title_label.setFrameShadow(QFrame.Raised)
            self.title_label.setFrameStyle(QFrame.Panel | QFrame.Raised)
            self.title_label.setStyleSheet("")
            self.title_label.setCursor(Qt.ArrowCursor)
            self.setFeatures(QDockWidget.DockWidgetClosable | QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable)
            self.title_label.setMinimumSize(0, 0)
            self.title_label.setMaximumSize(16777215, 16777215)
            self.title_label.setMinimumWidth(16)
            self.title_label.setFixedHeight(12)

            self.widget.setStyleSheet("")
            self.setAttribute(Qt.WA_TranslucentBackground, False)
            self.widget.layout().setSizeConstraint(QLayout.SetDefaultConstraint)
            for btn in self.tools_container.findChildren(QToolButton):
                btn.setStyleSheet("")
                btn.setMinimumSize(0, 0)
                btn.setMaximumSize(16777215, 16777215)
            self.toolbox_btn.setStyleSheet("")
            self.settings_btn.setStyleSheet("")

        self.tools_container.updateGeometry()
        self.widget.layout().activate()
        self.widget.updateGeometry()
        self.widget.update()

    @pyqtSlot()
    def setupLayout(self):
        from bettertoolbox import toolbuttons

        if hasattr(self, 'tools_layout') and self.tools_layout is not None:
            while self.tools_layout.count():
                item = self.tools_layout.takeAt(0)
                if item and item.widget():
                    item.widget().setParent(self)
                    item.widget().hide()
            self.main_layout.removeWidget(self.tools_container)
            self.tools_container.deleteLater()

        while self.main_layout.count():
            self.main_layout.takeAt(0)

        data = jsonMethod.loadJSON()
        is_float = self.isFloating()
        modern = data.get("modern", False)
        orientation = data.get("orientation", "Horizontal")
        if not is_float:
            orientation = "Vertical"
        spacing = data.get("spacing", 6)

        self.tools_container = QWidget()
        self.tools_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        if is_float and modern:
            if orientation == "Vertical":
                self.tools_layout = QVBoxLayout()
                self.tools_layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
            else:
                self.tools_layout = QHBoxLayout()
                self.tools_layout.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        else:
            self.tools_layout = FlowLayout(spacing=spacing if is_float else 6)
            
            is_horizontal = self.is_horizontal_dock()
            if is_horizontal:
                self.main_layout.setDirection(QBoxLayout.LeftToRight)
            else:
                self.main_layout.setDirection(QBoxLayout.TopToBottom)

        self.tools_layout.setContentsMargins(0, 0, 0, 0)
        self.tools_layout.setSpacing(spacing if is_float else 6)
        self.tools_container.setLayout(self.tools_layout)

        self.main_layout.addWidget(self.tools_container)

        current_tools = set(toolbuttons.ToolList)
        from bettertoolbox.toolbuttons import ToolButton as TBClass
        for child in self.findChildren(TBClass):
            if child not in current_tools:
                child.deleteLater()

        category_dictionary.categories.clear()
        iconSize = data.get("iconSize", 18)
        btnSize = data.get("btnSize", 28)
        if not is_float:
            btnSize = iconSize + 10

        for tb in toolbuttons.ToolList:
            if tb.category not in category_dictionary.categories:
                category_dictionary.categories[tb.category] = ToolCategory(tb.category)
            category_dictionary.categories[tb.category].addTool(tb)
            if tb.parent() != self:
                tb.setParent(self)
                tb.setStyle(_tk_style)
                try:
                    tb.clicked.disconnect()
                except TypeError:
                    pass
                tb.clicked.connect(self.activateTool)
            if tb.isMain == "1":
                self.mainToolButtons.addButton(tb)
                self.tools_layout.addWidget(tb)
                tb.updateIconSize(iconSize, btnSize)
                tb.installEventFilter(self)
                tb.show()
                if hasattr(tb, '_subMenu') and tb._subMenu:
                    tb._subMenu.deleteLater()
                    tb._subMenu = None
                subMenu = Menu(tb)
                subMenu.setWindowFlags(Qt.Popup)
                tb._subMenu = subMenu
                tb._subMenu.aboutToShow.connect(self.linkMenu)
                tb.setContextMenuPolicy(Qt.CustomContextMenu)
                try:
                    tb.customContextMenuRequested.disconnect()
                except TypeError:
                    pass
                tb.customContextMenuRequested.connect(
                    lambda pos, btn=tb: btn._subMenu.exec_(btn.mapToGlobal(pos))
                )
            else:
                tb.hide()

        try:
            self.toolbox_btn.setFixedSize(QSize(btnSize, btnSize))
            self.toolbox_btn.setIconSize(QSize(iconSize, iconSize))
            self.settings_btn.setFixedSize(QSize(btnSize, btnSize))
            self.settings_btn.setIconSize(QSize(iconSize, iconSize))
        except Exception:
            pass

        if is_float and modern:
            self.tools_layout.addWidget(self.settings_btn)
        else:
            self.main_layout.addStretch(1)
            self.main_layout.addWidget(self.toolbox_btn)
            self.main_layout.addWidget(self.settings_btn)

        self.toolbox_btn.installEventFilter(self)
        if is_float:
            self.toolbox_btn.hide()
        else:
            self.toolbox_btn.show()
        self.settings_btn.installEventFilter(self)
        self.settings_btn.show()

        self.setMinimumSize(0, 0)
        self.setMaximumSize(16777215, 16777215)
        self.apply_floating_styles()

        self._deferred_resize()

    def _deferred_resize(self):
        self.widget.layout().activate()
        if hasattr(self, 'tools_container') and self.tools_container:
            self.tools_container.layout().activate()
        if self.isFloating():
            self.widget.adjustSize()
            self.adjustSize()
        else:
            # Force Krita's dock manager to shrink the dock panel dimension
            data = jsonMethod.loadJSON()
            btnSize = data.get("btnSize", 28)
            ideal_size = btnSize + 16
            
            if self.is_horizontal_dock():
                self.setMaximumHeight(ideal_size)
                self.widget.setMaximumHeight(ideal_size)
                # Release the max height after layout settles
                QTimer.singleShot(200, self._release_max_height)
            else:
                self.setMaximumWidth(ideal_size)
                self.widget.setMaximumWidth(ideal_size)
                # Release the max width after layout settles
                QTimer.singleShot(200, self._release_max_width)

    def _release_max_width(self):
        self.setMaximumWidth(16777215)
        self.widget.setMaximumWidth(16777215)

    def _release_max_height(self):
        self.setMaximumHeight(16777215)
        self.widget.setMaximumHeight(16777215)

    def canvasChanged(self, canvas):
        pass

class BetterToolboxExtension(Extension):
    def __init__(self, parent):
        super().__init__(parent)

    def setup(self):
        pass

    def createActions(self, window):
        pass

instance = Krita.instance()
extension = BetterToolboxExtension(instance)
instance.addExtension(extension)
dock_widget_factory = DockWidgetFactory(DOCKER_ID, DockWidgetFactoryBase.DockLeft, bettertoolbox)
instance.addDockWidgetFactory(dock_widget_factory)
