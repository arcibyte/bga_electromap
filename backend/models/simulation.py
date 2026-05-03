import json
import os
from datetime import datetime

class SimulationManager:
    def __init__(self, data_file="backend/data/simulation_logs.json"):
        self.data_file = data_file
        os.makedirs(os.path.dirname(self.data_file), exist_ok=True)

    def save_recharge_event(self, vehicle_type: str, station_name: str, battery_level: float):
        if not (10 <= battery_level <= 20):
            return {"error": "el nivel de batería debe estar entre 10% y 20% para requerir carga"}

        new_event = {
            "timestamp": datetime.now().isoformat(),
            "vehicle_type": vehicle_type,
            "station": station_name,
            "battery_at_arrival": battery_level
        }

        try:
            data = []
            if os.path.exists(self.data_file):
                with open(self.data_file, 'r') as f:
                    data = json.load(f)
            
            data.append(new_event)

            with open(self.data_file, 'w') as f:
                json.dump(data, f, indent=4)
            
            return {"status": "success", "message": "Recarga registrada correctamente."}
        except Exception as e:
            return {"status": "error", "message": str(e)}