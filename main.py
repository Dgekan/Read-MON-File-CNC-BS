# pyside2-uic window.ui > ui_window.py -x -o
import sys,os
from PyQt5 import QtCore, QtGui, QtWidgets, uic, QtPrintSupport
from PyQt5.QtWidgets import QMainWindow,QMessageBox
from PyQt5.Qt import QLabel, QPixmap, Qt

class MyWindow(QMainWindow):
    def __init__(self,parent=None):
        super().__init__(parent)
        # Фаил формы
        uic.loadUi("mainwindow.ui",self)
        # Заголовок 
        self.setWindowTitle("Control Program Editor CNC. Ver.4.0.0 ")
        item = QtGui.QStandardItem()
        self.model =  QtGui.QStandardItemModel(self)
        self.model.appendRow(item)
        self.model.insertColumn(0)
        self.model.setHeaderData(0,Qt.Horizontal,"Х ")
        self.model.setHeaderData(1,Qt.Horizontal,"Z") 
        self.model.setHeaderData(2,Qt.Horizontal,"У") 
        self.tableView.resizeColumnsToContents()      
        self.tableView.setModel(self.model)
        self.tableView.setShowGrid(True)

if __name__ == "__main__":
       
    app = QtWidgets.QApplication(sys.argv)
    widget = MyWindow()
    widget.show()
   
    sys.exit(app.exec_())

