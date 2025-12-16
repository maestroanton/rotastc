"""
Módulo contendo diálogos personalizados para a aplicação.

Nota: Os diálogos AddressEditDialog e AddressSelectionDialog foram movidos para
address_verifier.py para manter a lógica de verificação de endereços centralizada.
"""

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QCheckBox, 
                              QPushButton, QScrollArea, QWidget, QLabel, 
                              QMessageBox, QLineEdit, QFormLayout, QGroupBox)
from PyQt6.QtGui import QIcon, QFont
from stc_common.ui.dialogs import DialogManager


# Initialize dialog manager
dialog_manager = DialogManager()

# Dialogs moved to address_verifier.py:
# - AddressEditDialog
# - AddressSelectionDialog
