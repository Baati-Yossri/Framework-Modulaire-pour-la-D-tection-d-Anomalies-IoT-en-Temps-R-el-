import time
import json
import random
import os
import pandas as pd
from kafka import KafkaProducer

# =========================
# CONFIG
# =========================
if os.path.exists("/.dockerenv") or os.path.exists("/app"):
    KAFKA_SERVER = "kafka:9092"
    CSV_PATH = "/app/data/input/test.csv"
else:
    KAFKA_SERVER = "localhost:9092"
    CSV_PATH = "data/input/test.csv"

TOPIC = "iot_data"
SENSORS = ['co', 'humidity', 'light', 'lpg', 'motion', 'smoke', 'temp']

print(f"🔌 Connexion à Kafka ({KAFKA_SERVER})...")
try:
    df = pd.read_csv(CSV_PATH)
    df.columns = [c.strip() for c in df.columns]
    if 'device' not in df.columns: raise ValueError("Colonne 'device' manquante")
    records = df.to_dict(orient='records')
    producer = KafkaProducer(bootstrap_servers=[KAFKA_SERVER], value_serializer=lambda x: json.dumps(x).encode('utf-8'))
    print(f"✅ Producer prêt.")
except Exception as e:
    print(f"❌ Erreur : {e}")
    exit(1)


def create_anomaly_values(base_data):
    data = base_data.copy()
    scenario = random.choice(["SURCHAUFFE", "GEL", "FUITE_GAZ", "INCENDIE", "HUMIDITE"])

    if scenario == "SURCHAUFFE":
        data['temp'] = random.uniform(85.0, 110.0)
    elif scenario == "GEL":
        data['temp'] = random.uniform(-20.0, -5.0)
    elif scenario == "FUITE_GAZ":
        data['co'] = random.uniform(0.05, 0.2)
        data['lpg'] = random.uniform(0.05, 0.2)
    elif scenario == "INCENDIE":
        data['temp'] = random.uniform(150.0, 300.0)
        data['smoke'] = random.uniform(0.1, 0.5)
    elif scenario == "HUMIDITE":
        data['humidity'] = random.uniform(98.0, 100.0)
    return data


try:
    while True:
        for row in records:
            device_id = row['device']
            current_data = {k: float(row[k]) for k in SENSORS if k in row}
            current_data['device_id'] = device_id


            if random.random() < 0.15:
                final_payload = create_anomaly_values(current_data)
            else:
                final_payload = current_data

            producer.send(TOPIC, value=final_payload)


            print(f"📤 Envoi de donnée d'après l'appareil {device_id} ...")

            time.sleep(3)

except KeyboardInterrupt:
    print("Arrêt.")
    producer.close()