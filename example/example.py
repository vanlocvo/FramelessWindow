import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from FramelessWindow import FramelessWindow, SYSTEMTHEME


class ExampleWindow(FramelessWindow):
    def __init__(self):
        super().__init__()
        self.resize(640, 480)
        self.setWindowTitle("Frameless Window")
        self.setWindowIcon(QIcon("logo.svg"))
        print(SYSTEMTHEME.AccentColor)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    example_win = ExampleWindow()
    example_win.show()
    sys.exit(app.exec())
