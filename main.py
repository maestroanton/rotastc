"""
Aplicação para processar PDFs e criar rotas.
"""

import sys
from PyQt6.QtWidgets import QApplication, QMessageBox, QDialog
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from stc_common.ui.dialogs import DialogManager
from address_extractor import AddressExtractor
from route_generator import RouteGenerator
from dialog import AddressSelectionDialog

# Initialize dialog manager
dialog_manager = DialogManager()


def show_results_dialog(text, addresses, extractor, route_generator):
    """Mostra os resultados em um dialog modal que realmente bloqueia."""
    
    if addresses:
        # Show address selection dialog first
        selection_dialog = AddressSelectionDialog(addresses, extractor)
        if selection_dialog.exec() != QDialog.DialogCode.Accepted:
            return QMessageBox.StandardButton.Cancel
        
        # Get selected addresses
        selected_addresses = selection_dialog.get_selected_addresses()
        
        # Show optimization dialog
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Icon.Information)
        
        # Set window icon
        icon_path = dialog_manager.get_icon_path()
        if icon_path:
            msg.setWindowIcon(QIcon(icon_path))
        
        msg.setWindowTitle("Otimização de Rota")
        msg.setText(f"{len(selected_addresses)} endereço(s) selecionado(s).\n\nDeseja otimizar a rota usando distâncias reais?")
        
        # Format selected addresses
        formatted_addresses = []
        for idx, addr in enumerate(selected_addresses, 1):
            formatted_addresses.append(f"Endereço {idx}:")
            formatted_addresses.append(extractor.format_address(addr))
            formatted_addresses.append("-" * 50)
        
        msg.setDetailedText('\n'.join(formatted_addresses))
        msg.setStandardButtons(QMessageBox.StandardButton.Yes | 
                               QMessageBox.StandardButton.No | 
                               QMessageBox.StandardButton.Cancel)
        
        result = msg.exec()
        
        optimize = False
        if result == QMessageBox.StandardButton.Yes:
            optimize = True
        elif result == QMessageBox.StandardButton.Cancel:
            return result
        
        # Use selected addresses instead of all addresses
        addresses = selected_addresses
        
        # Pergunta o que fazer com a rota
        action_msg = QMessageBox()
        action_msg.setIcon(QMessageBox.Icon.Question)
        if icon_path:
            action_msg.setWindowIcon(QIcon(icon_path))
        action_msg.setWindowTitle("Ação")
        action_msg.setText("O que deseja fazer com a rota?")
        open_browser_btn = action_msg.addButton("Abrir no Navegador", QMessageBox.ButtonRole.YesRole)
        save_file_btn = action_msg.addButton("Salvar em Arquivo", QMessageBox.ButtonRole.NoRole)
        cancel_btn = action_msg.addButton("Cancelar", QMessageBox.ButtonRole.RejectRole)
        
        action_msg.exec()
        clicked_button = action_msg.clickedButton()
        
        try:
            if clicked_button == open_browser_btn:
                urls = route_generator.open_route_in_browser(addresses, optimize=optimize)
                info_msg = QMessageBox()
                info_msg.setIcon(QMessageBox.Icon.Information)
                if icon_path:
                    info_msg.setWindowIcon(QIcon(icon_path))
                info_msg.setWindowTitle("Rota Criada")
                
                if isinstance(urls, list):
                    info_msg.setText(f"{len(urls)} rotas {'otimizadas' if optimize else 'sequenciais'} abertas no navegador!\n\n(Rota dividida devido ao limite do Google Maps)")
                    url_text = '\n\n'.join([f"Rota {i+1}:\n{url}" for i, url in enumerate(urls)])
                    info_msg.setDetailedText(url_text)
                else:
                    info_msg.setText(f"Rota {'otimizada' if optimize else 'sequencial'} aberta no navegador!")
                    info_msg.setDetailedText(f"URL da rota:\n{urls}")
                info_msg.exec()
            elif clicked_button == save_file_btn:
                filename = route_generator.save_route_to_file(addresses, optimize=optimize)
                info_msg = QMessageBox()
                info_msg.setIcon(QMessageBox.Icon.Information)
                if icon_path:
                    info_msg.setWindowIcon(QIcon(icon_path))
                info_msg.setWindowTitle("Rota Salva")
                info_msg.setText(f"Rota {'otimizada' if optimize else 'sequencial'} salva em:\n{filename}")
                info_msg.exec()
        except Exception as e:
            error_msg = QMessageBox()
            error_msg.setIcon(QMessageBox.Icon.Critical)
            if icon_path:
                error_msg.setWindowIcon(QIcon(icon_path))
            error_msg.setWindowTitle("Erro")
            error_msg.setText(f"Erro ao processar rota: {str(e)}")
            error_msg.exec()
        
        return result
    else:
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Icon.Information)
        
        # Set window icon
        icon_path = dialog_manager.get_icon_path()
        if icon_path:
            msg.setWindowIcon(QIcon(icon_path))
        
        msg.setWindowTitle("Texto Extraído")
        msg.setText("Nenhum endereço encontrado.\n\nClique em 'Show Details' para ver o texto extraído.")
        msg.setDetailedText(text)
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)
        return msg.exec()


def main():
    """Função principal da aplicação."""
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    # Select PDF
    pdf_file = dialog_manager.show_select_pdf_dialog(None)
    if not pdf_file:
        return 0
    
    # Show loading dialog
    loading_dict = dialog_manager.show_loading_dialog(None)
    app.processEvents()
    
    # Process PDF synchronously with pdfplumber
    extractor = AddressExtractor()
    
    def update_progress(msg, prog):
        dialog_manager.update_loading_progress(loading_dict, msg, prog)
        app.processEvents()
    
    try:
        text = extractor.extract_text_from_pdf(pdf_file, progress_callback=update_progress)
        
        # Extract and validate addresses with AI
        if text:
            addresses = extractor.extract_addresses(text, use_ai_validation=True, progress_callback=update_progress)
            
            # Close loading
            dialog_manager.close_loading_dialog(loading_dict)
            app.processEvents()
            
            # Show results
            route_generator = RouteGenerator()
            show_results_dialog(text, addresses, extractor, route_generator)
        else:
            # Close loading
            dialog_manager.close_loading_dialog(loading_dict)
            app.processEvents()
            dialog_manager.show_error_dialog("PDF não contém texto extraível.", None)
    except Exception as e:
        # Close loading
        dialog_manager.close_loading_dialog(loading_dict)
        app.processEvents()
        dialog_manager.show_error_dialog(f"Erro ao processar PDF: {str(e)}", None)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())