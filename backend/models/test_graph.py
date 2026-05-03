from backend.models.graph_engine import GraphEngine
from backend.data.data import electrolineras, puntos_referencia
import osmnx as ox

engine = GraphEngine()
engine.load_map()

engine.assign_nodes(electrolineras)
engine.assign_nodes(puntos_referencia)

engine.tag_electrolineras(electrolineras)

lat = 7.14
lon = -73.12

current_node = ox.nearest_nodes(engine.graph, lon, lat)

estacion, ruta, distancia = engine.nearest_charging_station(
    current_node, 
    electrolineras
)

print ("Estación:", estacion)
print ("Distancia:", distancia)