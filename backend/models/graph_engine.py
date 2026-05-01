import osmnx as ox
import networkx as nx
from models.data import electrolineras

class GraphEngine:
    def __init__(self):
        self.city = "Bucaramanga, Colombia"
        self.graph = None

    def load_map(self):
        print(f"Cargando mapa de {self.city}...")
        self.graph = ox.graph_from_place(self.city, network_type="drive")
        
        self.graph = ox.add_edge_speeds(self.graph)
        self.graph = ox.add_edge_travel_times(self.graph)
        
        return self.graph

    def get_shortest_path(self, origin_node, target_node):
        if not self.graph:
            self.load_map()
        return nx.shortest_path(self.graph, origin_node, target_node, weight="length")