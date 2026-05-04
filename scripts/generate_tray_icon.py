from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPainter, QPen, QPixmap

OUTPUT_PATH = Path(__file__).resolve().parent.parent / "imgs" / "app_icon.png"

if OUTPUT_PATH.exists():
    print(True)
    raise SystemExit(0)

pixmap = QPixmap(64, 64)
pixmap.fill(Qt.GlobalColor.transparent)

painter = QPainter(pixmap)
painter.setRenderHint(QPainter.RenderHint.Antialiasing)
painter.setBrush(QColor("#1f6feb"))
painter.setPen(Qt.PenStyle.NoPen)
painter.drawRoundedRect(4, 4, 56, 56, 12, 12)
painter.setPen(QPen(QColor("white")))
font = painter.font()
font.setBold(True)
font.setPointSize(24)
painter.setFont(font)
painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "O")
painter.end()

print(pixmap.save(str(OUTPUT_PATH), "PNG"))
