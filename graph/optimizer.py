import networkx as nx
import numpy as np
from collections import defaultdict
from graph.routing import dijkstra
from graph.nearest_station import encontrar_mas_cercana

#distancia mínima en metros entre estaciones
DISTANCIA_MINIMA_ENTRE_ESTACIONES = 1500

# umbral en km: si la distancia a la electrolinera más cercana supera esto,
# el nodo se considera zona critica
UMBRAL_DISTANCIA_CRITICA_KM = 2.0


def _distancia_entre_nodos(graph, nodo_a, nodo_b):
    """Distancia en metros entre dos nodos usando sus coordenadas."""
    a = graph.nodes[nodo_a]
    b = graph.nodes[nodo_b]
    dlat = (a['y'] - b['y']) * 111320
    dlon = (a['x'] - b['x']) * 111320 * np.cos(np.radians(a['y']))
    return np.sqrt(dlat**2 + dlon**2)


def _reconstruir_ruta_desde_logs(engine, logs):
    """
    Recorre los logs de simulación y recalcula las rutas origen-destino
    para construir el mapa de frecuencia de nodos.
    Retorna dict {nodo: frecuencia}.
    """
    referencias = {r['nombre']: r for r in engine.referencia_nodes if 'node' in r}
    frecuencia  = defaultdict(int)

    for log in logs:
        origen_ref  = referencias.get(log.get('origen'))
        destino_ref = referencias.get(log.get('destino'))
        if not origen_ref or not destino_ref:
            continue

        ruta, _ = dijkstra(
            engine.graph,
            origen_ref['node'],
            destino_ref['node'],
            weight='length'
        )
        if ruta:
            for nodo in ruta:
                frecuencia[nodo] += 1

    return frecuencia


def _detectar_zonas_criticas(engine, logs, electrolineras):
    referencias  = {r['nombre']: r for r in engine.referencia_nodes if 'node' in r}
    criticidad   = defaultdict(float)

    for log in logs:
        destino_ref = referencias.get(log.get('destino'))
        if not destino_ref:
            continue

        nodo        = destino_ref['node']
        bateria     = log.get('bateria_al_llegar', 20)
        dist_est_km = log.get('distancia_a_electrolinera_km', 0)

        # mayor puntaje cuanto más baja la batería y más lejos la estación
        factor_bateria  = max(0, (12 - bateria) / 12)
        factor_distancia = min(1, dist_est_km / UMBRAL_DISTANCIA_CRITICA_KM)

        criticidad[nodo] += (factor_bateria + factor_distancia)

    return criticidad


def _filtrar_por_restriccion_geografica(candidatos_ordenados, engine, electrolineras):
    nodos_existentes = [
        est['node'] for est in electrolineras if 'node' in est
    ]
    seleccionados = []

    for nodo, puntaje in candidatos_ordenados:
        demasiado_cerca = False

        # Verificar contra electrolineras existentes
        for nodo_est in nodos_existentes:
            try:
                dist = _distancia_entre_nodos(engine.graph, nodo, nodo_est)
                if dist < DISTANCIA_MINIMA_ENTRE_ESTACIONES:
                    demasiado_cerca = True
                    break
            except Exception:
                continue

        if demasiado_cerca:
            continue

        # verificar contra candidatos ya seleccionados
        for nodo_sel, _ in seleccionados:
            try:
                dist = _distancia_entre_nodos(engine.graph, nodo, nodo_sel)
                if dist < DISTANCIA_MINIMA_ENTRE_ESTACIONES:
                    demasiado_cerca = True
                    break
            except Exception:
                continue

        if not demasiado_cerca:
            seleccionados.append((nodo, puntaje))

    return seleccionados


def sugerir_nueva_electrolinera(engine, logs, electrolineras, top_n=3):
   
    if not logs:
        print(" no hay logs de simulación. Ejecute la opción 4 primero.")
        return []

    print("analizando frecuencia de rutas...")
    frecuencia = _reconstruir_ruta_desde_logs(engine, logs)

    print("detectando zonas críticas...")
    criticidad = _detectar_zonas_criticas(engine, logs, electrolineras)

    # normalizar frecuencia entre 0 y 1
    max_freq = max(frecuencia.values()) if frecuencia else 1
    freq_norm = {n: v / max_freq for n, v in frecuencia.items()}

    # normalizar criticidad entre 0 y 1
    max_crit = max(criticidad.values()) if criticidad else 1
    crit_norm = {n: v / max_crit for n, v in criticidad.items()}

    print("  [→] Calculando distancias a electrolineras existentes...")

    # calcular puntaje combinado para cada nodo candidato
    nodos_candidatos = set(frecuencia.keys()) | set(criticidad.keys())
    puntajes = {}

    for nodo in nodos_candidatos:
        # distancia al nodo de electrolinera más cercana (normalizada)
        dist_min = float('inf')
        for est in electrolineras:
            if 'node' not in est:
                continue
            try:
                d = _distancia_entre_nodos(engine.graph, nodo, est['node'])
                dist_min = min(dist_min, d)
            except Exception:
                continue

        # normalizar distancia: más lejos = mayor puntaje (zona sin cobertura)
        umbral_m = UMBRAL_DISTANCIA_CRITICA_KM * 1000
        dist_score = min(1.0, dist_min / umbral_m)

        puntaje = (
            0.40 * freq_norm.get(nodo, 0) +
            0.40 * crit_norm.get(nodo, 0) +
            0.20 * dist_score
        )
        puntajes[nodo] = puntaje

    # ordenar por puntaje descendente
    candidatos_ordenados = sorted(puntajes.items(), key=lambda x: -x[1])

    print("  [→] Aplicando restricción geográfica...")
    candidatos_filtrados = _filtrar_por_restriccion_geografica(
        candidatos_ordenados, engine, electrolineras
    )

    # construir resultado con informacion geográfica
    resultados = []
    for nodo, puntaje in candidatos_filtrados[:top_n]:
        datos_nodo = engine.graph.nodes[nodo]
        lat = datos_nodo['y']
        lon = datos_nodo['x']

        # electrolinera mas cercana al candidato
        est_cercana, _, dist_cercana = encontrar_mas_cercana(
            engine.graph, nodo, electrolineras
        )

        resultados.append({
            'nodo':                    nodo,
            'lat':                     round(lat, 6),
            'lon':                     round(lon, 6),
            'puntaje':                 round(puntaje, 4),
            'frecuencia_paso':         frecuencia.get(nodo, 0),
            'criticidad':              round(criticidad.get(nodo, 0), 3),
            'electrolinera_mas_cercana': est_cercana['nombre'] if est_cercana else 'N/A',
            'distancia_a_cercana_km':  round(dist_cercana / 1000, 3) if dist_cercana < float('inf') else None,
        })

    return resultados


def imprimir_sugerencias(sugerencias):
    if not sugerencias:
        print(" ! no se encontraron ubicaciones candidatas.")
        return

    print(f"\n  {'='*58}")
    print(f"  ubicaciones sugeridas para nueva electrolinera")
    print(f"  {'='*58}")

    for i, s in enumerate(sugerencias, 1):
        print(f"\n  opcion {i}")
        print(f"    coordenadas:              ({s['lat']}, {s['lon']})")
        print(f"    puntaje combinado:        {s['puntaje']}")
        print(f"    frecuencia de paso:       {s['frecuencia_paso']} veces")
        print(f"    indice de criticidad:     {s['criticidad']}")
        print(f"    estacion mas cercana:     {s['electrolinera_mas_cercana']}")
        print(f"    distancia a esa estacion: {s['distancia_a_cercana_km']} km")