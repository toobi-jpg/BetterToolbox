from PyQt5.QtWidgets import QLayout, QSizePolicy
from PyQt5.QtCore import Qt, QRect, QPoint, QSize
class FlowLayout(QLayout):
    def __init__(self, parent = None, margin = 0, spacing = 10):
        super().__init__(parent)
        self.margin = margin
        if parent is not None:
            self.setContentsMargins(margin, margin, margin, margin)
        self.setSpacing(spacing)
        self.itemList = []
    def __del__(self):
        item = self.takeAt(0)
        while item:
            item = self.takeAt(0)
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
        return Qt.Orientations(Qt.Orientation(0))
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
        size += QSize(2 * self.margin, 2 * self.margin)
        return size
    def doLayout(self, rect, testOnly):
        lines = []
        currentLine = []
        lineWidth = 0
        spacing = self.spacing()
        for item in self.itemList:
            itemWidth = item.sizeHint().width()
            if lineWidth + itemWidth > rect.width() and currentLine:
                lines.append((currentLine, lineWidth - spacing))
                currentLine = []
                lineWidth = 0
            currentLine.append(item)
            lineWidth += itemWidth + spacing
        if currentLine:
            lines.append((currentLine, lineWidth - spacing))
        y = rect.y()
        for lineItems, totalLineWidth in lines:
            lineHeight = 0
            offsetX = max(0, (rect.width() - totalLineWidth) / 2)
            x = rect.x() + offsetX
            for item in lineItems:
                if not testOnly:
                    item.setGeometry(QRect(QPoint(int(x), y), item.sizeHint()))
                x += item.sizeHint().width() + spacing
                lineHeight = max(lineHeight, item.sizeHint().height())
            y += lineHeight + spacing
        return y - rect.y()
