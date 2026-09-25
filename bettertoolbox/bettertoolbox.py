import json
import weakref
from os import path
from bettertoolbox.qt_compat import *
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

# One docker exists per Krita window; settings changes must re-lay out all of them.
_dockers = weakref.WeakSet()
_update_check_started = False

def relayout_all_dockers():
    for docker in list(_dockers):
        QTimer.singleShot(0, docker.safe_relayout)

def get_local_version():
    """The installed plugin version from version.json, or None if it can't be read."""
    try:
        with open(path.join(path.dirname(path.realpath(__file__)), 'version.json'), 'r', encoding='utf-8') as f:
            return json.load(f).get("version")
    except (OSError, ValueError):
        return None

class TKStyle(QProxyStyle):
    def styleHint(self, element, option, widget, returnData):
        if element == QStyle.StyleHint.SH_ToolButton_PopupDelay:
            return 100
        return super().styleHint(element, option, widget, returnData)
    def drawPrimitive(self, element, option, painter, widget):
        if element == QStyle.PrimitiveElement.PE_IndicatorArrowDown:
            adjusted_point = QPoint(0, 5)
            triangle = QPainterPath()
            startPoint = option.rect.bottomRight() - adjusted_point
            triangle.moveTo(startPoint)
            triangle.lineTo(startPoint + QPoint(0, 5))
            triangle.lineTo(startPoint + QPoint(-5, 5))
            painter.fillPath(triangle, Qt.GlobalColor.white)
        else:
            super().drawPrimitive(element, option, painter, widget)

_tk_style = None

