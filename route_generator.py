"""
Módulo para gerar rotas otimizadas usando Google Distance Matrix API.
Implementa algoritmos nearest-neighbor e 2-opt para otimização de rotas.
"""

import googlemaps
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # python-dotenv not installed; env vars must be set manually
    pass
from datetime import datetime
import time
import webbrowser
import urllib.parse
from datetime import datetime as dt


# =============================================================================
# DISTANCE MATRIX HELPER CLASS
# =============================================================================

class DistanceMatrix:
    """
    Encapsula a matriz de distâncias para acesso fácil e seguro.
    
    Esta classe converte a resposta da API do Google em uma matriz simples
    de distâncias (em metros) que pode ser indexada por [i][j].
    """
    
    def __init__(self, google_matrix_response):
        """
        Inicializa a matriz de distâncias.
        
        Args:
            google_matrix_response: Resposta da API do Google Distance Matrix
        """
        self.raw_response = google_matrix_response
        self.n = len(google_matrix_response['rows'])
        self._distance_matrix = self._build_distance_matrix()
        self._duration_matrix = self._build_duration_matrix()
    
    def _build_distance_matrix(self):
        """Constrói matriz de distâncias em metros."""
        matrix = []
        for row in self.raw_response['rows']:
            row_distances = []
            for element in row['elements']:
                if element['status'] == 'OK':
                    row_distances.append(element['distance']['value'])
                else:
                    # Usa infinito para rotas impossíveis
                    row_distances.append(float('inf'))
            matrix.append(row_distances)
        return matrix
    
    def _build_duration_matrix(self):
        """Constrói matriz de durações em segundos."""
        matrix = []
        for row in self.raw_response['rows']:
            row_durations = []
            for element in row['elements']:
                if element['status'] == 'OK':
                    row_durations.append(element['duration']['value'])
                else:
                    row_durations.append(float('inf'))
            matrix.append(row_durations)
        return matrix
    
    def distance(self, i, j):
        """Retorna distância de i para j em metros."""
        return self._distance_matrix[i][j]
    
    def duration(self, i, j):
        """Retorna duração de i para j em segundos."""
        return self._duration_matrix[i][j]
    
    def size(self):
        """Retorna número de locais na matriz."""
        return self.n


# =============================================================================
# ROUTE OPTIMIZATION ALGORITHMS
# =============================================================================

