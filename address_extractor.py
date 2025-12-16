"""
Módulo para extrair e processar endereços de PDFs usando pdfplumber.
"""

import re
import pdfplumber
import requests
import json
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


class AddressExtractor:
    """Extrai endereços diretamente de PDFs usando pdfplumber."""
    
    def __init__(self, deepseek_api_key=None):
        # Estados brasileiros
        self.estados = ['AC', 'AL', 'AP', 'AM', 'BA', 'CE', 'DF', 'ES', 'GO', 'MA', 
                       'MT', 'MS', 'MG', 'PA', 'PB', 'PR', 'PE', 'PI', 'RJ', 'RN', 
                       'RS', 'RO', 'RR', 'SC', 'SP', 'SE', 'TO']
        # Prefer environment variable if set
        self.deepseek_api_key = os.getenv('DEEPSEEK_API_KEY', deepseek_api_key)
        self.deepseek_api_url = "https://api.deepseek.com/v1/chat/completions"
    
    def extract_text_from_pdf(self, pdf_path, progress_callback=None):
        """
        Extrai texto de um PDF usando pdfplumber.
        
        Args:
            pdf_path: Caminho para o arquivo PDF
            progress_callback: Função callback para atualizar progresso
        
        Returns:
            str: Texto extraído do PDF
        """
        if progress_callback:
            progress_callback("Abrindo PDF...", 10)
        
        text_parts = []
        
        try:
            with pdfplumber.open(pdf_path) as pdf:
                total_pages = len(pdf.pages)
                
                for i, page in enumerate(pdf.pages, 1):
                    if progress_callback:
                        progress = 10 + (80 * i // total_pages)
                        progress_callback(f"Processando página {i} de {total_pages}...", progress)
                    
                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(page_text)
                
                if progress_callback:
                    progress_callback("Extração concluída!", 100)
                
                return '\n'.join(text_parts)
        
        except Exception as e:
            raise Exception(f"Erro ao processar PDF com pdfplumber: {str(e)}")
    
    def _validate_addresses_with_deepseek(self, candidate_addresses, progress_callback=None):
        """
        Usa DeepSeek AI para validar e filtrar endereços reais.
        
        Args:
            candidate_addresses: Lista de possíveis endereços extraídos
            progress_callback: Função callback para atualizar progresso
        
        Returns:
            list: Lista de endereços validados como reais
        """
        if not candidate_addresses:
            return []
        
        if progress_callback:
            progress_callback("Validando endereços com IA...", 90)
        
        # Formata os endereços candidatos para enviar ao DeepSeek
        addresses_text = []
        for idx, addr in enumerate(candidate_addresses, 1):
            addr_str = f"{idx}. {self.format_address(addr)}"
            addresses_text.append(addr_str)
        
        print(f"\n=== DEBUG: Enviando {len(candidate_addresses)} endereços para validação ===")
        for addr_text in addresses_text:
            print(addr_text)
        print("=" * 60)
        
        prompt = f"""Analise a lista abaixo e identifique APENAS os endereços completos e válidos do Brasil.

IMPORTANTE: Um endereço válido DEVE conter um nome de logradouro com número ou S/N.
O CEP NÃO é obrigatório - aceite endereços com ou sem CEP.

Tipos de logradouro aceitos: RUA, AVENIDA (AV), RODOVIA (ROD), TRAVESSA (TRAV), ESTRADA (EST), VIA, ALAMEDA, PRAÇA, PV, R, etc.

NÃO considere como endereço válido:
- Apenas CEP sozinho
- Apenas nome de cidade/estado
- Cabeçalhos ou títulos
- Nomes de empresas
- Dados de nota fiscal
- Linhas sem nome de rua/logradouro

Um endereço válido deve ter pelo menos: nome da rua/avenida/estrada/PV + número (ou S/N) + cidade.
O bairro e CEP são opcionais.

Exemplos de endereços VÁLIDOS:
- PV CARRASCO S/N, ICARAI AMONTADA - CE
- RUA DAS FLORES 123, CENTRO FORTALEZA - CE
- AVENIDA BRASIL S/N, SAO PAULO - SP

Lista para análise:
{chr(10).join(addresses_text)}

Responda APENAS com um array JSON contendo os números dos endereços VÁLIDOS.
Exemplo de resposta: [1, 3, 5]
Se nenhum endereço for válido, responda: []"""

        try:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.deepseek_api_key}"
            }
            
            payload = {
                "model": "deepseek-chat",
                "messages": [
                    {"role": "system", "content": "Você é um assistente especializado em validar endereços brasileiros. Responda apenas com JSON válido."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.1,
                "max_tokens": 500
            }
            
            response = requests.post(
                self.deepseek_api_url,
                headers=headers,
                json=payload,
                timeout=30
            )
            
            response.raise_for_status()
            result = response.json()
            
            # Extrai a resposta
            ai_response = result['choices'][0]['message']['content'].strip()
            
            print(f"\n=== DEBUG: Resposta do DeepSeek ===")
            print(ai_response)
            print("=" * 60)
            
            # Parse o JSON da resposta
            # Remove markdown code blocks se houver
            ai_response = ai_response.replace('```json', '').replace('```', '').strip()
            valid_indices = json.loads(ai_response)
            
            print(f"\n=== DEBUG: Índices validados: {valid_indices} ===")
            print(f"=== DEBUG: Retornando {len(valid_indices)} de {len(candidate_addresses)} endereços ===\n")
            
            # Filtra apenas os endereços validados
            validated_addresses = []
            for idx in valid_indices:
                if 1 <= idx <= len(candidate_addresses):
                    validated_addresses.append(candidate_addresses[idx - 1])
            
            return validated_addresses
            
        except Exception as e:
            print(f"Aviso: Erro ao validar com DeepSeek: {str(e)}")
            print("Retornando todos os endereços candidatos sem validação IA.")
            # Em caso de erro, retorna todos os candidatos
            return candidate_addresses
    
    def extract_addresses(self, text, use_ai_validation=True, progress_callback=None):
        """
        Extrai todos os endereços do texto.
        
        Args:
            text: Texto extraído do PDF
            use_ai_validation: Se True, usa DeepSeek para validar endereços
            progress_callback: Função callback para atualizar progresso
        
        Returns:
            list: Lista de dicionários com informações de endereços
        """
        addresses = []
        lines = text.split('\n')
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            # Verifica se a linha contém um endereço completo (com cidade)
            line_upper = line.upper()
            has_city = 'FORTALEZA' in line_upper
            
            # Se contém padrão de endereço e tem cidade na mesma linha, processa como linha única
            if self._contains_street_pattern(line) and has_city:
                address = self._parse_address_line(line)
                if address and address.get('logradouro'):
                    addresses.append(address)
                i += 1
            # Senão, se tem padrão de rua, processa como multi-linha
            elif self._is_street_line(line) or self._looks_like_street_name_with_number(line):
                address = self._parse_multiline_address(lines, i)
                if address and address.get('logradouro'):
                    addresses.append(address)
                    i += address.get('lines_consumed', 1)
                else:
                    i += 1
            else:
                i += 1
        
        # Remove RUA QUITERIO GIRAO 570 completamente (endereço inicial fixo)
        filtered_addresses = []
        for addr in addresses:
            logradouro = addr.get('logradouro', '').upper()
            if not ('QUITERIO GIRAO' in logradouro or 'QUITERIO' in logradouro):
                filtered_addresses.append(addr)
        
        addresses = filtered_addresses
        
        # # Valida endereços com DeepSeek AI se solicitado
        # if use_ai_validation and addresses:
        #     addresses = self._validate_addresses_with_deepseek(addresses, progress_callback)
        
        return addresses
    
    def _looks_like_street_name_with_number(self, line):
        """
        Verifica se a linha parece ser um nome de rua seguido de número,
        mesmo sem prefixo de tipo de logradouro.
        """
        line_upper = line.upper()
        
        # Rejeita linhas que são claramente não-endereços
        reject_patterns = [
            r'CNPJ',
            r'CPF',
            r'TARA:',
            r'PESO:',
            r'TRANSPORTES',
            r'IMPRESSO',
            r'POR\.:',
            r'\d{2}\.\d{3}\.\d{3}',  # CNPJ
            r'^CE\s+\d{5}',  # Apenas CEP sozinho
            r'^[A-Z]{2}\s+\d{5}',  # Estado + CEP sozinho
            r'CT-SPO',  # Código CT
            r'FTZ-\d+',  # Código FTZ
            r'^\d{9,}',  # Linha começa com número longo (código de pedido)
            r'^\d+\s+CT-',  # Número seguido de CT-
            r'DOCA$',  # Linha termina com DOCA
            r'\d+,\d+\s+\d+,\d+',  # Números decimais (valores monetários)
            r'ZONA RURAL',  # Zona rural sem logradouro
            r'DISTRITO INDUST',  # Distrito industrial sem logradouro
            r'POLO INDUSTRIAL',  # Polo industrial sem logradouro
        ]
        
        for pattern in reject_patterns:
            if re.search(pattern, line_upper):
                return False
        
        # Rejeita se a linha tem muitos números (típico de dados tabulares)
        if len(re.findall(r'\d+', line)) > 3:
            return False
        
        # Deve ter pelo menos 2 palavras e terminar com um número de 3-5 dígitos ou S/N (sem número)
        parts = line.strip().split()
        if len(parts) >= 2:
            # Verifica se tem um número que parece ser número de endereço ou S/N
            if re.search(r'\b\d{3,5}\b', line) or 'S/N' in line_upper:
                # Não deve ter caracteres especiais que indiquem que não é endereço
                if not re.search(r'[|()]', line):
                    return True
        return False
    
    def _parse_multiline_address(self, lines, start_idx):
        """
        Extrai endereço que está distribuído em múltiplas linhas.
        
        Args:
            lines: Lista de linhas
            start_idx: Índice da linha inicial
        
        Returns:
            dict: Endereço extraído
        """
        if start_idx >= len(lines):
            return None
        
        first_line = lines[start_idx].strip()
        
        # Rejeita se a linha inicial é claramente não-endereço
        first_upper = first_line.upper()
        reject_patterns = [
            r'CNPJ', r'CPF', r'TARA:', r'PESO:', r'TRANSPORTES', r'IMPRESSO', r'POR\.:',
            r'CT-SPO', r'FTZ-\d+', r'^\d{9,}', r'DOCA$',
            r'\d+,\d+\s+\d+,\d+',  # Valores monetários
        ]
        
        for pattern in reject_patterns:
            if re.search(pattern, first_upper):
                return None
        
        # Rejeita se tem muitos números (dados tabulares)
        if len(re.findall(r'\d+', first_line)) > 3:
            return None
        
        address = {
            'logradouro': first_line,
            'bairro': '',
            'cidade': '',
            'estado': '',
            'cep': '',
            'lines_consumed': 1
        }
        
        # Próximas linhas podem conter bairro, cidade, estado, CEP
        found_city = False
        for offset in range(1, min(6, len(lines) - start_idx)):
            next_line = lines[start_idx + offset].strip()
            if not next_line:
                continue
            
            next_upper = next_line.upper()
            
            # Se encontrou estado (indicador de linha com cidade)
            estado_pattern = r'\b(' + '|'.join(self.estados) + r')\b'
            estado_match = re.search(estado_pattern, next_upper)
            
            if estado_match:
                # Extrai o estado
                address['estado'] = estado_match.group(1)
                
                # Extrai bairro (procura primeiro por bairros conhecidos)
                bairros = ['ALDEOTA', 'PICI', 'CENTRO', 'MESSEJANA', 'MONTE CASTELO', 'VILA ELLERY', 'VILA UNIAO', 'MONGUBA']
                for bairro in bairros:
                    if bairro in next_upper:
                        address['bairro'] = bairro
                        break
                
                # Extrai a cidade: tudo antes do estado, mas depois do bairro (se houver)
                parts_before_estado = next_line[:estado_match.start()].strip().split()
                
                # Remove palavras do bairro se já identificamos um
                if address.get('bairro'):
                    bairro_words = address['bairro'].split()
                    # Filtra palavras do bairro
                    cidade_parts = []
                    skip_next = 0
                    for i, part in enumerate(parts_before_estado):
                        if skip_next > 0:
                            skip_next -= 1
                            continue
                        if part.upper() not in bairro_words:
                            cidade_parts.append(part)
                        else:
                            # Pula todas as palavras do bairro
                            skip_next = len(bairro_words) - 1
                else:
                    # Sem bairro, a cidade é tudo antes do estado
                    cidade_parts = parts_before_estado
                
                if cidade_parts:
                    address['cidade'] = ' '.join(cidade_parts).upper()
                    found_city = True
                    address['lines_consumed'] = offset + 1
                
                # Extrai CEP desta linha
                cep = self._extract_cep(next_line)
                if cep:
                    address['cep'] = cep
                
                # Continue procurando CEP nas próximas linhas se não encontrou
                if not cep:
                    for cep_offset in range(offset + 1, min(offset + 4, len(lines) - start_idx)):
                        cep_line = lines[start_idx + cep_offset].strip()
                        cep = self._extract_cep(cep_line)
                        if cep:
                            address['cep'] = cep
                            address['lines_consumed'] = cep_offset + 1
                            break
                
                break
            # Se encontrou só bairro
            elif any(b in next_upper for b in ['ALDEOTA', 'PICI', 'CENTRO', 'MESSEJANA', 'MONTE CASTELO', 'VILA ELLERY', 'VILA UNIAO', 'MONGUBA']):
                bairros = ['ALDEOTA', 'PICI', 'CENTRO', 'MESSEJANA', 'MONTE CASTELO', 'VILA ELLERY', 'VILA UNIAO', 'MONGUBA']
                for bairro in bairros:
                    if bairro in next_upper:
                        address['bairro'] = bairro
                        address['lines_consumed'] = offset + 1
                        break
        
        # Valida que o endereço tem cidade (caso contrário não é endereço válido)
        if not address.get('cidade'):
            return None
        
        return address
    
    def _is_street_line(self, line):
        """Verifica se a linha parece ser o início de um endereço."""
        line_upper = line.upper()
        
        # Rejeita linhas que não são endereços
        if re.search(r'(CNPJ|CPF|TARA:|PESO:|TRANSPORTES|IMPRESSO|POR\.:)', line_upper):
            return False
        
        # Rejeita linha que é só estado + CEP (ex: "CE 60440-593")
        if re.match(r'^[A-Z]{2}\s+\d{5}', line_upper):
            return False
        
        street_types = ['RODOVIA', 'ROD ', 'RUA', 'AVENIDA', 'AV ', 'TRAVESSA', 'ESTRADA', 'EST ', 
                       'ALAMEDA', 'PRAÇA', 'R ', 'TRAV', 'PÇA', 'VIA ', 'PV ']
        return any(line_upper.startswith(st) for st in street_types)
    
    def _contains_street_pattern(self, line):
        """Verifica se a linha contém um padrão de endereço."""
        street_types = ['RODOVIA', 'ROD ', 'RUA', 'AVENIDA', 'AV ', 'TRAVESSA', 'ESTRADA', 'EST ', 
                       'ALAMEDA', 'PRAÇA', 'R ', 'TRAV', 'PÇA', 'VIA ', 'PV ']
        line_upper = line.upper()
        
        # Verifica se contém algum tipo de logradouro seguido por nome e número
        for street_type in street_types:
            if street_type in line_upper:
                # Verifica se há pelo menos um número no resto da linha
                idx = line_upper.index(street_type)
                rest = line[idx:]
                if re.search(r'\d+', rest):
                    return True
        
        # Verifica padrão alternativo: nome de rua + número + bairro + cidade + estado
        # Exemplo: "LINEU JUCA 00421 VILA UNIAO FORTALEZA CE"
        if any(estado in line_upper for estado in self.estados):
            # Verifica se tem um número de 3-5 dígitos (número da rua)
            if re.search(r'\b\d{3,5}\b', line):
                return True
        
        return False
    
    def _parse_address_line(self, line):
        """
        Extrai informações de endereço de uma única linha.
        
        Args:
            line: Linha contendo o endereço
        
        Returns:
            dict: Endereço extraído
        """
        address = {
            'logradouro': '',
            'bairro': '',
            'cidade': '',
            'estado': '',
            'cep': '',
            'lines_consumed': 1
        }
        
        line_upper = line.upper()
        
        # Encontra o tipo de logradouro
        street_types = ['RODOVIA', 'AVENIDA', 'TRAVESSA', 'ESTRADA', 'ALAMEDA', 'PRAÇA', 'RUA', 'PV']
        street_start = -1
        found_street_type = None
        
        for street_type in street_types:
            idx = line_upper.find(street_type)
            if idx != -1:
                street_start = idx
                found_street_type = street_type
                break
        
        # Se não encontrou tipo de logradouro, tenta extrair endereço sem prefixo
        if street_start == -1:
            # Procura padrão: NOME + NUMERO + BAIRRO + CIDADE + ESTADO
            # Exemplo: "LINEU JUCA 00421 VILA UNIAO FORTALEZA CE"
            return self._parse_address_without_street_type(line)
        
        # Extrai a parte do endereço completo (do tipo de logradouro até o final da linha)
        address_part = line[street_start:].strip()
        
        # Extrai o logradouro completo (incluindo número)
        # O logradouro termina antes do bairro/cidade
        parts = address_part.split()
        logradouro_parts = []
        
        i = 0
        while i < len(parts):
            part_upper = parts[i].upper()
            
            # Para se encontrar bairro composto
            if i + 1 < len(parts):
                next_part = parts[i + 1].upper()
                # Verifica se é bairro composto conhecido
                if (part_upper == 'MONTE' and next_part == 'CASTELO') or \
                   (part_upper == 'VILA' and next_part in ['ELLERY', 'UNIAO']):
                    break
            
            # Para se encontrar bairro simples (mas não antes de verificar se faz parte do logradouro)
            if part_upper in ['ALDEOTA', 'PICI', 'CENTRO', 'MESSEJANA', 'MONGUBA']:
                break
            
            # Para se encontrar CEP
            if re.match(r'\d{5}-?\d{3}', part_upper):
                break
            
            # Para se encontrar estado (indica início da parte cidade/estado)
            if part_upper in self.estados:
                break
            
            logradouro_parts.append(parts[i])
            i += 1
        
        if logradouro_parts:
            address['logradouro'] = ' '.join(logradouro_parts)
        
        # Extrai CEP
        cep = self._extract_cep(line)
        if cep:
            address['cep'] = cep
        
        # Extrai estado e cidade dinamicamente
        estado_pattern = r'\b(' + '|'.join(self.estados) + r')\b'
        estado_match = re.search(estado_pattern, line_upper)
        
        if estado_match:
            address['estado'] = estado_match.group(1)
            
            # Extrai cidade: palavras antes do estado mas depois do logradouro
            # Encontra posição do estado na linha
            estado_pos = estado_match.start()
            
            # Pega tudo antes do estado
            before_estado = line[:estado_pos].strip()
            
            # A cidade são as últimas palavras antes do estado (geralmente 1-3 palavras)
            # mas depois do logradouro
            parts = before_estado.split()
            
            # Se temos logradouro, a cidade vem depois dele
            if address.get('logradouro'):
                # Remove palavras do logradouro
                logradouro_words = address['logradouro'].split()
                remaining_parts = parts[len(logradouro_words):]
                
                # Remove bairro se presente
                cidade_parts = []
                for part in remaining_parts:
                    if part.upper() not in ['ALDEOTA', 'PICI', 'CENTRO', 'MESSEJANA', 'MONTE', 'CASTELO', 'VILA', 'ELLERY', 'UNIAO', 'MONGUBA']:
                        cidade_parts.append(part)
                
                if cidade_parts:
                    address['cidade'] = ' '.join(cidade_parts).upper()
        
        # Procura por bairro
        bairros = ['ALDEOTA', 'PICI', 'CENTRO', 'MESSEJANA', 'MONTE CASTELO', 'VILA ELLERY', 'VILA UNIAO', 'MONGUBA']
        for bairro in bairros:
            if bairro in line_upper:
                address['bairro'] = bairro
                break
        
        return address
    
    def _parse_address_without_street_type(self, line):
        """
        Extrai endereço que não tem prefixo de tipo de logradouro.
        
        Args:
            line: Linha contendo o endereço
        
        Returns:
            dict: Endereço extraído ou None
        """
        line_upper = line.upper()
        
        # Verifica se tem estado (indicador de endereço)
        estado_pattern = r'\b(' + '|'.join(self.estados) + r')\b'
        estado_match = re.search(estado_pattern, line_upper)
        
        if not estado_match:
            return None
        
        # Extrai a cidade: palavras antes do estado
        estado_pos = estado_match.start()
        before_estado = line[:estado_pos].strip()
        parts = before_estado.split()
        
        # A cidade são as últimas 1-3 palavras antes do estado
        # mas depois do bairro (se houver)
        bairros = ['ALDEOTA', 'PICI', 'CENTRO', 'MESSEJANA', 'MONTE CASTELO', 'VILA ELLERY', 'VILA UNIAO', 'MONGUBA']
        
        # Encontra onde termina o bairro (se houver)
        bairro_end_idx = -1
        for i, part in enumerate(parts):
            for bairro in bairros:
                if bairro in ' '.join(parts[max(0,i-1):i+2]).upper():
                    bairro_end_idx = i + len(bairro.split())
                    break
        
        # Cidade: últimas palavras antes do estado, depois do bairro
        if bairro_end_idx >= 0:
            cidade_parts = parts[bairro_end_idx:]
        else:
            # Pega últimas 1-3 palavras como cidade
            cidade_parts = parts[-min(3, len(parts)):]
        
        cidade_completa = ' '.join(cidade_parts).upper() if cidade_parts else ''
        
        address = {
            'logradouro': '',
            'bairro': '',
            'cidade': cidade_completa,
            'estado': estado_match.group(1) if estado_match else '',
            'cep': '',
            'lines_consumed': 1
        }
        
        # Extrai CEP
        cep = self._extract_cep(line)
        if cep:
            address['cep'] = cep
        
        # Procura por bairro
        bairros = ['ALDEOTA', 'PICI', 'CENTRO', 'MESSEJANA', 'MONTE CASTELO', 'VILA ELLERY', 'VILA UNIAO', 'MONGUBA']
        bairro_found = None
        bairro_idx = -1
        
        for bairro in bairros:
            idx = line_upper.find(bairro)
            if idx != -1:
                bairro_found = bairro
                bairro_idx = idx
                address['bairro'] = bairro
                break
        
        # Extrai logradouro: tudo antes do bairro (ou antes da cidade se não tiver bairro)
        if bairro_idx != -1:
            logradouro = line[:bairro_idx].strip()
        else:
            # Logradouro é tudo antes da cidade
            # Encontra onde começa a cidade na linha original
            if cidade_parts:
                cidade_str = ' '.join(cidade_parts)
                city_idx = line.upper().find(cidade_str)
                if city_idx != -1:
                    logradouro = line[:city_idx].strip()
                else:
                    return None
            else:
                return None
        
        address['logradouro'] = logradouro
        
        return address

    
    def _extract_cep(self, line):
        """Extrai CEP de uma linha."""
        # Padrão: 12345-678 ou 12345678
        cep_match = re.search(r'\d{5}-?\d{3}', line)
        if cep_match:
            return cep_match.group(0)
        return ''
    
    def format_address(self, address):
        """
        Formata um endereço para exibição.
        
        Args:
            address: Dicionário com dados do endereço
        
        Returns:
            str: Endereço formatado
        """
        parts = []
        
        if address.get('logradouro'):
            parts.append(address['logradouro'])
        
        if address.get('bairro'):
            parts.append(address['bairro'])
        
        city_state = []
        if address.get('cidade'):
            city_state.append(address['cidade'])
        if address.get('estado'):
            city_state.append(address['estado'])
        if city_state:
            parts.append(' - '.join(city_state))
        
        if address.get('cep'):
            parts.append(f"CEP: {address['cep']}")
        
        return '\n'.join(parts)