# Window surfaces drawn by the GPU, where per-pixel transparency isn't available (Qt5's RasterGLSurface is fine)
_GPU_SURFACES = {getattr(QSurface.SurfaceType, n) for n in
                 ("OpenGLSurface", "OpenVGSurface", "VulkanSurface", "MetalSurface", "Direct3DSurface")
                 if hasattr(QSurface.SurfaceType, n)}

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
        self.tab3 = QWidget()
        self.tab1.layout = QVBoxLayout(self.tab1)
        self.tab1.layout.setContentsMargins(6, 6, 6, 6)
        self.tab2.layout = QVBoxLayout(self.tab2)
        self.tab2.layout.setContentsMargins(10, 10, 10, 10)
        self.tab2.layout.setSpacing(6)
        self.tab3.layout = QVBoxLayout(self.tab3)
        self.tab3.layout.setContentsMargins(10, 10, 10, 10)
        self.tab3.layout.setSpacing(6)
        self.tabs.addTab(self.tab1, "Tools")
        self.tabs.addTab(self.tab2, "Layout")
        self.tabs.addTab(self.tab3, "Behaviour")
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
        self.iconSizeSlider = QSlider(Qt.Orientation.Horizontal)
        self.iconSizeSlider.setRange(10, 64)
        self.iconSizeSlider.setValue(data.get("iconSize", 18))
        self.iconSizeLabel = QLabel(f'{self.iconSizeSlider.value()}px')
        self.iconSizeLabel.setMinimumWidth(28)
        self.iconSizeLabel.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.iconSizeLabel.setStyleSheet("font-size: 10px; color: #888;")

        btn_lbl = QLabel(i18n("Button"))
        btn_lbl.setStyleSheet("font-size: 11px;")
        self.btnSizeSlider = QSlider(Qt.Orientation.Horizontal)
        self.btnSizeSlider.setRange(10, 80)
        self.btnSizeSlider.setValue(data.get("btnSize", 28))
        self.btnSizeLabel = QLabel(f'{self.btnSizeSlider.value()}px')
        self.btnSizeLabel.setMinimumWidth(28)
        self.btnSizeLabel.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
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
        size_grid.addWidget(self.lockBtn, 0, 3, 2, 1, Qt.AlignmentFlag.AlignCenter)
        size_grid.addWidget(btn_lbl, 1, 0)
        size_grid.addWidget(self.btnSizeSlider, 1, 1)
        size_grid.addWidget(self.btnSizeLabel, 1, 2)
        size_grid.setColumnStretch(1, 1)
        self.tab2.layout.addLayout(size_grid)

        # ── Separator ──
        sep1 = QFrame()
        sep1.setFrameShape(QFrame.Shape.HLine)
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
        self.spacingSlider = QSlider(Qt.Orientation.Horizontal)
        self.spacingSlider.setRange(0, 30)
        self.spacingSlider.setValue(data.get("spacing", 6))
        self.spacingLabel = QLabel(f'{self.spacingSlider.value()}px')
        self.spacingLabel.setMinimumWidth(28)
        self.spacingLabel.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
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

        # ── Separator ──
        sep_color = QFrame()
        sep_color.setFrameShape(QFrame.Shape.HLine)
        sep_color.setStyleSheet("color: rgba(255,255,255,15);")
        self.tab2.layout.addWidget(sep_color)
        self.sep_color = sep_color

        # ── Color Section ──
        color_header = QLabel("Color")
        color_header.setStyleSheet("font-weight: bold; font-size: 11px; color: #aaa; padding: 2px 0;")
        self.tab2.layout.addWidget(color_header)
        self.color_header = color_header

        self.colorModeGroup = QButtonGroup(self)
        self.themeRadio = QRadioButton(i18n("Follow Krita theme"))
        self.customColorRadio = QRadioButton(i18n("Custom color"))
        self.themeRadio.setStyleSheet("font-size: 11px;")
        self.customColorRadio.setStyleSheet("font-size: 11px;")
        self.colorModeGroup.addButton(self.themeRadio)
        self.colorModeGroup.addButton(self.customColorRadio)

        color_mode = data.get("colorMode", "theme")
        if color_mode == "custom":
            self.customColorRadio.setChecked(True)
        else:
            self.themeRadio.setChecked(True)

        color_radio_row = QHBoxLayout()
        color_radio_row.setContentsMargins(0, 0, 0, 0)
        color_radio_row.addWidget(self.themeRadio)
        color_radio_row.addWidget(self.customColorRadio)
        color_radio_row.addStretch()
        self.colorRadioWidget = QWidget()
        self.colorRadioWidget.setLayout(color_radio_row)
        self.tab2.layout.addWidget(self.colorRadioWidget)

        # Custom color picker row
        picker_row = QHBoxLayout()
        picker_row.setContentsMargins(18, 4, 0, 0)
        picker_lbl = QLabel(i18n("Button color"))
        picker_lbl.setStyleSheet("font-size: 11px;")
        self._custom_color = QColor(data.get("customColor", "#323232"))
        self.colorPickerBtn = QPushButton()
        self.colorPickerBtn.setFixedSize(60, 24)
        self.colorPickerBtn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._update_color_preview()
        self.colorPickerBtn.clicked.connect(self._pick_color)
        picker_row.addWidget(picker_lbl)
        picker_row.addWidget(self.colorPickerBtn)
        picker_row.addStretch()
        self.colorPickerWidget = QWidget()
        self.colorPickerWidget.setLayout(picker_row)
        self.tab2.layout.addWidget(self.colorPickerWidget)

        # Show/hide picker based on radio selection
        self.colorPickerWidget.setVisible(self.customColorRadio.isChecked())
        self.customColorRadio.toggled.connect(self.colorPickerWidget.setVisible)

        self.floatingNotice = QLabel(i18n("⬆ Floating options appear when the toolbar is undocked."))
        self.floatingNotice.setStyleSheet("color: #666; font-size: 10px; font-style: italic; padding: 4px 0;")
        self.floatingNotice.setWordWrap(True)
        self.tab2.layout.addWidget(self.floatingNotice)

        self.tab2.layout.addStretch()

        # ── Behaviour Tab ──

        # ── Submenu Section ──
        submenu_header = QLabel("Submenu")
        submenu_header.setStyleSheet("font-weight: bold; font-size: 11px; color: #aaa; padding: 2px 0;")
        self.tab3.layout.addWidget(submenu_header)

        self.longPressCheckbox = QCheckBox(i18n("Activate submenu by long pressing on tool category"))
        self.longPressCheckbox.setStyleSheet("font-size: 11px;")
        self.longPressCheckbox.setChecked(data.get("longPressSubmenu", False))
        self.tab3.layout.addWidget(self.longPressCheckbox)

        longpress_hint = QLabel(i18n("When enabled, press and hold a tool button to open its submenu.\nUseful for pen tablet workflows where right-clicking is difficult."))
        longpress_hint.setStyleSheet("color: #666; font-size: 10px; font-style: italic; padding: 4px 0 0 18px;")
        longpress_hint.setWordWrap(True)
        self.tab3.layout.addWidget(longpress_hint)

        # Long Press Delay
        delay_row = QHBoxLayout()
        delay_row.setContentsMargins(18, 4, 0, 0)
        delay_lbl = QLabel(i18n("Hold duration"))
        delay_lbl.setStyleSheet("font-size: 11px;")
        self.longPressDelaySlider = QSlider(Qt.Orientation.Horizontal)
        self.longPressDelaySlider.setRange(2, 10)
        self.longPressDelaySlider.setSingleStep(1)
        self.longPressDelaySlider.setValue(data.get("longPressDelay", 400) // 100)
        self.longPressDelayLabel = QLabel(f'{self.longPressDelaySlider.value() * 100}ms')
        self.longPressDelayLabel.setMinimumWidth(36)
        self.longPressDelayLabel.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.longPressDelayLabel.setStyleSheet("font-size: 10px; color: #888;")
        self.longPressDelaySlider.valueChanged.connect(
            lambda v: self.longPressDelayLabel.setText(f"{v * 100}ms")
        )
        delay_row.addWidget(delay_lbl)
        delay_row.addWidget(self.longPressDelaySlider, 1)
        delay_row.addWidget(self.longPressDelayLabel)
        self.longPressDelayWidget = QWidget()
        self.longPressDelayWidget.setLayout(delay_row)
        self.tab3.layout.addWidget(self.longPressDelayWidget)

        # Enable/disable delay slider based on checkbox
        self.longPressDelayWidget.setEnabled(self.longPressCheckbox.isChecked())
        self.longPressCheckbox.toggled.connect(self.longPressDelayWidget.setEnabled)

        self.swapSubToolCheckbox = QCheckBox(i18n("Remember last used sub-tool per category"))
        self.swapSubToolCheckbox.setStyleSheet("font-size: 11px;")
        self.swapSubToolCheckbox.setChecked(data.get("swapSubTool", True))
        self.tab3.layout.addWidget(self.swapSubToolCheckbox)

        swap_hint = QLabel(i18n("When enabled, selecting a sub-tool from the submenu makes it\nthe visible button for that category."))
        swap_hint.setStyleSheet("color: #666; font-size: 10px; font-style: italic; padding: 4px 0 0 18px;")
        swap_hint.setWordWrap(True)
        self.tab3.layout.addWidget(swap_hint)

        self.autoUpdateCheckbox = QCheckBox(i18n("Check for plugin updates on startup"))
        self.autoUpdateCheckbox.setStyleSheet("font-size: 11px;")
        self.autoUpdateCheckbox.setChecked(data.get("autoUpdate", True))
        self.tab3.layout.addWidget(self.autoUpdateCheckbox)

        update_hint = QLabel(i18n("When enabled, the plugin checks for updates on startup and prompts to install them."))
        update_hint.setStyleSheet("color: #666; font-size: 10px; font-style: italic; padding: 4px 0 0 18px;")
        update_hint.setWordWrap(True)
        self.tab3.layout.addWidget(update_hint)

        # ── Separator ──
        sep_beh = QFrame()
        sep_beh.setFrameShape(QFrame.Shape.HLine)
        sep_beh.setStyleSheet("color: rgba(255,255,255,15);")
        self.tab3.layout.addWidget(sep_beh)

        # ── Floating Section ──
        float_beh_header = QLabel("Floating")
        float_beh_header.setStyleSheet("font-weight: bold; font-size: 11px; color: #aaa; padding: 2px 0;")
        self.tab3.layout.addWidget(float_beh_header)

        self.followWindowCheckbox = QCheckBox(i18n("Follow Krita window position when floating"))
        self.followWindowCheckbox.setStyleSheet("font-size: 11px;")
        self.followWindowCheckbox.setChecked(data.get("followKritaWindow", False))
        self.tab3.layout.addWidget(self.followWindowCheckbox)

        follow_hint = QLabel(i18n("When enabled, the floating toolbar maintains its position relative to\nthe Krita window. Moving Krita to another monitor will bring the toolbar along."))
        follow_hint.setStyleSheet("color: #666; font-size: 10px; font-style: italic; padding: 4px 0 0 18px;")
        follow_hint.setWordWrap(True)
        self.tab3.layout.addWidget(follow_hint)

        # ── Separator ──
        sep_beh2 = QFrame()
        sep_beh2.setFrameShape(QFrame.Shape.HLine)
        sep_beh2.setStyleSheet("color: rgba(255,255,255,15);")
        self.tab3.layout.addWidget(sep_beh2)

        # ── Tooltips Section ──
        tooltip_header = QLabel("Tooltips")
        tooltip_header.setStyleSheet("font-weight: bold; font-size: 11px; color: #aaa; padding: 2px 0;")
        self.tab3.layout.addWidget(tooltip_header)

        self.showShortcutsCheckbox = QCheckBox(i18n("Show keyboard shortcuts in tooltips"))
        self.showShortcutsCheckbox.setStyleSheet("font-size: 11px;")
        self.showShortcutsCheckbox.setChecked(data.get("showShortcuts", True))
        self.tab3.layout.addWidget(self.showShortcutsCheckbox)

        shortcut_hint = QLabel(i18n("Displays the assigned keyboard shortcut next to each tool name."))
        shortcut_hint.setStyleSheet("color: #666; font-size: 10px; font-style: italic; padding: 4px 0 0 18px;")
        shortcut_hint.setWordWrap(True)
        self.tab3.layout.addWidget(shortcut_hint)

        self.tab3.layout.addStretch()

        self.layout.addWidget(self.tabs)

        # ── Footer ──
        footer = QHBoxLayout()
        footer.setContentsMargins(10, 6, 10, 8)
        version_label = QLabel(f"BetterToolbox v{get_local_version() or '?'}")
        version_label.setStyleSheet("color: #666; font-size: 10px;")
        footer.addWidget(version_label)
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
        self.parentWidget().reject()

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

    def _update_color_preview(self):
        """Update the color picker button to show the current custom color."""
        c = self._custom_color
        self.colorPickerBtn.setStyleSheet(
            f"background-color: {c.name()}; border: 1px solid #4a4a4a; border-radius: 3px;"
        )

    def _pick_color(self):
        """Open a color dialog to choose a custom toolbar color."""
        color = QColorDialog.getColor(
            self._custom_color, self, i18n("Choose Toolbar Color"),
            QColorDialog.ColorDialogOption.ShowAlphaChannel
        )
        if color.isValid():
            self._custom_color = color
            self._update_color_preview()

    def update_visibility(self):
        is_float = self.docker.isFloating()
        show_float = is_float
        self.float_header.setVisible(show_float)
        self.orientationWidget.setVisible(show_float)
        self.spacingWidget.setVisible(show_float)
        self.sep_color.setVisible(show_float)
        self.color_header.setVisible(show_float)
        self.colorRadioWidget.setVisible(show_float)
        self.colorPickerWidget.setVisible(show_float and self.customColorRadio.isChecked())
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
            "orientation": "Vertical" if self.verticalRadio.isChecked() else "Horizontal",
            "longPressSubmenu": self.longPressCheckbox.isChecked(),
            "longPressDelay": self.longPressDelaySlider.value() * 100,
            "swapSubTool": self.swapSubToolCheckbox.isChecked(),
            "showShortcuts": self.showShortcutsCheckbox.isChecked(),
            "autoUpdate": self.autoUpdateCheckbox.isChecked(),
            "followKritaWindow": self.followWindowCheckbox.isChecked(),
            "colorMode": "custom" if self.customColorRadio.isChecked() else "theme",
            "customColor": self._custom_color.name(QColor.NameFormat.HexArgb)
        })
        toolbuttons.load_tool_list()
        self.parentWidget().accept()
        relayout_all_dockers()

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