class RouteOptimizer:
    """
    Classe dedicada a algoritmos de otimização de rotas.
    
    Separa a lógica de otimização da classe principal para maior clareza.
    """
    
    def __init__(self, distance_matrix):
        """
        Inicializa o otimizador.
        
        Args:
            distance_matrix: Instância de DistanceMatrix
        """
        self.dm = distance_matrix
    
    # -------------------------------------------------------------------------
    # NEAREST NEIGHBOR ALGORITHM
    # -------------------------------------------------------------------------
    
    def nearest_neighbor(self, start_idx=0):
        """
        Gera rota inicial usando algoritmo nearest-neighbor (vizinho mais próximo).
        
        Algoritmo guloso que sempre escolhe o próximo ponto não visitado mais próximo.
        Complexidade: O(n²)
        
        Args:
            start_idx: Índice do ponto de partida (default: 0)
        
        Returns:
            list: Lista de índices representando a rota (inclui retorno ao início)
        """
        n = self.dm.size()
        visited = [False] * n
        route = [start_idx]
        visited[start_idx] = True
        current = start_idx
        
        # Visita todos os pontos
        for _ in range(n - 1):
            nearest = -1
            nearest_dist = float('inf')
            
            for j in range(n):
                if not visited[j]:
                    dist = self.dm.distance(current, j)
                    if dist < nearest_dist:
                        nearest_dist = dist
                        nearest = j
            
            if nearest != -1:
                route.append(nearest)
                visited[nearest] = True
                current = nearest
        
        # Retorna ao ponto inicial
        route.append(start_idx)
        
        return route
    
    # -------------------------------------------------------------------------
    # 2-OPT ALGORITHM
    # -------------------------------------------------------------------------
    
    def two_opt(self, initial_route, max_iterations=1000):
        """
        Melhora a rota usando o algoritmo 2-opt.
        
        O 2-opt funciona assim:
        1. Pega uma rota inicial
        2. Remove duas arestas não adjacentes
        3. Reconecta os segmentos de forma diferente
        4. Se a nova rota for melhor, mantém
        5. Repete até não haver mais melhorias
        
        Exemplo visual:
        
        Antes:  A -> B -> C -> D -> E -> A
                         ↓
        Remove arestas (B,C) e (D,E):
                A -> B    C -> D    E -> A
                         ↓
        Reconecta invertendo C-D:
                A -> B -> D -> C -> E -> A
        
        Complexidade: O(n² * iterações)
        
        Args:
            initial_route: Rota inicial (lista de índices, com retorno ao início)
            max_iterations: Número máximo de iterações sem melhoria
        
        Returns:
            list: Rota otimizada (lista de índices)
        """
        # Copia a rota para não modificar a original
        route = initial_route.copy()
        n = len(route)
        
        # Não faz sentido otimizar rotas muito pequenas
        # Precisa de pelo menos 4 pontos: início, 2 waypoints, retorno
        if n < 4:
            return route
        
        improved = True
        iterations = 0
        
        while improved and iterations < max_iterations:
            improved = False
            iterations += 1
            
            # Tenta todas as combinações de trocas 2-opt
            # i e j são as posições na rota (não os índices dos locais)
            # i vai de 1 até n-3 (não mexe no ponto inicial)
            # j vai de i+1 até n-2 (não mexe no retorno final)
            for i in range(1, n - 2):
                for j in range(i + 1, n - 1):
                    
                    # Calcula o ganho da troca
                    gain = self._calculate_two_opt_gain(route, i, j)
                    
                    if gain > 0:
                        # Realiza a troca: inverte o segmento entre i e j
                        route = self._apply_two_opt_swap(route, i, j)
                        improved = True
                        break  # Reinicia a busca
                
                if improved:
                    break
        
        return route
    
    def _calculate_two_opt_gain(self, route, i, j):
        """
        Calcula o ganho de distância ao fazer uma troca 2-opt.
        
        Remove as arestas:
          - route[i-1] -> route[i]
          - route[j]   -> route[j+1]
        
        Adiciona as arestas:
          - route[i-1] -> route[j]
          - route[i]   -> route[j+1]
        
        Args:
            route: Rota atual
            i: Posição inicial do segmento a inverter
            j: Posição final do segmento a inverter
        
        Returns:
            float: Ganho de distância (positivo = melhoria)
        """
        # Índices dos locais nas posições da rota
        a = route[i - 1]  # Ponto antes do segmento
        b = route[i]      # Início do segmento
        c = route[j]      # Fim do segmento
        d = route[j + 1]  # Ponto depois do segmento
        
        # Distância atual das arestas que serão removidas
        current_distance = self.dm.distance(a, b) + self.dm.distance(c, d)
        
        # Distância das novas arestas após a troca
        new_distance = self.dm.distance(a, c) + self.dm.distance(b, d)
        
        # Ganho = distância antiga - distância nova
        return current_distance - new_distance
    
    def _apply_two_opt_swap(self, route, i, j):
        """
        Aplica a troca 2-opt invertendo o segmento entre i e j.
        
        Args:
            route: Rota atual
            i: Posição inicial do segmento
            j: Posição final do segmento
        
        Returns:
            list: Nova rota com o segmento invertido
        """
        # Cria nova rota:
        # 1. Mantém elementos antes de i
        # 2. Inverte elementos de i até j (inclusive)
        # 3. Mantém elementos depois de j
        new_route = route[:i] + route[i:j+1][::-1] + route[j+1:]
        return new_route
    
    # -------------------------------------------------------------------------
    # COMBINED OPTIMIZATION
    # -------------------------------------------------------------------------
    
    def optimize(self, start_idx=0, use_two_opt=True):
        """
        Executa otimização completa: nearest-neighbor + 2-opt.
        
        Args:
            start_idx: Índice do ponto de partida
            use_two_opt: Se True, aplica 2-opt após nearest-neighbor
        
        Returns:
            list: Rota otimizada
        """
        # Passo 1: Gera rota inicial com nearest-neighbor
        route = self.nearest_neighbor(start_idx)
        
        # Passo 2: Melhora com 2-opt (se habilitado)
        if use_two_opt and self.dm.size() >= 4:
            route = self.two_opt(route)
        
        return route
    
    def calculate_route_distance(self, route):
        """
        Calcula a distância total de uma rota.
        
        Args:
            route: Lista de índices representando a rota
        
        Returns:
            int: Distância total em metros
        """
        total = 0
        for i in range(len(route) - 1):
            total += self.dm.distance(route[i], route[i + 1])
        return total
    
    def calculate_route_duration(self, route):
        """
        Calcula a duração total de uma rota.
        
        Args:
            route: Lista de índices representando a rota
        
        Returns:
            int: Duração total em segundos
        """
        total = 0
        for i in range(len(route) - 1):
            total += self.dm.duration(route[i], route[i + 1])
        return total


