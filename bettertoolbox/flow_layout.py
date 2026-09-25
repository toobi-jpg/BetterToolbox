from bettertoolbox.qt_compat import QLayout, QSizePolicy, Qt, QRect, QPoint, QSize
class FlowLayout(QLayout):
    def __init__(self, parent = None, margin = 0, spacing = 10):
        super().__init__(parent)
        self.margin = margin
        self.setContentsMargins(margin, margin, margin, margin)
        self.setSpacing(spacing)
        self.itemList = []
    def addItem(self, item):
        self.itemList.append(item)
    def count(self):
        return len(self.itemList)
    def itemAt(self, index):
        if index >= 0 and index < len(self.itemList):
            return self.itemList[index]
        return None
    def takeAt(self, index):
        if index >= 0 and index < len(self.itemList):
            return self.itemList.pop(index)
        return None
    def expandingDirections(self):
        return Qt.Orientation(0)
    def hasHeightForWidth(self):
        return True
    def heightForWidth(self, width):
        height = self.doLayout(QRect(0, 0, width, 0), True)
        return height
    def setGeometry(self, rect):
        super(FlowLayout, self).setGeometry(rect)
        self.doLayout(rect, False)
    def sizeHint(self):
        return self.minimumSize()
    def minimumSize(self):
        size = QSize()
        for item in self.itemList:
            size = size.expandedTo(item.minimumSize())
        m = self.contentsMargins()
        size += QSize(m.left() + m.right(), m.top() + m.bottom())
        return size
    def doLayout(self, rect, testOnly):
        m = self.contentsMargins()
        area = rect.adjusted(m.left(), m.top(), -m.right(), -m.bottom())
        lines = []
        currentLine = []
        lineWidth = 0
        spacing = self.spacing()
        for item in self.itemList:
            if item.isEmpty():
                continue  # hidden widgets take no space
            hint = item.sizeHint()
            if lineWidth + hint.width() > area.width() and currentLine:
                lines.append((currentLine, lineWidth - spacing))
                currentLine = []
                lineWidth = 0
            currentLine.append((item, hint))
            lineWidth += hint.width() + spacing
        if currentLine:
            lines.append((currentLine, lineWidth - spacing))
        y = area.y()
        for lineItems, totalLineWidth in lines:
            lineHeight = 0
            x = area.x() + max(0, (area.width() - totalLineWidth) / 2)
            for item, hint in lineItems:
                if not testOnly:
                    item.setGeometry(QRect(QPoint(int(x), y), hint))
                x += hint.width() + spacing
                lineHeight = max(lineHeight, hint.height())
            y += lineHeight + spacing
        if lines:
            y -= spacing  # no gap after the last line
        return y - rect.y() + m.bottom()
