# Rapport de Projet : Framework Modulaire pour la Détection d'Anomalies IoT

## 1. Introduction et Objectifs

Ce projet vise à concevoir et déployer un **framework de traitement de données en temps réel** capable de surveiller un réseau de capteurs IoT. L'objectif principal est de détecter instantanément des anomalies critiques (incendies, fuites de gaz, surchauffes) dans un flux continu de données et d'alerter les opérateurs via un tableau de bord interactif.

Il s'agit d'un problème de **détection d'anomalies non-supervisée** implémenté sur une architecture Big Data distribuée.

## 2. Analyse et Description des Données

### 2.1. Vue d'ensemble
Le jeu de données utilisé provient de relevés de capteurs IoT environnementaux.
*   **Volumétrie** : Les données sont simulées en continu à partir d'un fichier source `test.csv` (12.2 MB) et d'un fichier d'entraînement `train.csv` (36.5 MB).
*   **Variables (Features)** : Le dataset comprend 7 mesures physiques essentielles :
    *   `co`, `lpg`, `smoke` : Détection de gaz et qualité de l'air.
    *   `temp`, `humidity` : Conditions climatiques.
    *   `light`, `motion` : Conditions environnementales physiques.
*   **Identifiants** : Chaque relevé est associé à un `device_id` unique et un horodatage.

### 2.2. Nettoyage et Préparation
Avant d'être exploitées par les modèles, les données subissent plusieurs traitements automatiques dans le pipeline :
*   **Types de Données** : Conversion explicite des valeurs brutes en flottants (`FloatType`).
*   **Gestion des Valeurs Manquantes** : Remplacement des `null` par 0.0 pour assurer la robustesse du flux.
*   **Normalisation** : Utilisation d'un `StandardScaler` pour centrer et réduire les données (Moyenne = 0, Écart-type = 1). Cette étape est cruciale car les échelles de valeurs sont très hétérogènes (ex: Température ~20 vs CO ~0.004).

## 3. Architecture et Technologies

L'infrastructure repose sur une architecture micro-services entièrement conteneurisée via **Docker**.

| Composant | Technologie | Description |
| :--- | :--- | :--- |
| **Ingestion** | **Apache Kafka** | Broker de messages assurant le découplage entre les capteurs et le traitement. Topic : `iot_data`. |
| **Traitement** | **Apache Spark** | Moteur de calcul distribué. Utilise *Spark Structured Streaming* pour l'analyse en temps réel. |
| **Stockage** | **HDFS** | Système de fichiers distribué (Hadoop) pour stocker le modèle ML et l'historique des données (format Parquet). |
| **Machine Learning** | **Spark MLlib** | Librairie utilisée pour entraîner et exécuter le modèle de clustering K-Means. |
| **Visualisation** | **Streamlit** | Interface web Python pour le monitoring des alertes en temps réel. |

## 4. Implémentation par Modules

Le code est organisé de manière modulaire :

1.  **Module Ingestion (`producer.py`)** : Simule l'activité des capteurs. Il injecte aléatoirement des scénarios d'anomalies (ex: *SURCHAUFFE*, *GEL*, *INCENDIE*) pour tester la réactivité du système.
2.  **Module Machine Learning (`train_model.py`)** : Charge les données historiques depuis HDFS, vectorise les features, et entraîne un modèle K-Means (`k=2`). Le modèle apprend à reconnaître un état "normal" de fonctionnement.
3.  **Module Processing (`processor.py`)** : C'est le cœur du système. Il consomme le flux Kafka, normalise les données à la volée, et applique le modèle pour calculer un score d'anomalie.
4.  **Module Visualization (`dashboard.py`)** : Lit le buffer de sortie et présente les KPIs (Température, État, Graphiques) aux utilisateurs.

## 5. Algorithme de Détection (K-Means)

L'approche retenue est basée sur la distance. Le modèle K-Means divise l'espace des données normales en clusters.

*   **Règle de Décision** : Pour chaque nouveau point, on calcule sa **Distance Euclidienne** par rapport au centre du cluster le plus proche.
*   **Seuil d'Alerte** : Si la distance dépasse un seuil défini (ex: `3.0`), le point est marqué comme **ANOMALY**. Sinon, il est **NORMAL**.
*   **Root Cause Analysis** : En cas d'anomalie, l'algorithme identifie quelle variable contribue le plus à la distance (ex: "temp" si la température est inhabituellement élevée) pour expliquer la cause de l'alerte.
