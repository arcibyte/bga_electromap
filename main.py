import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from data.locations import electrolineras, puntos_referencia
from utils.menu import mostrar_encabezado, mostrar_menu_principal, separador, titulo_seccion
from utils.validators import validar_entero, validar_flotante, validar_si_no
from utils.file_io import exportar_logs_todos_formatos

estado = {
    'engine':     None,
    'simulator':  None,
    'logs':       [],
    'mapa_listo': False,
}

def op_ver_ubicaciones():
    titulo_seccion("1. ELECTROLINERAS Y PUNTOS DE REFERENCIA")
    print("\n  electrolineras:")
    for e in electrolineras:
        print(f"    [{e['id']}] {e['nombre']:<32} ({e['lat']}, {e['lon']})")
    print("\n  puntos de referencia:")
    for p in puntos_referencia:
        print(f"    [{p['id']}] {p['nombre']:<35} ({p['lat']}, {p['lon']})")

def op_cargar_mapa():
    titulo_seccion("2. CARGAR MAPA VIAL")
    from graph.graph_engine import GraphEngine
    from simulation.simulator import Simulator

    print("\n  la primera descarga puede tardar 1-2 minutos")
    if not validar_si_no("  continuar? (s/n): "):
        return

    engine = GraphEngine()
    engine.load_map()
    engine.energy_weight()

    print("  asignando nodos...")
    engine.electrolinera_nodes = engine.assign_nodes([dict(e) for e in electrolineras])
    engine.referencia_nodes    = engine.assign_nodes([dict(p) for p in puntos_referencia])

    estado['engine']     = engine
    estado['simulator']  = Simulator(engine)
    estado['simulator'].inicializar_vehiculos()
    estado['mapa_listo'] = True
    print("\n  mapa listo")

def op_ruta_mas_corta():
    titulo_seccion("3. RUTA MAS CORTA (DIJKSTRA)")
    if not estado['mapa_listo']:
        print("  primero cargue el mapa (opcion 2)")
        return

    engine = estado['engine']
    refs   = engine.referencia_nodes

    print("\n  puntos disponibles:")
    for i, p in enumerate(refs):
        print(f"    [{i+1}] {p['nombre']}")

    io = validar_entero("  origen  (numero): ", 1, len(refs)) - 1
    id = validar_entero("  destino (numero): ", 1, len(refs)) - 1
    if io == id:
        print("  origen y destino deben ser distintos")
        return

    from graph.routing import dijkstra
    origen  = refs[io]
    destino = refs[id]

    print(f"\n  calculando: {origen['nombre']} - {destino['nombre']}")

    ruta_d, _ = dijkstra(engine.graph, origen['node'], destino['node'], weight='length')
    ruta_e, _ = dijkstra(engine.graph, origen['node'], destino['node'], weight='consumo')

    if ruta_d:
        print(f"\n  ruta mas corta (distancia):   {engine.get_route_distance(ruta_d)} km"
              f" | consumo: {engine.get_route_consumption(ruta_d)} kWh")
    if ruta_e:
        print(f"  ruta mas eficiente (energia): {engine.get_route_distance(ruta_e)} km"
              f" | consumo: {engine.get_route_consumption(ruta_e)} kWh")

    if ruta_d and validar_si_no("\n  visualizar ruta? (s/n): "):
        from visualization.graph_viz import visualizar_ruta
        visualizar_ruta(engine, ruta_d, origen['nombre'], destino['nombre'])

def op_simulacion():
    titulo_seccion("4. SIMULACION DE RECORRIDOS")
    if not estado['mapa_listo']:
        print("  primero cargue el mapa (opcion 2)")
        return
    n    = validar_entero("  numero de recorridos (1-100): ", 1, 100)
    logs = estado['simulator'].run(n_recorridos=n)
    estado['logs'].extend(logs)
    print(f"\n  logs acumulados: {len(estado['logs'])}")

def op_estadisticas():
    titulo_seccion("5. ESTADISTICAS")
    if not estado['logs']:
        print("  sin datos, ejecute la opcion 4 primero")
        return
    from simulation.stats import generar_estadisticas, imprimir_estadisticas
    imprimir_estadisticas(generar_estadisticas(estado['logs']))

def op_entrenar_modelo():
    titulo_seccion("6. ENTRENAMIENTO DEL MODELO ML")
    if not estado['mapa_listo']:
        print("  primero cargue el mapa (opcion 2)")
        return
    from ml.dataset_builder import construir_dataset, guardar_dataset
    from ml.trainer import entrenar_modelo
    engine = estado['engine']
    df = construir_dataset(engine, engine.electrolinera_nodes, engine.referencia_nodes)
    guardar_dataset(df)
    entrenar_modelo(df)