# Settings writes these as you edit (Add Tool, preset switch); Cancel puts them back
_TOOL_SETTING_DEFAULTS = {"presets": {}, "active_preset": "Default", "custom_tools": []}

class SDialog(QDialog):
    def __init__(self, docker):
        super().__init__()
        self.docker = docker
        data = jsonMethod.loadJSON()
        self._tools_snapshot = {k: data.get(k, d) for k, d in _TOOL_SETTING_DEFAULTS.items()}
        self.setWindowTitle("BetterToolBox Settings")
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setMinimumSize(680, 540)
        self.setStyleSheet(DIALOG_STYLE)
        SLayout = QVBoxLayout(self)
        SLayout.setContentsMargins(6, 6, 6, 0)
        self.settings_widget = SettingsWidget(self, docker)
        SLayout.addWidget(self.settings_widget)

    def exec(self):
        self.settings_widget.update_visibility()
        return super().exec()

    def reject(self):
        # Cancel, Esc and the title-bar X all land here: drop unsaved tool/preset edits
        current = jsonMethod.loadJSON()
        changed = {k: v for k, v in self._tools_snapshot.items() if current.get(k, _TOOL_SETTING_DEFAULTS[k]) != v}
        if changed:
            jsonMethod.update_dict(changed)
        toolbuttons.load_tool_list()
        relayout_all_dockers()
        super().reject()

