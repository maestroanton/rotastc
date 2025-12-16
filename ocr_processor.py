"""
Módulo para processar PDFs usando OCR Space API.
"""

import requests
import os
import sys

try:
    from dotenv import load_dotenv
    # Load .env from the correct location for both development and PyInstaller
    if getattr(sys, 'frozen', False):
        # Running as PyInstaller executable
        env_path = os.path.join(sys._MEIPASS, '.env')
    else:
        # Running in development
        env_path = '.env'
    load_dotenv(env_path)
except ImportError:
    # python-dotenv not installed; env vars must be set manually
    pass


class OCRProcessor:
    """Processa arquivos PDF usando OCR Space API."""
    
    def __init__(self, api_key=None):
        """
        Inicializa o processador OCR.
        
        Args:
            api_key: Chave da API do OCR Space
        """
        # Prefer environment variable, fall back to constructor arg
        self.api_key = os.getenv('OCR_SPACE_API_KEY', api_key)
        self.api_url = "https://api.ocr.space/parse/image"
    
    def process_pdf(self, pdf_path, language='por', progress_callback=None):
        """
        Processa um arquivo PDF e extrai o texto via OCR.
        
        Args:
            pdf_path: Caminho para o arquivo PDF
            language: Código do idioma (por=português, eng=inglês)
            progress_callback: Função callback para atualizar progresso
        
        Returns:
            dict: Resultado do OCR contendo texto extraído e informações
        """
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"Arquivo não encontrado: {pdf_path}")
        
        if progress_callback:
            progress_callback("Enviando PDF para processamento OCR...", 10)
        
        # Preparar payload para API
        payload = {
            'apikey': self.api_key,
            'language': language,
            'isOverlayRequired': False,
            'detectOrientation': True,
            'scale': True,
            'OCREngine': 2,  # Engine 2 é melhor para PDFs
            'filetype': 'PDF'
        }
        
        try:
            with open(pdf_path, 'rb') as f:
                files = {'file': f}
                
                if progress_callback:
                    progress_callback("Processando com OCR...", 30)
                
                response = requests.post(
                    self.api_url,
                    files=files,
                    data=payload,
                    timeout=60
                )
                
                if progress_callback:
                    progress_callback("Analisando resultado...", 70)
                
                response.raise_for_status()
                result = response.json()
                
                if progress_callback:
                    progress_callback("OCR concluído!", 100)
                
                return self._parse_result(result)
                
        except requests.exceptions.Timeout:
            raise Exception("Timeout ao processar PDF. Tente novamente.")
        except requests.exceptions.RequestException as e:
            raise Exception(f"Erro na requisição: {str(e)}")
        except Exception as e:
            raise Exception(f"Erro ao processar PDF: {str(e)}")
    
    def _parse_result(self, result):
        """
        Analisa o resultado da API e extrai informações relevantes.
        
        Args:
            result: Resposta JSON da API
        
        Returns:
            dict: Dados processados
        """
        print(f"DEBUG OCR Result: {result}")  # Debug
        
        # Check if processing was successful
        is_errored = result.get('IsErroredOnProcessing', False)
        
        if not is_errored:
            parsed_results = result.get('ParsedResults', [])
            
            if parsed_results:
                text = parsed_results[0].get('ParsedText', '')
                exit_code = parsed_results[0].get('ExitCode', 0)
                error_message = parsed_results[0].get('ErrorMessage', '')
                
                print(f"DEBUG: Extracted text length: {len(text)}")  # Debug
                
                return {
                    'success': True,
                    'text': text,
                    'exit_code': exit_code,
                    'error_message': error_message,
                    'pages': len(parsed_results)
                }
        
        # Se houver erro
        error_msg = result.get('ErrorMessage', ['Erro desconhecido'])
        if isinstance(error_msg, list):
            error_msg = ', '.join(error_msg)
        
        return {
            'success': False,
            'text': '',
            'error_message': error_msg
        }