def op_prediccion():
    titulo_seccion("7. PREDICCION CON MODELO ML")
    from ml.predictor import predecir_electrolinera
    print("\n  ingrese posicion actual del vehiculo:")
    lat = validar_flotante("  latitud  (ej. 7.11): ", 6.5, 7.5)
    lon = validar_flotante("  longitud (ej. -73.10): ", -74.0, -72.5)
    bat = validar_flotante("  bateria % (10-20): ", 10.0, 20.0)
    res = predecir_electrolinera(lat, lon, bat, electrolineras)
    if "error" in res:
        print(f"  {res['error']}")
        return
    print(f"\n  electrolinera recomendada: {res['electrolinera_nombre']}")
    print(f"  distancia estimada:        {res['distancia_estimada_km']} km")
    print(f"  confianza del modelo:      {res['confianza_pct']}%")

def op_mapa_folium():
    titulo_seccion("8. MAPA INTERACTIVO (FOLIUM)")
    from visualization.map_folium import generar_mapa_completo
    engine = estado['engine'] if estado['mapa_listo'] else None
    generar_mapa_completo(electrolineras, puntos_referencia, estado['logs'], engine)

def op_graficas():
    titulo_seccion("9. GRAFICAS ESTADISTICAS (PLOTLY)")
    if not estado['logs']:
        print("  sin datos, ejecute la opcion 4 primero")
        return
    from simulation.stats import generar_estadisticas
    from visualization.charts_plotly import (
        grafica_recargas_por_electrolinera,
        grafica_distribucion_bateria,
        grafica_pie_vehiculos,
    )
    stats = generar_estadisticas(estado['logs'])
    grafica_recargas_por_electrolinera(stats)
    grafica_distribucion_bateria(estado['logs'])
    grafica_pie_vehiculos(stats)

def op_exportar():
    titulo_seccion("10. EXPORTAR DATOS (JSON - CSV - XLSX - TXT)")
    if not estado['logs']:
        print("  sin logs para exportar")
        return
    exportar_logs_todos_formatos(estado['logs'])

def op_sugerir_electrolinera():
    titulo_seccion("11. SUGERENCIA DE NUEVA ELECTROLINERA")

    if not estado['mapa_listo']:
        print("  primero cargue el mapa (opcion 2)")
        return
    if not estado['logs']:
        print("  sin datos de simulacion, ejecute la opcion 4 primero")
        return

    from graph.optimizer import sugerir_nueva_electrolinera, imprimir_sugerencias

    engine          = estado['engine']
    electrolineras_ = engine.electrolinera_nodes

    top_n = validar_entero("  cuantas sugerencias desea ver (1-5): ", 1, 5)

    sugerencias = sugerir_nueva_electrolinera(
        engine, estado['logs'], electrolineras_, top_n=top_n
    )
    imprimir_sugerencias(sugerencias)

    if sugerencias and validar_si_no("\n  visualizar sugerencias en el mapa? (s/n): "):
        import folium as fl
        import webbrowser

        mapa_base = fl.Map(location=[7.08, -73.11], zoom_start=12)
        for i, s in enumerate(sugerencias, 1):
            fl.Marker(
                location=[s['lat'], s['lon']],
                popup=fl.Popup(
                    f"<b>sugerencia {i}</b><br>"
                    f"puntaje: {s['puntaje']}<br>"
                    f"frecuencia: {s['frecuencia_paso']}<br>"
                    f"dist a estacion cercana: {s['distancia_a_cercana_km']} km",
                    max_width=220
                ),
                icon=fl.Icon(color='red', icon='plus', prefix='fa'),
                tooltip=f"nueva estacion sugerida #{i}"
            ).add_to(mapa_base)

        ruta = "data/mapa_sugerencias.html"
        os.makedirs("data", exist_ok=True)
        mapa_base.save(ruta)
        webbrowser.open(f"file://{os.path.abspath(ruta)}")
        print(f"  mapa guardado: {ruta}")


OPCIONES = {
    '1':  op_ver_ubicaciones,
    '2':  op_cargar_mapa,
    '3':  op_ruta_mas_corta,
    '4':  op_simulacion,
    '5':  op_estadisticas,
    '6':  op_entrenar_modelo,
    '7':  op_prediccion,
    '8':  op_mapa_folium,
    '9':  op_graficas,
    '10': op_exportar,
    '11': op_sugerir_electrolinera,
}
CENTINELA = '0'

def main():
    mostrar_encabezado()
    opcion = ''
    while opcion != CENTINELA:
        mostrar_menu_principal()
        opcion = input().strip()
        if opcion == CENTINELA:
            print("\n  cerrando BGA Electromap\n")
            break
        if opcion in OPCIONES:
            try:
                OPCIONES[opcion]()
            except KeyboardInterrupt:
                print("\n  operacion cancelada")
            except Exception as e:
                print(f"\n  error inesperado: {e}")
                import traceback; traceback.print_exc()
        else:
            print(f"  opcion '{opcion}' no valida")
        separador()

if __name__ == "__main__":
    main()