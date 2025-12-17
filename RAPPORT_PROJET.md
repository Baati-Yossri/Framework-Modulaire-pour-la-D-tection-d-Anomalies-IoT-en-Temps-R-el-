# Rapport Détaillé du Projet : Framework IoT pour la Détection d'Anomalies

## 1. Description du Sujet
Le projet est un **Framework complet de traitement de données IoT en temps réel**.
Son objectif est de surveiller un parc de capteurs connectés, de détecter instantanément des anomalies critiques (incendies, fuites de gaz, défaillances) et de fournir une visualisation en direct.
Il met en œuvre une architecture **Big Data** robuste capable de passer à l'échelle, utilisant des technologies standards de l'industrie (Spark, Kafka, Hadoop).

## 2. Architecture & Flux de Données (Pipeline)
Le système suit un pipeline de traitement de données (Data Pipeline) en 5 étapes majeures :

### Étape 1 : Simulation & Ingestion (Producer)
*   **Source** : Un script Python (`producer.py`) simule des capteurs IoT en lisant le fichier `test.csv`.
*   **Injection d'Anomalies** : De manière aléatoire (15% de chance), le producteur modifie les valeurs pour simuler des incidents :
    *   *SURCHAUFFE* (Temp > 85°C)
    *   *GEL* (Temp < -5°C)
    *   *INCENDIE* (Temp très haute + Fumée)
    *   *FUITE_GAZ* (CO et LPG élevés)
*   **Transmission** : Les données sont sérialisées en JSON et envoyées vers un **Topic Kafka** nommé `iot_data`.

### Étape 2 : Messaging (Kafka)
*   **Apache Kafka** agit comme un tampon (buffer) haute performance. Il découple la production (capteurs) de la consommation (analyse), garantissant qu'aucune donnée n'est perdue même si le traitement ralentit.

### Étape 3 : Traitement en Streaming (Spark Structure Streaming)
*   **Spark** s'abonne au topic Kafka et récupère les messages en micro-batchs (toutes les 2 secondes).
*   Il décode le JSON et applique le modèle de Machine Learning pré-entraîné pour classifier chaque événement.

### Étape 4 : Stockage (HDFS & Local)
Les résultats sont sauvegardés à deux endroits :
1.  **HDFS (Hadoop Distributed File System)** : Stockage long terme au format **Parquet** (partitionné par date et par appareil) pour un historique fiable et performant.
2.  **CSV Local (Buffer)** : Un fichier tampon (`viz_buffer.csv`) est mis à jour en temps réel pour alimenter le tableau de bord.

### Étape 5 : Visualisation (Streamlit)
*   Une application web **Streamlit** lit le fichier tampon et affiche :
    *   Les alertes en temps réel.
    *   Les métriques des capteurs.
    *   L'état du système (Normal / Anomalie).

## 3. Description de la Base de Données
Les données proviennent d'un jeu de données de télémétrie environnementale.

*   **Fichiers** :
    *   `train.csv` (36.5 MB) : Base "saine" servant à définir le comportement normal.
    *   `test.csv` (12.2 MB) : Base de test replayée en boucle.
*   **Attributs (Features)** :
    *   `co`, `lpg`, `smoke` : Gaz et fumées (qualité de l'air).
    *   `temp`, `humidity` : Conditions ambiantes.
    *   `light`, `motion` : Environnement physique.

## 4. Outils & Technologies
L'infrastructure est entièrement conteneurisée via **Docker**.

| Composant | Technologie | Rôle |
| :--- | :--- | :--- |
| **Orchestrateur** | Docker Compose | Gère le cycle de vie des conteneurs. |
| **Broker** | Apache Kafka (+ Zookeeper) | Bus de messages centralisé. |
| **Stockage** | Apache Hadoop (HDFS) | Système de fichiers distribué pour modèles et archives. |
| **Moteur** | Apache Spark (PySpark) | Traitement distribué (Entraînement + Streaming). |
| **ML** | Spark MLlib | Bibliothèque de Machine Learning scalable. |
| **Front** | Streamlit | Interface utilisateur interactive. |

## 5. Algorithme & Modèle Machine Learning
Le cœur de la détection repose sur un algorithme non supervisé : **K-Means Clustering**.

### A. Entraînement (`train_model.py`)
Le modèle n'apprend pas "ce qu'est une anomalie", mais **"ce qu'est la normalité"**.
1.  **Chargement** : Lecture de `train.csv` depuis HDFS.
2.  **Vectorisation** : Regroupement des 7 colonnes de capteurs en un seul vecteur caractéristique.
3.  **Normalisation (StandardScaler)** : Étape critique. Comme les variables ont des unités différentes (ex: Température ~20°C vs CO ~0.005), on centre et réduit les données (Moyenne=0, Écart-type=1) pour que le K-Means ne soit pas biaisé par les grandes valeurs.
4.  **Clustering** : L'algorithme K-Means (avec `k=2`) divise les données en 2 groupes principaux représentatifs des états standards de fonctionnement.
5.  **Sauvegarde** : Le modèle (centres des clusters) et le Scaler (moyennes/écarts-types) sont sauvegardés dans HDFS pour être réutilisés.

### B. Détection en Temps Réel (`processor.py`)
La détection se fait par mesure de **distance** (Distance Euclidienne).
Pour chaque nouveau point de donnée $X$ arrivant de Kafka :
1.  On normalise $X$ avec le Scaler chargé.
2.  Le modèle prédit le cluster le plus proche ($C$).
3.  On calcule la distance $D$ entre le point $X$ et le centre du cluster $C$.
    *   $$D = \sqrt{\sum (x_i - c_i)^2}$$
4.  **Règle de Décision** :
    *   Si $D < 3.0$ (Seuil) $\rightarrow$ **NORMAL**. (Le point est proche d'un état connu).
    *   Si $D \ge 3.0$ $\rightarrow$ **ANOMALY**. (Le point est statistiquement éloigné de tout comportement normal connu).
5.  **Explication (Root Cause Analysis)** :
    *   Si c'est une anomalie, l'algorithme regarde quelle dimension du vecteur a la plus grande différence avec le centre ($|x_i - c_i|$).
    *   Exemple : Si la différence de température est la plus grande, la cause retournée est "temp".
