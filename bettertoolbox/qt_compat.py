# Krita 5.x ships PyQt5, Krita 6 ships PyQt6 — and each one refuses to import the other.
try:
    from PyQt5.QtCore import *
    from PyQt5.QtGui import *
    from PyQt5.QtWidgets import *
    from PyQt5.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply
except ImportError:
    from PyQt6.QtCore import *
    from PyQt6.QtGui import *
    from PyQt6.QtWidgets import *
    from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply

def event_global_pos(event):
    """Global QPoint of a mouse event (globalPos() was removed in Qt6)."""
    if hasattr(event, "globalPosition"):
        return event.globalPosition().toPoint()
    return event.globalPos()

def event_pos(event):
    """Local QPoint of a drop event (QDropEvent.pos() was removed in Qt6)."""
    if hasattr(event, "position"):
        return event.position().toPoint()
    return event.pos()
