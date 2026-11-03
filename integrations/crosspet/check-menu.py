from collections import defaultdict
from unittest.mock import patch
from PyQt6.QtWidgets import QApplication, QWidget
from PyQt6.QtTest import QTest
from PyQt6.QtCore import QPoint
from crosspet.ui import Pet
from crosspet import core
app=QApplication([])
class Dummy(QWidget):
    def __init__(self):
        super().__init__()
        self.character='deepseek'; self.settings=defaultdict(bool, layer='normal', skins={}, menuReduceTransparency=True, menuReduceMotion=True); self.skin_choices={}; self.characters={c:{'name':c} for c in core.CHARACTERS}; self.tray=None
    def __getattr__(self,name):
        return lambda *args, **kwargs: None
pet=Dummy()
menu=Pet.make_menu(pet)
action=next(a for a in menu.actions() if a.text()=='桌面便签')
assert action.isEnabled() and action.property('glassSymbol')=='todo-note'
menu.popup(QPoint(30,30)); QTest.qWait(100)
assert not menu.grab().isNull()
with patch('crosspet.ui.subprocess.Popen') as launch:
    action.trigger()
    assert launch.call_args.args[0][0].endswith('/.local/bin/linux-todo-notes')
print('Installed menu action, icon and launcher: OK')
menu.close()
