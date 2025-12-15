"""
Módulo contendo diálogos personalizados para a aplicação.
"""

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QCheckBox, 
                              QPushButton, QScrollArea, QWidget, QLabel, 
                              QMessageBox, QLineEdit, QFormLayout, QGroupBox)
from PyQt6.QtGui import QIcon, QFont
from stc_common.ui.dialogs import DialogManager


# Initialize dialog manager
dialog_manager = DialogManager()


class AddressEditDialog(QDialog):
    """Dialog para editar um endereço individual."""
    
    def __init__(self, address, extractor, parent=None):
        super().__init__(parent)
        self.address = address.copy()  # Work with a copy
        self.extractor = extractor
        
        self.setWindowTitle("Editar Endereço")
        self.setMinimumWidth(500)
        
        # Set window icon
        icon_path = dialog_manager.get_icon_path()
        if icon_path:
            self.setWindowIcon(QIcon(icon_path))
        
        self.init_ui()
    
    def init_ui(self):
        """Inicializa a interface do diálogo."""
        layout = QVBoxLayout()
        
        # Form for address fields
        form_layout = QFormLayout()
        
        # Logradouro
        self.logradouro_edit = QLineEdit(self.address.get('logradouro', ''))
        form_layout.addRow("Logradouro:", self.logradouro_edit)
        
        # Número
        self.numero_edit = QLineEdit(self.address.get('numero', ''))
        form_layout.addRow("Número:", self.numero_edit)
        
        # Complemento
        self.complemento_edit = QLineEdit(self.address.get('complemento', ''))
        form_layout.addRow("Complemento:", self.complemento_edit)
        
        # Bairro
        self.bairro_edit = QLineEdit(self.address.get('bairro', ''))
        form_layout.addRow("Bairro:", self.bairro_edit)
        
        # Cidade
        self.cidade_edit = QLineEdit(self.address.get('cidade', ''))
        form_layout.addRow("Cidade:", self.cidade_edit)
        
        # Estado
        self.estado_edit = QLineEdit(self.address.get('estado', ''))
        form_layout.addRow("Estado:", self.estado_edit)
        
        # CEP
        self.cep_edit = QLineEdit(self.address.get('cep', ''))
        form_layout.addRow("CEP:", self.cep_edit)
        
        layout.addLayout(form_layout)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        save_btn = QPushButton("Salvar")
        save_btn.setDefault(True)
        save_btn.clicked.connect(self.save_address)
        button_layout.addWidget(save_btn)
        
        cancel_btn = QPushButton("Cancelar")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def save_address(self):
        """Salva as alterações do endereço."""
        self.address['logradouro'] = self.logradouro_edit.text().strip()
        self.address['numero'] = self.numero_edit.text().strip()
        self.address['complemento'] = self.complemento_edit.text().strip()
        self.address['bairro'] = self.bairro_edit.text().strip()
        self.address['cidade'] = self.cidade_edit.text().strip()
        self.address['estado'] = self.estado_edit.text().strip()
        self.address['cep'] = self.cep_edit.text().strip()
        
        # Validate that at least logradouro and cidade are filled
        if not self.address['logradouro'] or not self.address['cidade']:
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.setWindowTitle("Aviso")
            msg.setText("Logradouro e Cidade são obrigatórios!")
            msg.exec()
            return
        
        self.accept()
    
    def get_address(self):
        """Retorna o endereço editado."""
        return self.address


class AddressSelectionDialog(QDialog):
    """Dialog para seleção de endereços com checkboxes."""
    
    def __init__(self, addresses, extractor, parent=None):
        super().__init__(parent)
        self.addresses = addresses
        self.extractor = extractor
        self.checkboxes = []
        self.selected_addresses = []
        
        self.setWindowTitle("Seleção de Endereços")
        self.setMinimumWidth(600)
        self.setMinimumHeight(400)
        
        # Set window icon
        icon_path = dialog_manager.get_icon_path()
        if icon_path:
            self.setWindowIcon(QIcon(icon_path))
        
        self.init_ui()
    
    def init_ui(self):
        """Inicializa a interface do diálogo."""
        layout = QVBoxLayout()
        
        # Title label
        title_label = QLabel(f"Total de endereços encontrados: {len(self.addresses)}")
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(10)
        title_label.setFont(title_font)
        layout.addWidget(title_label)
        
        # Instruction label
        instruction_label = QLabel("Desmarque os endereços que NÃO deseja incluir na rota:")
        layout.addWidget(instruction_label)
        
        # Scroll area for checkboxes
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        
        # Create checkboxes with edit buttons for each address
        for idx, addr in enumerate(self.addresses, 1):
            # Horizontal layout for checkbox and edit button
            row_layout = QHBoxLayout()
            
            checkbox = QCheckBox(f"Endereço {idx}: {self.extractor.format_address(addr)}")
            checkbox.setChecked(True)  # All addresses are checked by default
            checkbox.setStyleSheet("QCheckBox { padding: 5px; }")
            self.checkboxes.append(checkbox)
            row_layout.addWidget(checkbox, 1)  # Stretch factor 1
            
            # Edit button
            edit_btn = QPushButton("Editar")
            edit_btn.setFixedWidth(80)
            edit_btn.clicked.connect(lambda checked, index=idx-1: self.edit_address(index))
            row_layout.addWidget(edit_btn)
            
            scroll_layout.addLayout(row_layout)
        
        scroll_layout.addStretch()
        scroll_area.setWidget(scroll_widget)
        layout.addWidget(scroll_area)
        
        # Buttons layout
        button_layout = QHBoxLayout()
        
        # Select All button
        select_all_btn = QPushButton("Marcar Todos")
        select_all_btn.clicked.connect(self.select_all)
        button_layout.addWidget(select_all_btn)
        
        # Deselect All button
        deselect_all_btn = QPushButton("Desmarcar Todos")
        deselect_all_btn.clicked.connect(self.deselect_all)
        button_layout.addWidget(deselect_all_btn)
        
        button_layout.addStretch()
        
        # Confirm button
        confirm_btn = QPushButton("Confirmar Seleção")
        confirm_btn.setDefault(True)
        confirm_btn.clicked.connect(self.confirm_selection)
        button_layout.addWidget(confirm_btn)
        
        # Cancel button
        cancel_btn = QPushButton("Cancelar")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def edit_address(self, index):
        """Abre dialog para editar um endereço específico."""
        edit_dialog = AddressEditDialog(self.addresses[index], self.extractor, self)
        if edit_dialog.exec() == QDialog.DialogCode.Accepted:
            # Update the address in the list
            self.addresses[index] = edit_dialog.get_address()
            # Update the checkbox text
            self.checkboxes[index].setText(
                f"Endereço {index + 1}: {self.extractor.format_address(self.addresses[index])}"
            )
    
    def select_all(self):
        """Marca todos os checkboxes."""
        for checkbox in self.checkboxes:
            checkbox.setChecked(True)
    
    def deselect_all(self):
        """Desmarca todos os checkboxes."""
        for checkbox in self.checkboxes:
            checkbox.setChecked(False)
    
    def confirm_selection(self):
        """Confirma a seleção e fecha o diálogo."""
        self.selected_addresses = []
        for idx, checkbox in enumerate(self.checkboxes):
            if checkbox.isChecked():
                self.selected_addresses.append(self.addresses[idx])
        
        if not self.selected_addresses:
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.setWindowTitle("Aviso")
            msg.setText("Você deve selecionar pelo menos um endereço!")
            msg.exec()
            return
        
        self.accept()
    
    def get_selected_addresses(self):
        """Retorna a lista de endereços selecionados."""
        return self.selected_addresses
