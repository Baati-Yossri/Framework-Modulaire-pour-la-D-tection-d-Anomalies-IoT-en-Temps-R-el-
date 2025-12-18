# Documentation des Modules IoT

Ce dossier contient les composants modulaires du framework de détection d'anomalies IoT. Chaque sous-dossier gère une partie spécifique du pipeline de données.

## 📂 Structure des Modules

| Module | Fichier Principal | Description |
| :--- | :--- | :--- |
| **Ingestion** | `ingestion/producer.py` | Simule des capteurs IoT et envoie les données vers Kafka. |
| **Machine Learning** | `ml/train_model.py` | Entraîne le modèle K-Means sur les données historiques. |
| **Processing** | `processing/processor.py` | Traite le flux Kafka en temps réel avec Spark Streaming. |
| **Visualization** | `visualization/dashboard.py` | Affiche les alertes et métriques en temps réel via Streamlit. |

---

## 1. Module Ingestion (`ingestion/producer.py`)
**Rôle :** Simuleur de données IoT.
Ce script lit un fichier CSV de base, injecte aléatoirement des anomalies (ex: incendie, fuite de gaz) et envoie les données au topic Kafka `iot_data`.

### Fonctionnalités Clés :
- Simulation de scénarios : `SURCHAUFFE`, `GEL`, `FUITE_GAZ`, `INCENDIE`, `HUMIDITE`.
- Envoi JSON vers Kafka toutes les 3 secondes.

### Exemple de Code (Génération d'Anomalie) :
```python
# Extrait de producer.py
def create_anomaly_values(base_data):
    scenario = "INCENDIE"
    # Simule une température extrême et de la fumée
    base_data['temp'] = random.uniform(150.0, 300.0)
    base_data['smoke'] = random.uniform(0.1, 0.5)
    return base_data
```

---

## 2. Module Machine Learning (`ml/train_model.py`)
**Rôle :** Création du modèle de détection.
Ce script utilise PySpark pour entraîner un algorithme de clustering non-supervisé (K-Means) qui apprendra ce qu'est un comportement "normal".

### Fonctionnalités Clés :
- Chargement des données depuis HDFS.
- Normalisation des features (`StandardScaler`).
- Entraînement K-Means (`k=2`).
- Sauvegarde du modèle et du scaler sur HDFS pour l'inférence.

### Exemple de Code 1 (Préparation & Vectorisation) :
Avant l'entraînement, il est crucial de préparer les données.
1. **Conversion** : `cast(FloatType)` transforme le texte en nombres.
2. **Nettoyage** : `na.fill(0.0)` remplace les valeurs manquantes.
3. **Vectorisation** : `VectorAssembler` fusionne les 7 colonnes en un seul vecteur pour Spark ML.

```python
# Extrait de train_model.py
assembler = VectorAssembler(
    inputCols=['co', 'humidity', 'light', 'lpg', 'motion', 'smoke', 'temp'], 
    outputCol="raw_features"
)
df_vec = assembler.transform(df)
```

### Exemple de Code 2 (Entraînement) :
```python
# Extrait de train_model.py
kmeans = KMeans(
    k=2, 
    featuresCol="features",
    predictionCol="cluster"
)
model = kmeans.fit(df_scaled)
model.save("hdfs://namenode:9000/iot/models/kmeans_iot")
```

---

## 3. Module Processing (`processing/processor.py`)
**Rôle :** Moteur de détection en temps réel.
Ce script Spark Structured Streaming consomme les messages Kafka, applique le modèle K-Means entraîné, et détermine si une donnée est anormale en calculant sa distance par rapport au centre du cluster.

### Fonctionnalités Clés :
- Calcul de distance (Score d'anomalie).
- Identification de la cause (ex: quelle sonde a une valeur aberrante).
- Stockage historique dans HDFS (Parquet).
- Mise à jour d'un buffer CSV local pour le dashboard.

### Exemple de Code (Analyse) :
```python
# Extrait de processor.py
@udf(StringType())
def analyze_anomaly(features, prediction):
    dist = calculate_distance(features, prediction)
    if dist > ANOMALY_THRESHOLD:
        return f"ANOMALY|{dist:.2f}|TEMP_HIGH"
    return f"NORMAL|{dist:.2f}|RAS"
```

---

## 4. Module Visualization (`visualization/dashboard.py`)
**Rôle :** Interface Utilisateur.
Une application Streamlit qui lit le buffer CSV mis à jour par le Processeur pour afficher l'état du système.

### Fonctionnalités Clés :
- Métriques en temps réel (Température, Score).
- Mise en évidence visuelle des anomalies (Rouge).
- Graphiques d'évolution du score d'anomalie.

### Exemple de Code (Affichage) :
```python
# Extrait de dashboard.py
if status == 'ANOMALY':
    st.metric("État", "CRITIQUE", delta_color="inverse")
    st.error(f"Cause: {cause}")
else:
    st.metric("État", "NORMAL")
```
