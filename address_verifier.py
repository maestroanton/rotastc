"""
Módulo para verificar e validar como o Google Maps interpretou os endereços.
Este módulo captura as respostas da API do Google e compara os endereços
enviados com os endereços interpretados/geocodificados.
Também inclui diálogos para seleção e edição manual de endereços.
"""

import json
import os
from datetime import datetime
from typing import List, Dict, Any, Optional
import googlemaps
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QCheckBox, 
                              QPushButton, QScrollArea, QWidget, QLabel, 
                              QMessageBox, QLineEdit, QFormLayout)
from PyQt6.QtGui import QIcon, QFont
from stc_common.ui.dialogs import DialogManager

# Initialize dialog manager
dialog_manager = DialogManager()


class AddressVerifier:
    """
    Verifica e registra como o Google Maps interpretou os endereços fornecidos.
    Útil para identificar endereços mal interpretados ou ambíguos.
    """
    
    def __init__(self, google_api_key: str = None):
        """
        Inicializa o verificador de endereços.
        
        Args:
            google_api_key: Chave da API do Google Maps
        """
        api_key = os.getenv('GOOGLE_MAPS_API_KEY', google_api_key)
        self.gmaps = googlemaps.Client(key=api_key)
        self.verification_log = []
    
    def verify_address(self, original_address: str, context_data: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Verifica um único endereço através do geocoding do Google.
        
        Args:
            original_address: Endereço original enviado ao Google
            context_data: Dados adicionais do endereço (dicionário original)
        
        Returns:
            dict: Informações sobre como o Google interpretou o endereço
        """
        try:
            # Geocodifica o endereço para ver como o Google o interpretou
            geocode_result = self.gmaps.geocode(original_address, language='pt-BR')
            
            if not geocode_result:
                return {
                    'original_address': original_address,
                    'interpreted_address': None,
                    'status': 'NOT_FOUND',
                    'location': None,
                    'place_id': None,
                    'address_components': None,
                    'context_data': context_data,
                    'timestamp': datetime.now().isoformat()
                }
            
            # Pega o primeiro resultado (mais relevante)
            result = geocode_result[0]
            
            verification = {
                'original_address': original_address,
                'interpreted_address': result.get('formatted_address'),
                'status': 'OK',
                'location': result.get('geometry', {}).get('location'),
                'location_type': result.get('geometry', {}).get('location_type'),
                'place_id': result.get('place_id'),
                'address_components': result.get('address_components'),
                'types': result.get('types'),
                'context_data': context_data,
                'timestamp': datetime.now().isoformat()
            }
            
            # Adiciona flags de alerta se houver discrepâncias
            verification['alerts'] = self._check_for_alerts(original_address, result)
            
            return verification
            
        except Exception as e:
            return {
                'original_address': original_address,
                'interpreted_address': None,
                'status': 'ERROR',
                'error': str(e),
                'context_data': context_data,
                'timestamp': datetime.now().isoformat()
            }
    
    def verify_addresses_batch(self, addresses: List[str], context_data_list: Optional[List[Dict]] = None) -> List[Dict[str, Any]]:
        """
        Verifica múltiplos endereços em lote.
        
        Args:
            addresses: Lista de endereços originais
            context_data_list: Lista de dicionários com dados de contexto
        
        Returns:
            list: Lista de verificações para cada endereço
        """
        if context_data_list is None:
            context_data_list = [None] * len(addresses)
        
        verifications = []
        for address, context in zip(addresses, context_data_list):
            verification = self.verify_address(address, context)
            verifications.append(verification)
            self.verification_log.append(verification)
        
        return verifications
    
    def _check_for_alerts(self, original: str, geocode_result: Dict) -> List[str]:
        """
        Verifica se há alertas ou discrepâncias entre o endereço original
        e o interpretado pelo Google.
        
        Args:
            original: Endereço original
            geocode_result: Resultado do geocoding do Google
        
        Returns:
            list: Lista de alertas encontrados
        """
        alerts = []
        interpreted = geocode_result.get('formatted_address', '').lower()
        original_lower = original.lower()
        
        # Verifica se o tipo de localização é impreciso
        location_type = geocode_result.get('geometry', {}).get('location_type')
        if location_type in ['APPROXIMATE', 'GEOMETRIC_CENTER']:
            alerts.append(f"Localização aproximada (tipo: {location_type})")
        
        # Verifica se é uma área ampla em vez de endereço específico
        types = geocode_result.get('types', [])
        vague_types = ['locality', 'administrative_area_level_1', 'administrative_area_level_2', 'country']
        if any(t in types for t in vague_types) and 'street_address' not in types:
            alerts.append(f"Endereço vago ou área ampla (tipos: {', '.join(types[:3])})")
        
        # Verifica mudanças significativas no nome da rua/localidade
        # Extrai palavras significativas (mais de 3 caracteres) do endereço original
        original_words = set([w for w in original_lower.split() if len(w) > 3])
        interpreted_words = set([w for w in interpreted.split() if len(w) > 3])
        
        # Verifica se a cidade mudou
        original_cities = self._extract_city_name(original_lower)
        interpreted_cities = self._extract_city_name(interpreted)
        if original_cities and interpreted_cities and original_cities != interpreted_cities:
            alerts.append(f"Cidade mudou: '{original_cities}' → '{interpreted_cities}'")
        
        return alerts
    
    def _extract_city_name(self, address: str) -> Optional[str]:
        """
        Tenta extrair o nome da cidade do endereço.
        
        Args:
            address: String do endereço
        
        Returns:
            str: Nome da cidade ou None
        """
        # Lista de cidades comuns no Ceará (pode ser expandida)
        cities = ['fortaleza', 'caucaia', 'juazeiro do norte', 'maracanaú', 'sobral', 
                  'crato', 'itapipoca', 'maranguape', 'iguatu', 'quixadá']
        
        address_lower = address.lower()
        for city in cities:
            if city in address_lower:
                return city
        
        return None
    
    def save_verification_json(self, output_path: str):
        """
        Salva as verificações em formato JSON.
        
        Args:
            output_path: Caminho para salvar o arquivo JSON
        """
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(self.verification_log, f, ensure_ascii=False, indent=2)
    
    def clear_log(self):
        """Limpa o log de verificações."""
        self.verification_log = []
    
    def get_problematic_addresses(self, include_not_found: bool = True, include_alerts: bool = True) -> List[Dict]:
        """
        Retorna apenas os endereços problemáticos.
        
        Args:
            include_not_found: Incluir endereços não encontrados
            include_alerts: Incluir endereços com alertas
        
        Returns:
            list: Lista de verificações problemáticas
        """
        problematic = []
        
        for verification in self.verification_log:
            is_problematic = False
            
            if include_not_found and verification['status'] == 'NOT_FOUND':
                is_problematic = True
            
            if include_alerts and verification.get('alerts'):
                is_problematic = True
            
            if verification['status'] == 'ERROR':
                is_problematic = True
            
            if is_problematic:
                problematic.append(verification)
        
        return problematic


class AddressEditDialog(QDialog):
    """Dialog para editar um endereço individual."""
    
    def __init__(self, address, formatter_func, parent=None):
        super().__init__(parent)
        self.address = address.copy()  # Work with a copy
        self.formatter_func = formatter_func
        
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
    """Dialog para seleção de endereços com checkboxes e opção de edição."""
    
    def __init__(self, addresses, formatter_func, parent=None):
        super().__init__(parent)
        self.addresses = addresses
        self.formatter_func = formatter_func
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
        
        # Track seen formatted addresses to identify duplicates
        seen_formatted_addresses = {}
        
        # Scroll area for checkboxes
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        
        # Create checkboxes with edit buttons for each address
        for idx, addr in enumerate(self.addresses, 1):
            # Format the address to check for duplicates
            formatted_address = self.formatter_func(addr)
            is_duplicate = formatted_address in seen_formatted_addresses
            
            # Track this formatted address
            if not is_duplicate:
                seen_formatted_addresses[formatted_address] = idx - 1
            
            # Horizontal layout for checkbox and edit button
            row_layout = QHBoxLayout()
            
            checkbox = QCheckBox(f"Endereço {idx}: {formatted_address}")
            # Check by default, but uncheck if it's a duplicate
            checkbox.setChecked(not is_duplicate)
            checkbox.setStyleSheet("QCheckBox { padding: 5px; }")
            
            # Disable editing and selecting for duplicates
            if is_duplicate:
                checkbox.setEnabled(False)
                checkbox.setToolTip(f"Duplicado do Endereço {seen_formatted_addresses[formatted_address] + 1}")
            
            self.checkboxes.append(checkbox)
            row_layout.addWidget(checkbox, 1)  # Stretch factor 1
            
            # Edit button
            edit_btn = QPushButton("Editar")
            edit_btn.setFixedWidth(80)
            edit_btn.clicked.connect(lambda checked, index=idx-1: self.edit_address(index))
            # Disable edit button for duplicates
            edit_btn.setEnabled(not is_duplicate)
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
        edit_dialog = AddressEditDialog(self.addresses[index], self.formatter_func, self)
        if edit_dialog.exec() == QDialog.DialogCode.Accepted:
            # Update the address in the list
            self.addresses[index] = edit_dialog.get_address()
            # Update the checkbox text
            self.checkboxes[index].setText(
                f"Endereço {index + 1}: {self.formatter_func(self.addresses[index])}"
            )
    
    def select_all(self):
        """Marca todos os checkboxes (exceto duplicados desabilitados)."""
        for checkbox in self.checkboxes:
            if checkbox.isEnabled():
                checkbox.setChecked(True)
    
    def deselect_all(self):
        """Desmarca todos os checkboxes (exceto duplicados desabilitados)."""
        for checkbox in self.checkboxes:
            if checkbox.isEnabled():
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