# =============================================================================
# MAIN ROUTE GENERATOR CLASS
# =============================================================================

class RouteGenerator:
    """Gera rotas otimizadas a partir de uma lista de endereços."""
    
    def __init__(self, google_api_key=None):
        """
        Inicializa o gerador de rotas.
        
        Args:
            google_api_key: Chave da API do Google Maps
        """
        # Prefer environment variable if set
        api_key = os.getenv('GOOGLE_MAPS_API_KEY', google_api_key)
        self.google_api_key = api_key
        self.gmaps = googlemaps.Client(key=api_key)
        self.fixed_start = "STC Transportes, Fortaleza, CE"
    
    def format_address_for_api(self, address_dict):
        """
        Formata um dicionário de endereço para string compatível com Google API.
        
        Args:
            address_dict: Dicionário com dados do endereço
        
        Returns:
            str: Endereço formatado
        """
        parts = []
        
        if address_dict.get('logradouro'):
            parts.append(address_dict['logradouro'])
        
        if address_dict.get('bairro'):
            parts.append(address_dict['bairro'])
        
        if address_dict.get('cidade'):
            parts.append(address_dict['cidade'])
        
        if address_dict.get('estado'):
            parts.append(address_dict['estado'])
        
        if address_dict.get('cep'):
            parts.append(address_dict['cep'])
        
        return ', '.join(parts)
    
    def get_distance_matrix(self, origins, destinations, progress_callback=None):
        """
        Obtém matriz de distâncias entre origens e destinos.
        Divide automaticamente em batches se exceder limite da API (100 elementos).
        
        Args:
            origins: Lista de endereços de origem
            destinations: Lista de endereços de destino
            progress_callback: Função callback para atualizar progresso
        
        Returns:
            dict: Matriz de distâncias do Google Maps API
        """
        if progress_callback:
            progress_callback("Calculando distâncias...", 30)
        
        try:
            # Google Maps API aceita até 100 elementos por request
            # onde elementos = origins × destinations
            # Usando 10x10 = 100 elementos (seguro)
            MAX_BATCH_SIZE = 10
            
            # Se couber em uma requisição, faz diretamente
            if len(origins) * len(destinations) <= 100:
                matrix = self.gmaps.distance_matrix(
                    origins=origins,
                    destinations=destinations,
                    mode="driving",
                    language="pt-BR",
                    units="metric",
                    departure_time=datetime.now()
                )
                return matrix
            
            # Caso contrário, divide em batches
            all_rows = []
            total_batches = ((len(origins) - 1) // MAX_BATCH_SIZE + 1) * ((len(destinations) - 1) // MAX_BATCH_SIZE + 1)
            batch_num = 0
            
            for i in range(0, len(origins), MAX_BATCH_SIZE):
                origin_batch = origins[i:i + MAX_BATCH_SIZE]
                row_data = []
                
                for j in range(0, len(destinations), MAX_BATCH_SIZE):
                    dest_batch = destinations[j:j + MAX_BATCH_SIZE]
                    batch_num += 1
                    
                    if progress_callback:
                        progress_msg = f"Calculando distâncias (batch {batch_num}/{total_batches})..."
                        progress_pct = 30 + int((batch_num / total_batches) * 30)  # 30-60%
                        progress_callback(progress_msg, progress_pct)
                    
                    # Faz requisição do batch
                    batch_matrix = self.gmaps.distance_matrix(
                        origins=origin_batch,
                        destinations=dest_batch,
                        mode="driving",
                        language="pt-BR",
                        units="metric",
                        departure_time=datetime.now()
                    )
                    
                    # Adiciona atraso pequeno para evitar rate limiting
                    if batch_num < total_batches:
                        time.sleep(0.2)
                    
                    # Armazena os elementos desta parte
                    if j == 0:
                        # Primeira coluna de destinos - inicializa as rows
                        for row_idx, row in enumerate(batch_matrix['rows']):
                            row_data.append({'elements': row['elements'].copy()})
                    else:
                        # Adiciona elementos às rows existentes
                        for row_idx, row in enumerate(batch_matrix['rows']):
                            row_data[row_idx]['elements'].extend(row['elements'])
                
                all_rows.extend(row_data)
            
            # Reconstrói a resposta completa no formato esperado
            complete_matrix = {
                'status': 'OK',
                'origin_addresses': origins,
                'destination_addresses': destinations,
                'rows': all_rows
            }
            
            return complete_matrix
        
        except Exception as e:
            raise Exception(f"Erro ao obter matriz de distâncias: {str(e)}")
    
    def optimize_route(self, addresses, use_two_opt=True, progress_callback=None):
        """
        Gera rota otimizada usando nearest-neighbor + 2-opt.
        
        O algoritmo funciona assim:
        1. Começa no ponto fixo (Rua Quitério Girão 570)
        2. Gera rota inicial com nearest-neighbor
        3. Melhora a rota com 2-opt (se habilitado)
        4. Retorna ao ponto inicial no final
        
        Args:
            addresses: Lista de dicionários de endereços
            use_two_opt: Se True, aplica otimização 2-opt (default: True)
            progress_callback: Função callback para atualizar progresso
        
        Returns:
            dict: Dicionário com rota otimizada e informações
        """
        if not addresses:
            return {
                'route': [],
                'total_distance': 0,
                'total_duration': 0,
                'error': 'Nenhum endereço fornecido'
            }
        
        if progress_callback:
            progress_callback("Formatando endereços...", 10)
        
        # Formata endereços para API
        formatted_addresses = [self.format_address_for_api(addr) for addr in addresses]
        
        # Adiciona ponto de partida (índice 0)
        all_locations = [self.fixed_start] + formatted_addresses
        
        if progress_callback:
            progress_callback("Obtendo matriz de distâncias...", 20)
        
        # Obtém matriz de distâncias completa
        try:
            google_matrix = self.get_distance_matrix(all_locations, all_locations, progress_callback)
        except Exception as e:
            return {
                'route': [],
                'total_distance': 0,
                'total_duration': 0,
                'error': str(e)
            }
        
        # Verifica se a matriz é válida
        if google_matrix['status'] != 'OK':
            return {
                'route': [],
                'total_distance': 0,
                'total_duration': 0,
                'error': f"Erro na API do Google: {google_matrix['status']}"
            }
        
        if progress_callback:
            progress_callback("Otimizando rota (nearest-neighbor)...", 40)
        
        # Cria matriz de distâncias encapsulada
        dm = DistanceMatrix(google_matrix)
        
        # Cria otimizador
        optimizer = RouteOptimizer(dm)
        
        # Gera rota inicial com nearest-neighbor
        route_indices = optimizer.nearest_neighbor(start_idx=0)
        
        # Aplica 2-opt se habilitado
        if use_two_opt:
            if progress_callback:
                progress_callback("Otimizando rota (2-opt)...", 60)
            route_indices = optimizer.two_opt(route_indices)
        
        if progress_callback:
            progress_callback("Calculando distâncias...", 80)
        
        # Calcula totais
        total_distance = optimizer.calculate_route_distance(route_indices)
        total_duration = optimizer.calculate_route_duration(route_indices)
        
        if progress_callback:
            progress_callback("Rota otimizada!", 100)
        
        # Monta rota final com informações detalhadas
        route = []
        for idx in route_indices:
            if idx == 0:
                route.append({
                    'address': self.fixed_start,
                    'is_start': True,
                    'original_data': None
                })
            else:
                route.append({
                    'address': formatted_addresses[idx - 1],
                    'is_start': False,
                    'original_data': addresses[idx - 1]
                })
        
        return {
            'route': route,
            'route_indices': route_indices,
            'total_distance': total_distance,  # em metros
            'total_duration': total_duration,  # em segundos
            'total_distance_km': round(total_distance / 1000, 2),
            'total_duration_min': round(total_duration / 60, 2),
            'num_stops': len(addresses),
            'error': None
        }
    
    def nearest_neighbor_route(self, addresses, progress_callback=None):
        """
        Alias para optimize_route com 2-opt habilitado.
        Mantido para compatibilidade com código existente.
        
        Args:
            addresses: Lista de dicionários de endereços
            progress_callback: Função callback para atualizar progresso
        
        Returns:
            dict: Dicionário com rota otimizada e informações
        """
        return self.optimize_route(addresses, use_two_opt=True, progress_callback=progress_callback)
    
    def get_route_details(self, route_result):
        """
        Retorna detalhes legíveis da rota.
        
        Args:
            route_result: Resultado do método nearest_neighbor_route
        
        Returns:
            str: Texto formatado com detalhes da rota
        """
        if route_result.get('error'):
            return f"Erro: {route_result['error']}"
        
        lines = []
        lines.append("=" * 60)
        lines.append("ROTA OTIMIZADA")
        lines.append("=" * 60)
        lines.append(f"Total de paradas: {route_result['num_stops']}")
        lines.append(f"Distância total: {route_result['total_distance_km']} km")
        lines.append(f"Tempo estimado: {route_result['total_duration_min']} minutos")
        lines.append("=" * 60)
        lines.append("\nSequência de paradas:")
        lines.append("-" * 60)
        
        for i, stop in enumerate(route_result['route'], 1):
            if stop['is_start']:
                lines.append(f"\n{i}. [PONTO DE PARTIDA/RETORNO]")
            else:
                lines.append(f"\n{i}.")
            lines.append(f"   {stop['address']}")
        
        lines.append("\n" + "=" * 60)
        
        return '\n'.join(lines)
    
    def generate_route_from_extractor(self, address_extractor_result, progress_callback=None):
        """
        Gera rota a partir do resultado do AddressExtractor.
        
        Args:
            address_extractor_result: Lista de endereços do AddressExtractor
            progress_callback: Função callback para atualizar progresso
        
        Returns:
            dict: Resultado da rota otimizada
        """
        return self.nearest_neighbor_route(address_extractor_result, progress_callback)
    
    def open_route_in_browser(self, addresses, optimize=False):
        """
        Abre a rota no Google Maps no navegador.
        
        Args:
            addresses: Lista de dicionários de endereços
            optimize: Se True, usa rota otimizada; se False, usa ordem original
        
        Returns:
            str or list: URL(s) da rota aberta
        """
        if not addresses:
            raise ValueError("Nenhum endereço fornecido")
        
        # Google Maps suporta até 9 waypoints por URL (start + 9 waypoints + end = 11 total)
        MAX_WAYPOINTS = 9
        
        if optimize:
            # Gera rota otimizada COMPLETA primeiro
            route_result = self.nearest_neighbor_route(addresses)
            
            if route_result.get('error'):
                raise Exception(route_result['error'])
            
            # Usa a ordem otimizada (remove pontos de início/retorno)
            ordered_addresses = [
                stop['original_data'] 
                for stop in route_result['route'] 
                if not stop['is_start'] and stop['original_data']
            ]
        else:
            # Usa ordem original
            ordered_addresses = addresses
        
        # Formata endereços
        formatted_addresses = [self.format_address_for_api(addr) for addr in ordered_addresses]
        
        # Divide em múltiplas rotas se necessário
        if len(formatted_addresses) > MAX_WAYPOINTS:
            urls = []
            chunks = []
            
            # Divide a rota otimizada em chunks
            for i in range(0, len(formatted_addresses), MAX_WAYPOINTS):
                chunk = formatted_addresses[i:i + MAX_WAYPOINTS]
                chunks.append(chunk)
            
            # Cria URLs para cada chunk
            for idx, chunk in enumerate(chunks):
                is_first = (idx == 0)
                is_last = (idx == len(chunks) - 1)
                
                url = self._create_google_maps_url(
                    chunk, 
                    is_first=is_first,
                    is_last=is_last,
                    prev_chunk_last=chunks[idx-1][-1] if idx > 0 else None
                )
                webbrowser.open(url)
                urls.append(url)
            
            return urls
        else:
            url = self._create_google_maps_url(formatted_addresses, is_first=True, is_last=True)
            webbrowser.open(url)
            return url
    
    def _create_google_maps_url(self, addresses, is_first=True, is_last=True, prev_chunk_last=None):
        """
        Cria URL do Google Maps com waypoints.
        
        Args:
            addresses: Lista de endereços formatados
            is_first: Se é o primeiro chunk (inicia do ponto fixo)
            is_last: Se é o último chunk (termina no ponto fixo)
            prev_chunk_last: Último endereço do chunk anterior (para continuidade)
        
        Returns:
            str: URL do Google Maps
        """
        # Define origem
        if is_first:
            # Primeiro chunk: começa do ponto fixo
            origin = self.fixed_start
            waypoints = addresses
        else:
            # Chunks intermediários: começam do último endereço do chunk anterior
            origin = prev_chunk_last
            waypoints = addresses
        
        # Define destino
        if is_last:
            # Último chunk: termina no ponto fixo
            destination = self.fixed_start
        else:
            # Chunks intermediários: terminam no último waypoint (que será a origem do próximo)
            destination = waypoints[-1]
            waypoints = waypoints[:-1]  # Remove o último pois será o destino
        
        # Constrói URL
        base_url = "https://www.google.com/maps/dir/"
        
        # Adiciona origem
        url_parts = [urllib.parse.quote(origin)]
        
        # Adiciona waypoints
        for wp in waypoints:
            url_parts.append(urllib.parse.quote(wp))
        
        # Adiciona destino
        url_parts.append(urllib.parse.quote(destination))
        
        url = base_url + '/'.join(url_parts)

        # Force driving mode in the opened Google Maps directions URL.
        # Using the `travelmode` query parameter ensures the browser shows car
        # directions rather than walking/transit/bicycling.
        url = url + '?travelmode=driving'

        return url
    
    def save_route_to_file(self, addresses, optimize=False):
        """
        Salva a rota em um arquivo de texto.
        
        Args:
            addresses: Lista de dicionários de endereços
            optimize: Se True, usa rota otimizada; se False, usa ordem original
        
        Returns:
            str: Nome do arquivo salvo
        """
        if not addresses:
            raise ValueError("Nenhum endereço fornecido")
        
        if optimize:
            # Gera rota otimizada
            route_result = self.nearest_neighbor_route(addresses)
            
            if route_result.get('error'):
                raise Exception(route_result['error'])
            
            # Monta conteúdo do arquivo
            lines = []
            lines.append("=" * 70)
            lines.append("ROTA OTIMIZADA - GERADA AUTOMATICAMENTE")
            lines.append(f"Data: {dt.now().strftime('%d/%m/%Y %H:%M:%S')}")
            lines.append("=" * 70)
            lines.append(f"\nTotal de paradas: {route_result['num_stops']}")
            lines.append(f"Distância total: {route_result['total_distance_km']} km")
            lines.append(f"Tempo estimado: {route_result['total_duration_min']} minutos")
            lines.append("\n" + "=" * 70)
            lines.append("SEQUÊNCIA DE PARADAS:")
            lines.append("=" * 70)
            
            for i, stop in enumerate(route_result['route'], 1):
                if stop['is_start']:
                    lines.append(f"\n{i}. [PONTO DE PARTIDA/RETORNO]")
                    lines.append(f"    {stop['address']}")
                else:
                    lines.append(f"\n{i}. PARADA {i-1}")
                    lines.append(f"    {stop['address']}")
            
            lines.append("\n" + "=" * 70)
            
        else:
            # Rota sequencial (ordem original)
            lines = []
            lines.append("=" * 70)
            lines.append("ROTA SEQUENCIAL - ORDEM ORIGINAL")
            lines.append(f"Data: {dt.now().strftime('%d/%m/%Y %H:%M:%S')}")
            lines.append("=" * 70)
            lines.append(f"\nTotal de paradas: {len(addresses)}")
            lines.append("\n" + "=" * 70)
            lines.append("SEQUÊNCIA DE PARADAS:")
            lines.append("=" * 70)
            
            lines.append(f"\n1. [PONTO DE PARTIDA/RETORNO]")
            lines.append(f"    {self.fixed_start}")
            
            for i, addr in enumerate(addresses, 2):
                lines.append(f"\n{i}. PARADA {i-1}")
                lines.append(f"    {self.format_address_for_api(addr)}")
            
            lines.append(f"\n{len(addresses) + 2}. [RETORNO]")
            lines.append(f"    {self.fixed_start}")
            
            lines.append("\n" + "=" * 70)
        
        # Salva arquivo
        timestamp = dt.now().strftime('%Y%m%d_%H%M%S')
        filename = f"rota_{'otimizada' if optimize else 'sequencial'}_{timestamp}.txt"
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
        
        return filename
