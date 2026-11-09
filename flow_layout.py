# -*- coding: utf-8 -*-
"""FlowLayout — layout tipo Qt oficial que envuelve los widgets a la
siguiente línea en vez de forzar un ancho mínimo gigante (como hace
QHBoxLayout cuando no caben todos los botones)."""
from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtWidgets import QLayout


class FlowLayout(QLayout):
    def __init__(self, parent=None, margin: int = 0, hspacing: int = 8, vspacing: int = 8):
        super().__init__(parent)
        self._hspacing = hspacing
        self._vspacing = vspacing
        self._items = []
        self.setContentsMargins(margin, margin, margin, margin)

    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, index):
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index):
        return self._items.pop(index) if 0 <= index < len(self._items) else None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._do_layout(QRect(0, 0, width, 0), True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._do_layout(rect, False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        left, top, right, bottom = self.getContentsMargins()
        size += QSize(left + right, top + bottom)
        return size

    def _do_layout(self, rect, test_only):
        left, top, right, bottom = self.getContentsMargins()
        effective = rect.adjusted(left, top, -right, -bottom)
        x, y = effective.x(), effective.y()
        line_height = 0

        for item in self._items:
            hint = item.sizeHint()
            next_x = x + hint.width() + self._hspacing
            if next_x - self._hspacing > effective.right() and line_height > 0:
                x = effective.x()
                y += line_height + self._vspacing
                next_x = x + hint.width() + self._hspacing
                line_height = 0
            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), hint))
            x = next_x
            line_height = max(line_height, hint.height())

        return y + line_height - rect.y() + bottom