class UpdateDialog(QDialog):
    def __init__(self, parent, remote_version, release_notes):
        super().__init__(parent)
        self.setWindowTitle(i18n("Update Available"))
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setMinimumSize(520, 380)
        self.resize(550, 420)
        
        self.setStyleSheet("""
            QDialog {
                background: #2b2b2b;
                color: #ddd;
            }
            QLabel {
                color: #ddd;
            }
            QTextBrowser {
                background: #202020;
                color: #ccc;
                border: 1px solid #3a3a3a;
                border-radius: 4px;
                padding: 8px;
                font-family: sans-serif;
            }
            QPushButton {
                background-color: #3e3e3e;
                border: 1px solid #555;
                border-radius: 4px;
                color: #ddd;
                padding: 6px 16px;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #4f4f4f;
                border-color: #666;
            }
            QPushButton:pressed {
                background-color: #2b2b2b;
            }
            QPushButton#updateBtn {
                background-color: #3a6dae;
                border-color: #4a7ebe;
                font-weight: bold;
            }
            QPushButton#updateBtn:hover {
                background-color: #477fc4;
                border-color: #5b92d6;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        
        header = QLabel(i18n(f"A new version of BetterToolbox ({remote_version}) is available!"))
        header.setStyleSheet("font-weight: bold; font-size: 13px; color: #5599dd;")
        layout.addWidget(header)
        
        notes_lbl = QLabel(i18n("Release notes & changes:"))
        notes_lbl.setStyleSheet("color: #aaa; font-size: 11px;")
        layout.addWidget(notes_lbl)
        
        self.notes_browser = QTextBrowser()
        self.notes_browser.setPlainText(release_notes)
        layout.addWidget(self.notes_browser)
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        self.cancel_btn = QPushButton(i18n("Later"))
        self.cancel_btn.clicked.connect(self.reject)
        
        self.update_btn = QPushButton(i18n("Update Now"))
        self.update_btn.setObjectName("updateBtn")
        self.update_btn.clicked.connect(self.accept)
        
        btn_layout.addWidget(self.cancel_btn)
        btn_layout.addWidget(self.update_btn)
        layout.addLayout(btn_layout)

class bettertoolbox(QDockWidget):
    activate_layout = pyqtSignal()
    def __init__(self):
        super().__init__()
        
        global _tk_style
        if _tk_style is None:
            _tk_style = TKStyle("fusion")
        
        self.setFloating(False)
        self.setWindowTitle('BetterToolBox')
        # Must be set before the floating window is first created: Qt6 only gives a window an alpha
        # channel at creation time (Qt5 applied it live). Has no visible effect while docked.
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.mainToolButtons = QButtonGroup()
        self.mainToolButtons.setExclusive(True)
        self.widget = QWidget()
        self.widget.setObjectName("MainContainer")
        self.widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.title_label = QLabel(" ")
        self.title_label.setFrameShape(QFrame.Shape.StyledPanel)
        self.title_label.setFrameShadow(QFrame.Shadow.Raised)
        self.title_label.setFrameStyle(QFrame.Shape.Panel | QFrame.Shadow.Raised)
        self.title_label.setMinimumWidth(16)
        self.title_label.setFixedHeight(12)
        self.setWidget(self.widget)
        self.setTitleBarWidget(self.title_label)
        self.main_layout = QBoxLayout(QBoxLayout.Direction.TopToBottom, self.widget)
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
        self.tools_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
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

        # Window-follow tracking state
        self._krita_window_offset = None
        self._tracked_qwindow = None

        # Active tool tracking state
        self._toolbox_buttons = {}
        self._tool_watch_retries = 0
        self._syncing_tool = False

        self.installEventFilter(self)

        if not toolbuttons.ToolList:
            toolbuttons.load_tool_list()

        # toolbuttons.ToolList holds shared, never-shown models; each docker shows its own buttons
        # (one docker per Krita window), so closing one window can't destroy another's buttons.
        self._views = {}
        _dockers.add(self)
        # Tool buttons do nothing without a document: refresh their enabled state when that changes
        notifier = Krita.instance().notifier()
        if not notifier.active():
            notifier.setActive(True)
        for signal in (notifier.imageCreated, notifier.imageClosed, notifier.viewCreated, notifier.viewClosed):
            signal.connect(self._schedule_enabled_refresh)
        self.activate_layout.connect(self.setupLayout)
        self.topLevelChanged.connect(self.on_float_changed)
        self.dockLocationChanged.connect(self.on_dock_location_changed)
        QTimer.singleShot(0, self.activate_layout.emit)
        QTimer.singleShot(300, self._install_tool_watcher)
        QTimer.singleShot(500, self._clamp_to_screen)
        QTimer.singleShot(1000, self.check_for_updates)

    def _schedule_enabled_refresh(self, *args):
        QTimer.singleShot(0, self._refresh_enabled)

    def _refresh_enabled(self):
        try:
            enabled = len(Krita.instance().documents()) > 0
            for tb in self._views.values():
                tb.setEnabled(enabled)
        except RuntimeError:
            pass  # this docker's window was closed

    def safe_relayout(self):
        try:
            self.setupLayout()
        except RuntimeError:
            pass  # this docker's window was closed

    def on_dock_location_changed(self, area):
        self.setupLayout()

    def is_horizontal_dock(self):
        if self.isFloating():
            return False
        qwin = self._own_qwindow()
        if qwin is not None:
            area = qwin.dockWidgetArea(self)
            return area in (Qt.DockWidgetArea.TopDockWidgetArea, Qt.DockWidgetArea.BottomDockWidgetArea)
        return False

    def on_float_changed(self, is_float):
        if not is_float:
            self._remove_window_tracker()
            # Immediately reset floating-mode state before Krita settles dock geometry
            self.widget.setStyleSheet("")
            self.widget.layout().setSizeConstraint(QLayout.SizeConstraint.SetDefaultConstraint)
            self.title_label.setFixedHeight(12)
            self.title_label.setFrameShape(QFrame.Shape.StyledPanel)
            self.title_label.setFrameStyle(QFrame.Shape.Panel | QFrame.Shadow.Raised)
            self.title_label.setStyleSheet("")
            for btn in self.tools_container.findChildren(QToolButton):
                btn.setStyleSheet("")
        self.setupLayout()

    def _start_drag(self):
        if self._drag_start_pos is not None:
            self._is_dragging = True

    def _check_dock_proximity(self):
        cursor = QCursor.pos()
        qwin = self._own_qwindow()
        if qwin is None:
            return
        win_rect = qwin.geometry()
        dock_margin = 40
        if cursor.x() <= win_rect.left() + dock_margin or cursor.x() >= win_rect.right() - dock_margin:
            self.setFloating(False)

    def open_settings(self):
        dialog = SDialog(self)
        dialog.exec()

    def activateTool(self):
        sender = self.sender()
        if not sender:
            return
        actionName = sender.objectName()
        ac = Application.action(actionName)
        if ac:
            ac.trigger()
            if ac.isCheckable() and isinstance(sender, ToolButton):
                sender.setChecked(ac.isChecked())

    def _toggle_action(self, actionName):
        """The Krita action if it is an on/off mode rather than a tool (tool actions aren't checkable)."""
        action = Application.action(actionName)
        return action if action is not None and action.isCheckable() else None

    def linkMenu(self):
        subMenu = self.sender()
        if not subMenu:
            return
        if subMenu.isEmpty():
            categoryName = subMenu.parent_btn.category
            if categoryName not in category_dictionary.categories:
                return
            category = category_dictionary.categories[categoryName]
            data = jsonMethod.loadJSON()
            show_shortcuts = data.get("showShortcuts", True)
            swap_sub_tool = data.get("swapSubTool", True)
            for key in category.ToolButtons:
                toolBtn = category.ToolButtons[key]
                toolIcon = toolBtn.icon()
                toolText = toolBtn.displayName()
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
                toolAction = QAction(toolIcon, toolText, subMenu)
                try:
                    krita_action = Application.action(toolName)
                    if krita_action and show_shortcuts:
                        toolAction.setShortcut(krita_action.shortcut())
                except Exception:
                    pass
                toolAction.setObjectName(toolName)
                toolAction.triggered.connect(self.activateTool)
                if swap_sub_tool:
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
        model = next((tb for tb in toolbuttons.ToolList if tb.actionName == sender.objectName()), None)
        if model is not None:
            self._promote(model)

    def _promote(self, model):
        """Make model the visible button of its category (re-laying out if needed) and highlight it."""
        if model.isMain != "1":
            for tb in toolbuttons.ToolList:
                if tb.category == model.category and tb.isMain == "1":
                    tb.isMain = "0"
            model.isMain = "1"
            self.activate_layout.emit()
        view = self._views.get(model)
        if view is not None and not view.isChecked():
            view.setChecked(True)

    def toggle_standard_toolbox(self):
        for docker in Krita.instance().dockers():
            if docker.objectName() == "ToolBox":
                docker.setVisible(not docker.isVisible())
                break

    def _build_btn_style(self, data):
        """Build the floating button stylesheet based on color mode setting."""
        color_mode = data.get("colorMode", "theme")

        if color_mode == "custom":
            c = QColor(data.get("customColor", "#323232"))
            r, g, b, a = c.red(), c.green(), c.blue(), c.alpha()
            # Derive hover (lighter) and checked (darker) variants
            hover = c.lighter(130)
            checked = c.darker(130)
            hr, hg, hb = hover.red(), hover.green(), hover.blue()
            cr, cg, cb = checked.red(), checked.green(), checked.blue()
            # Border: slightly darker than base
            br_c = c.darker(150)
            br_r, br_g, br_b = br_c.red(), br_c.green(), br_c.blue()
        else:
            # Follow Krita theme — read palette colors
            palette = QApplication.palette()
            base = palette.color(QPalette.ColorRole.Button)
            r, g, b = base.red(), base.green(), base.blue()
            a = 220
            hover = base.lighter(130)
            hr, hg, hb = hover.red(), hover.green(), hover.blue()
            checked = base.darker(120)
            cr, cg, cb = checked.red(), checked.green(), checked.blue()
            br_c = base.darker(150)
            br_r, br_g, br_b = br_c.red(), br_c.green(), br_c.blue()

        return f"""
            QToolButton {{
                background-color: rgba({r}, {g}, {b}, {a});
                border-radius: 4px;
                border: 1px solid rgba({br_r}, {br_g}, {br_b}, 150);
                margin: 0px;
            }}
            QToolButton:hover {{
                background-color: rgba({hr}, {hg}, {hb}, 255);
            }}
            QToolButton:checked {{
                background-color: rgba({cr}, {cg}, {cb}, 255);
            }}
        """

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
        spacing = data.get("spacing", 6)

        self.tools_layout.setSpacing(spacing if is_float else 6)

        if is_float:
            self.title_label.setFixedHeight(4)
            self.title_label.setFrameShape(QFrame.Shape.NoFrame)
            self.title_label.setStyleSheet("background: transparent;")
            self.title_label.setCursor(Qt.CursorShape.SizeAllCursor)
            self.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetClosable | QDockWidget.DockWidgetFeature.DockWidgetMovable | QDockWidget.DockWidgetFeature.DockWidgetFloatable)

            self.widget.setStyleSheet("QWidget#MainContainer { background-color: transparent; }")
            self.widget.layout().setSizeConstraint(QLayout.SizeConstraint.SetFixedSize)

            btn_style = self._build_btn_style(data)
            for btn in self.tools_container.findChildren(QToolButton):
                btn.setStyleSheet(btn_style)
            self.toolbox_btn.setStyleSheet(btn_style)
            self.settings_btn.setStyleSheet(btn_style)
        else:
            self.title_label.setFrameShape(QFrame.Shape.StyledPanel)
            self.title_label.setFrameShadow(QFrame.Shadow.Raised)
            self.title_label.setFrameStyle(QFrame.Shape.Panel | QFrame.Shadow.Raised)
            self.title_label.setStyleSheet("")
            self.title_label.setCursor(Qt.CursorShape.ArrowCursor)
            self.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetClosable | QDockWidget.DockWidgetFeature.DockWidgetMovable | QDockWidget.DockWidgetFeature.DockWidgetFloatable)
            self.title_label.setMinimumSize(0, 0)
            self.title_label.setMaximumSize(16777215, 16777215)
            self.title_label.setMinimumWidth(16)
            self.title_label.setFixedHeight(12)

            self.widget.setStyleSheet("")
            self.widget.layout().setSizeConstraint(QLayout.SizeConstraint.SetDefaultConstraint)
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
        QTimer.singleShot(0, self._update_window_mask)

    def _update_window_mask(self):
        """Clip the floating toolbar to its buttons when its window can't do per-pixel transparency.

        Krita 6 draws every window through OpenGL (ANGLE, via QT_WIDGETS_RHI), where transparent
        pixels come out black. A window mask makes the gaps truly see-through on any renderer;
        CPU-drawn windows (Krita 5) keep their smooth per-pixel transparency.
        """
        try:
            wh = self.windowHandle() if self.isFloating() else None
            if wh is None or wh.surfaceType() not in _GPU_SURFACES:
                if not self.mask().isEmpty():
                    self.clearMask()
                return
            region = QRegion()
            for btn in self.widget.findChildren(QToolButton):
                if not btn.isVisibleTo(self):
                    continue
                shape = QPainterPath()
                # Slightly rounder than the buttons' 4px so their anti-aliased corners don't show black
                shape.addRoundedRect(QRectF(QRect(btn.mapTo(self, QPoint(0, 0)), btn.size())), 6, 6)
                region = region.united(QRegion(shape.toFillPolygon().toPolygon()))
            if region.isEmpty():
                self.clearMask()
            else:
                self.setMask(region)
        except RuntimeError:
            pass  # this docker's window was closed

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
        orientation = data.get("orientation", "Horizontal")
        if not is_float:
            orientation = "Vertical"
        spacing = data.get("spacing", 6)

        self.tools_container = QWidget()
        self.tools_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        if is_float:
            if orientation == "Vertical":
                self.tools_layout = QVBoxLayout()
                self.tools_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
            else:
                self.tools_layout = QHBoxLayout()
                self.tools_layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        else:
            self.tools_layout = FlowLayout(spacing=spacing if is_float else 6)
            
            is_horizontal = self.is_horizontal_dock()
            if is_horizontal:
                self.main_layout.setDirection(QBoxLayout.Direction.LeftToRight)
            else:
                self.main_layout.setDirection(QBoxLayout.Direction.TopToBottom)

        self.tools_layout.setContentsMargins(0, 0, 0, 0)
        self.tools_layout.setSpacing(spacing if is_float else 6)
        self.tools_container.setLayout(self.tools_layout)

        self.main_layout.addWidget(self.tools_container)

        category_dictionary.categories.clear()
        iconSize = data.get("iconSize", 18)
        btnSize = data.get("btnSize", 28)
        if not is_float:
            btnSize = iconSize + 10

        old_views, self._views = self._views, {}
        for model in toolbuttons.ToolList:
            if model.category not in category_dictionary.categories:
                category_dictionary.categories[model.category] = ToolCategory(model.category)
            category_dictionary.categories[model.category].addTool(model)
            toggle = self._toggle_action(model.actionName)
            tb = old_views.pop(model, None)
            if tb is None:
                tb = ToolButton(model.actionName, model.toolName, model.iconName, model.category, model.isMain)
                tb.setParent(self)
                tb.setStyle(_tk_style)
                tb.clicked.connect(self.activateTool)
                if toggle is not None:
                    toggle.toggled.connect(tb.setChecked)
            elif tb.iconName != model.iconName:
                tb.iconName = model.iconName
                tb.setIcon(model.icon())
            tb.toolName = model.toolName
            tb.category = model.category
            tb.isMain = model.isMain
            self._views[model] = tb
            if tb.isMain == "1":
                if toggle is None:
                    self.mainToolButtons.addButton(tb)
                else:
                    # A mode toggle (e.g. eraser) isn't a tool: show its own on/off state,
                    # outside the exclusive "active tool" group
                    self.mainToolButtons.removeButton(tb)
                    tb.setChecked(toggle.isChecked())
                self.tools_layout.addWidget(tb)
                tb.updateIconSize(iconSize, btnSize)
                tb.installEventFilter(self)
                tb.show()
                if hasattr(tb, '_subMenu') and tb._subMenu:
                    tb._subMenu.deleteLater()
                    tb._subMenu = None
                subMenu = Menu(tb)
                subMenu.setWindowFlags(Qt.WindowType.Popup)
                tb._subMenu = subMenu
                tb._subMenu.aboutToShow.connect(self.linkMenu)
                tb.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
                try:
                    tb.customContextMenuRequested.disconnect()
                except TypeError:
                    pass
                tb.customContextMenuRequested.connect(
                    lambda pos, btn=tb: btn._subMenu.exec(btn.mapToGlobal(pos))
                )
                self._setup_long_press(tb)
                self._update_tooltip(tb, data)
            else:
                self.mainToolButtons.removeButton(tb)
                tb.setChecked(False)
                tb.hide()
        for stale in old_views.values():
            self.mainToolButtons.removeButton(stale)
            stale.deleteLater()

        try:
            self.toolbox_btn.setFixedSize(QSize(btnSize, btnSize))
            self.toolbox_btn.setIconSize(QSize(iconSize, iconSize))
            self.settings_btn.setFixedSize(QSize(btnSize, btnSize))
            self.settings_btn.setIconSize(QSize(iconSize, iconSize))
        except Exception:
            pass

        if is_float:
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

        self._deferred_resize(btnSize)

        self._refresh_enabled()
        QTimer.singleShot(0, self._sync_active_tool)

        if is_float:
            QTimer.singleShot(100, self._clamp_to_screen)
            QTimer.singleShot(150, self._install_window_tracker)

    def _deferred_resize(self, btnSize):
        self.widget.layout().activate()
        if hasattr(self, 'tools_container') and self.tools_container:
            self.tools_container.layout().activate()
        if self.isFloating():
            self.widget.adjustSize()
            self.adjustSize()
        else:
            # Force Krita's dock manager to shrink the dock panel dimension
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
        try:
            self.setMaximumWidth(16777215)
            self.widget.setMaximumWidth(16777215)
        except RuntimeError:
            pass

    def _release_max_height(self):
        try:
            self.setMaximumHeight(16777215)
            self.widget.setMaximumHeight(16777215)
        except RuntimeError:
            pass

    def _clamp_to_screen(self):
        """Clamp the floating toolbar so it stays fully within the screen bounds."""
        try:
            if not self.isFloating():
                return
            if getattr(self, '_is_clamping', False):
                return
            self._is_clamping = True
            try:
                geo = self.geometry()
                screen = QApplication.screenAt(geo.center())
                if not screen:
                    # Fallback: try the Krita window's screen
                    qwin = self._own_qwindow()
                    if qwin is not None:
                        wh = qwin.windowHandle()
                        if wh:
                            screen = wh.screen()
                if not screen:
                    screen = QApplication.primaryScreen()
                if not screen:
                    return
                avail = screen.availableGeometry()
                x = geo.x()
                y = geo.y()
                # Clamp right/bottom edges first, then left/top (so toolbar is always reachable)
                if x + geo.width() > avail.right() + 1:
                    x = avail.right() + 1 - geo.width()
                if y + geo.height() > avail.bottom() + 1:
                    y = avail.bottom() + 1 - geo.height()
                if x < avail.left():
                    x = avail.left()
                if y < avail.top():
                    y = avail.top()
                if x != geo.x() or y != geo.y():
                    self.move(x, y)
                    self._update_window_offset()
            finally:
                self._is_clamping = False
        except RuntimeError:
            pass

    def _update_window_offset(self):
        """Recalculate the offset between the toolbar and the Krita window."""
        try:
            if not self.isFloating():
                self._krita_window_offset = None
                return
            qwin = self._own_qwindow()
            if qwin is not None:
                self._krita_window_offset = self.pos() - qwin.pos()
            else:
                self._krita_window_offset = None
        except RuntimeError:
            pass

    def _install_window_tracker(self):
        """Install an event filter on the Krita main window to track move events."""
        try:
            self._remove_window_tracker()
            data = jsonMethod.loadJSON()
            if not data.get("followKritaWindow", False):
                return
            if not self.isFloating():
                return
            qwin = self._own_qwindow()
            if qwin is not None:
                self._tracked_qwindow = qwin
                qwin.installEventFilter(self)
                try:
                    qwin.destroyed.connect(self._on_tracked_window_destroyed)
                except (RuntimeError, TypeError):
                    pass
                self._update_window_offset()
        except RuntimeError:
            pass

    def _remove_window_tracker(self):
        """Remove the event filter from the tracked Krita window."""
        try:
            if self._tracked_qwindow is not None:
                try:
                    self._tracked_qwindow.removeEventFilter(self)
                except RuntimeError:
                    pass  # Window already deleted
                try:
                    self._tracked_qwindow.destroyed.disconnect(self._on_tracked_window_destroyed)
                except (RuntimeError, TypeError):
                    pass
                self._tracked_qwindow = None
        except RuntimeError:
            pass

    def _on_tracked_window_destroyed(self):
        """Handle the tracked Krita window being destroyed."""
        try:
            self._tracked_qwindow = None
            self._krita_window_offset = None
        except RuntimeError:
            pass

    def _on_krita_window_moved(self):
        """Reposition the floating toolbar relative to the Krita window."""
        try:
            if not self.isFloating() or self._krita_window_offset is None:
                return
            if self._is_dragging:
                return  # Don't fight the user's drag
            if self._tracked_qwindow is not None:
                self.move(self._tracked_qwindow.pos() + self._krita_window_offset)
                self._clamp_to_screen()
        except RuntimeError:
            pass


    def _own_qwindow(self):
        """The Krita main window this docker belongs to - not necessarily the active one."""
        qwin = self.parentWidget()
        while qwin is not None and not isinstance(qwin, QMainWindow):
            qwin = qwin.parentWidget()
        if qwin is None:
            main_window = Krita.instance().activeWindow()
            qwin = main_window.qwindow() if main_window else None
        return qwin

    def _find_krita_toolbox(self):
        """Locate Krita's own ToolBox docker, its buttons always follow the active tool."""
        qwin = self._own_qwindow()
        if qwin is not None:
            toolbox = qwin.findChild(QDockWidget, "ToolBox")
            if toolbox is not None:
                return toolbox
        for docker in Krita.instance().dockers():
            if docker.objectName() == "ToolBox":
                return docker
        return None

    def _install_tool_watcher(self):
        """Mirror Krita's active tool, so shortcut driven tool changes update the highlight."""
        try:
            toolbox = self._find_krita_toolbox()
            if toolbox is None:
                if self._tool_watch_retries < 10:
                    self._tool_watch_retries += 1
                    QTimer.singleShot(1000, self._install_tool_watcher)
                return
            self._toolbox_buttons.clear()
            for btn in toolbox.findChildren(QToolButton):
                toolId = btn.objectName()
                if not toolId:
                    continue
                self._toolbox_buttons[toolId] = btn
                try:
                    btn.toggled.disconnect(self._on_krita_tool_toggled)
                except (RuntimeError, TypeError):
                    pass
                btn.toggled.connect(self._on_krita_tool_toggled)
            if not self._toolbox_buttons:
                if self._tool_watch_retries < 10:
                    self._tool_watch_retries += 1
                    QTimer.singleShot(1000, self._install_tool_watcher)
                return
            self._sync_active_tool()
        except RuntimeError:
            pass

    def _on_krita_tool_toggled(self, checked):
        """A Krita toolbox button switched on the active tool changed."""
        if not checked:
            return
        sender = self.sender()
        if not sender:
            return
        try:
            self._highlight_tool(sender.objectName())
        except RuntimeError:
            pass

    def _sync_active_tool(self):
        """Highlight whichever tool Krita currently has active."""
        if not self._toolbox_buttons:
            return
        for toolId, btn in list(self._toolbox_buttons.items()):
            try:
                checked = btn.isChecked()
            except RuntimeError:
                self._toolbox_buttons.pop(toolId, None)
                continue
            if checked:
                self._highlight_tool(toolId)
                return

    def _highlight_tool(self, toolId):
        """Check the docker button for toolId, promoting it out of a submenu if needed."""
        if not toolId or self._syncing_tool:
            return
        target = None
        for tb in toolbuttons.ToolList:
            if tb.actionName == toolId:
                target = tb
                break
        if target is None:
            self._clear_highlight()
            return
        self._syncing_tool = True
        try:
            if target.isMain != "1" and not jsonMethod.loadJSON().get("swapSubTool", True):
                self._clear_highlight()
                return
            self._promote(target)
        finally:
            self._syncing_tool = False

    def _clear_highlight(self):
        """Drop the highlight when the active tool is not shown in the docker."""
        checked = self.mainToolButtons.checkedButton()
        if checked is None:
            return
        self.mainToolButtons.setExclusive(False)
        checked.setChecked(False)
        self.mainToolButtons.setExclusive(True)

    def _setup_long_press(self, tb):
        """Attach a long-press timer to a tool button for submenu activation."""
        if hasattr(tb, '_lp_timer'):
            tb._lp_timer.stop()
            tb._lp_timer.deleteLater()

        timer = QTimer(tb)
        timer.setSingleShot(True)
        timer.timeout.connect(lambda btn=tb: self._on_long_press(btn))
        tb._lp_timer = timer
        tb._lp_active = False

    def _on_long_press(self, btn):
        """Show submenu if long-press-submenu is enabled."""
        data = jsonMethod.loadJSON()
        if not data.get("longPressSubmenu", False):
            return
        if hasattr(btn, '_subMenu') and btn._subMenu:
            btn._lp_active = True
            btn._subMenu.exec(btn.mapToGlobal(QPoint(btn.width(), 0)))

    def _update_tooltip(self, tb, data=None):
        """Update tool button tooltip, optionally appending its keyboard shortcut."""
        if data is None:
            data = jsonMethod.loadJSON()
        tb.updateToolTip(data.get("showShortcuts", True))

    def check_for_updates(self):
        global _update_check_started
        try:
            data = jsonMethod.loadJSON()
            if not data.get("autoUpdate", True) or _update_check_started:
                return
            _update_check_started = True
            self.nam = QNetworkAccessManager(self)
            self.nam.finished.connect(self.on_update_check_finished)
            url = QUrl("https://api.github.com/repos/toobi-jpg/BetterToolbox/releases/latest")
            req = QNetworkRequest(url)
            self.nam.setRedirectPolicy(QNetworkRequest.RedirectPolicy.NoLessSafeRedirectPolicy)
            req.setRawHeader(b"User-Agent", b"BetterToolbox-Krita-Plugin")
            self.nam.get(req)
        except RuntimeError:
            pass

    def on_update_check_finished(self, reply):
        status_code = reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
        if reply.error() == QNetworkReply.NetworkError.NoError and status_code in (200, 201):
            try:
                response = json.loads(bytes(reply.readAll()).decode('utf-8'))
                tag_name = response.get("tag_name", "1.0.0")
                remote_version = tag_name.lstrip('v')
                release_notes = response.get("body", "")
                
                local_version = get_local_version() or "1.1.1"
                if self.is_newer_version(local_version, remote_version):
                    self.check_release_compat(tag_name, remote_version, release_notes)
            except Exception:
                pass
        reply.deleteLater()

    def check_release_compat(self, tag_name, remote_version, release_notes):
        """Fetch the release's version.json before offering it, to see which Krita versions it supports."""
        try:
            self._pending_release = (tag_name, remote_version, release_notes)
            self.compat_nam = QNetworkAccessManager(self)
            self.compat_nam.finished.connect(self.on_compat_check_finished)
            url = QUrl(f"https://raw.githubusercontent.com/toobi-jpg/BetterToolbox/{tag_name}/bettertoolbox/version.json")
            req = QNetworkRequest(url)
            self.compat_nam.setRedirectPolicy(QNetworkRequest.RedirectPolicy.NoLessSafeRedirectPolicy)
            req.setRawHeader(b"User-Agent", b"BetterToolbox-Krita-Plugin")
            self.compat_nam.get(req)
        except RuntimeError:
            pass

    def on_compat_check_finished(self, reply):
        status_code = reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
        if reply.error() == QNetworkReply.NetworkError.NoError and status_code in (200, 201):
            try:
                remote_info = json.loads(bytes(reply.readAll()).decode('utf-8'))
                if self.is_compatible_release(remote_info):
                    tag_name, remote_version, release_notes = self._pending_release
                    dialog = UpdateDialog(self, remote_version, release_notes)
                    accepted = dialog.exec() == QDialog.DialogCode.Accepted
                    dialog.deleteLater()
                    if accepted:
                        self.start_download(tag_name)
            except Exception:
                pass
        reply.deleteLater()

    def is_compatible_release(self, version_info):
        """Releases without "qt_versions" predate Krita 6 support and only run on Qt5."""
        qt_major = int(QT_VERSION_STR.split('.')[0])
        return qt_major in version_info.get("qt_versions", [5])

    def is_newer_version(self, local, remote):
        try:
            l_parts = [int(x) for x in local.split('.')]
            r_parts = [int(x) for x in remote.split('.')]
            return r_parts > l_parts
        except Exception:
            return False

    def start_download(self, tag_name="main"):
        try:
            self.download_nam = QNetworkAccessManager(self)
            self.download_nam.finished.connect(self.on_download_finished)
            # Fetch the tagged release source code archive
            url = QUrl(f"https://github.com/toobi-jpg/BetterToolbox/archive/refs/tags/{tag_name}.zip")
            req = QNetworkRequest(url)
            req.setTransferTimeout(60000)
            self.download_nam.setRedirectPolicy(QNetworkRequest.RedirectPolicy.NoLessSafeRedirectPolicy)
            self.download_nam.get(req)
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        except RuntimeError:
            pass

    def on_download_finished(self, reply):
        QApplication.restoreOverrideCursor()
        status_code = reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
        if reply.error() == QNetworkReply.NetworkError.NoError and status_code in (200, 201):
            self.install_update(reply.readAll())
        else:
            QMessageBox.critical(self, i18n("Update Failed"), i18n("Failed to download the update."))
        reply.deleteLater()

    def install_update(self, zip_data):
        import io
        import os
        import shutil
        import zipfile
        # Replace the copy Krita actually loaded; abspath so a linked dev folder is never followed
        plugin_dir = path.dirname(path.abspath(__file__))
        pykrita_path = path.dirname(plugin_dir)
        staging_dir = plugin_dir + ".update"
        backup_dir = plugin_dir + ".backup"
        try:
            shutil.rmtree(staging_dir, ignore_errors=True)
            os.makedirs(staging_dir)
            staging_real = path.realpath(staging_dir)
            zip_file = zipfile.ZipFile(io.BytesIO(bytes(zip_data)))
            root_dir = zip_file.namelist()[0].split('/')[0] + '/'
            desktop_data = None
            for member in zip_file.namelist():
                if not member.startswith(root_dir) or member.endswith('/'):
                    continue
                rel_path = member[len(root_dir):]
                if rel_path == "bettertoolbox.desktop":
                    desktop_data = zip_file.read(member)
                    continue
                if not rel_path.startswith("bettertoolbox/"):
                    continue
                dest_path = path.realpath(path.join(staging_dir, rel_path[len("bettertoolbox/"):]))
                if path.commonpath([staging_real, dest_path]) != staging_real:
                    raise ValueError(f"Unsafe path in update archive: {member}")
                os.makedirs(path.dirname(dest_path), exist_ok=True)
                with open(dest_path, "wb") as f:
                    f.write(zip_file.read(member))

            version_path = path.join(staging_dir, "version.json")
            if not path.exists(path.join(staging_dir, "__init__.py")) or not path.exists(version_path):
                raise ValueError("The update archive does not contain the plugin.")
            with open(version_path, 'r', encoding='utf-8') as f:
                if not self.is_compatible_release(json.load(f)):
                    raise ValueError("This release does not support this version of Krita.")
            self._merge_user_settings(path.join(plugin_dir, "data.json"), path.join(staging_dir, "data.json"))

            # Swap whole folders, so a failure never leaves a half-updated plugin behind
            shutil.rmtree(backup_dir, ignore_errors=True)
            os.replace(plugin_dir, backup_dir)
            try:
                os.replace(staging_dir, plugin_dir)
            except OSError:
                os.replace(backup_dir, plugin_dir)
                raise
            json_class._cached_data = None  # the in-memory cache predates the merge; reload before the next save
            if desktop_data is not None:
                desktop_path = path.join(pykrita_path, "bettertoolbox.desktop")
                with open(desktop_path + ".update", "wb") as f:
                    f.write(desktop_data)
                os.replace(desktop_path + ".update", desktop_path)
            QMessageBox.information(
                self,
                i18n("Update Complete"),
                i18n("BetterToolbox has been updated to the latest version. Please restart Krita to apply changes.")
            )
        except Exception as e:
            shutil.rmtree(staging_dir, ignore_errors=True)
            QMessageBox.critical(self, i18n("Update Failed"), i18n(f"Error extracting update: {str(e)}"))

    def _merge_user_settings(self, user_path, new_path):
        """Carry the user's settings into the new release, adding any keys/presets it introduces."""
        try:
            with open(user_path, 'r', encoding='utf-8') as f:
                user_settings = json.load(f)
        except (OSError, ValueError):
            return  # No usable user settings: keep the release defaults
        default_settings = {}
        try:
            with open(new_path, 'r', encoding='utf-8') as f:
                default_settings = json.load(f)
        except (OSError, ValueError):
            pass
        for key, val in default_settings.items():
            if key not in user_settings:
                user_settings[key] = val
            elif key == "presets":
                for p_name, p_val in val.items():
                    if p_name not in user_settings["presets"]:
                        user_settings["presets"][p_name] = p_val
        with open(new_path, 'w', encoding='utf-8') as f:
            json.dump(user_settings, f, indent=4, sort_keys=True)

    def eventFilter(self, obj, event):
        # Handle own resize/show events to clamp floating toolbar to screen bounds dynamically
        if obj == self:
            if event.type() in (QEvent.Type.Resize, QEvent.Type.Show):
                if self.isFloating():
                    QTimer.singleShot(0, self._clamp_to_screen)
                QTimer.singleShot(0, self._update_window_mask)

        # Long-press detection for tool buttons
        if isinstance(obj, ToolButton) and self.tools_container.isAncestorOf(obj):
            if event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
                data = jsonMethod.loadJSON()
                if data.get("longPressSubmenu", False) and hasattr(obj, '_lp_timer'):
                    delay = data.get("longPressDelay", 400)
                    obj._lp_timer.setInterval(delay)
                    obj._lp_timer.start()
                    obj._lp_active = False
            elif event.type() == QEvent.Type.MouseButtonRelease and event.button() == Qt.MouseButton.LeftButton:
                if hasattr(obj, '_lp_timer'):
                    obj._lp_timer.stop()
                    if obj._lp_active:
                        obj._lp_active = False
                        return True  # Swallow the release so it doesn't activate the tool

        # Floating drag handling — press and hold the settings button to move the toolbox
        if self.isFloating() and obj == self.settings_btn:
            if event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
                self._drag_start_pos = event_global_pos(event)
                self._drag_timer.start()
                self._is_dragging = False
            elif event.type() == QEvent.Type.MouseMove and self._drag_start_pos is not None:
                if self._is_dragging:
                    delta = event_global_pos(event) - self._drag_start_pos
                    self.move(self.pos() + delta)
                    self._drag_start_pos = event_global_pos(event)
                    return True
            elif event.type() == QEvent.Type.MouseButtonRelease:
                was_dragging = self._is_dragging
                self._drag_timer.stop()
                self._drag_start_pos = None
                self._is_dragging = False
                if was_dragging:
                    self._check_dock_proximity()
                    self._clamp_to_screen()
                    self._update_window_offset()
                    return True

        # Track Krita main window moves for follow-window feature
        if self._tracked_qwindow is not None and obj == self._tracked_qwindow:
            if event.type() == QEvent.Type.Move:
                self._on_krita_window_moved()

        return super().eventFilter(obj, event)

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
dock_widget_factory = DockWidgetFactory(DOCKER_ID, DockWidgetFactoryBase.DockPosition.DockLeft, bettertoolbox)
instance.addDockWidgetFactory(dock_widget_factory)
