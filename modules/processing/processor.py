from pyspark.sql import SparkSession
from pyspark.sql.functions import from_json, col, udf, current_timestamp, date_format
from pyspark.sql.types import StructType, StructField, FloatType, StringType
from pyspark.ml.clustering import KMeansModel
from pyspark.ml.feature import StandardScalerModel, VectorAssembler
import math
import os
import pandas as pd
import shutil

# =========================
# 1. Configuration
# =========================
spark = SparkSession.builder \
    .appName("IoT_KMeans_Processor") \
    .master("spark://spark-master:7077") \
    .config("spark.jars.packages", "org.apache.spark:spark-sql-kafka-0-10_2.12:3.4.1") \
    .config("spark.sql.shuffle.partitions", "5") \
    .getOrCreate()

MODEL_PATH = "hdfs://namenode:9000/iot/models/kmeans_iot"
SCALER_PATH = "hdfs://namenode:9000/iot/models/scaler_kmeans"
HISTORY_PATH = "hdfs://namenode:9000/iot/data/history_parquet"
VIZ_BUFFER_PATH = "/app/data/viz_buffer.csv"

# --- ORDRE STRICT DES COLONNES ---
# C'est cette liste qui garantit que "status" va dans "status" et pas ailleurs
COLUMNS_ORDER = [
    "device_id", "temp", "humidity", "smoke", "co", "lpg", "motion", "light",
    "cluster", "status", "score", "cause", "timestamp"
]

# =========================
# 2. Reset Buffer (Nettoyage au démarrage)
# =========================
print("🧹 [INIT] Nettoyage du fichier tampon...")
if os.path.exists(VIZ_BUFFER_PATH):
    os.remove(VIZ_BUFFER_PATH)

# Création fichier vide avec les en-têtes corrects
pd.DataFrame(columns=COLUMNS_ORDER).to_csv(VIZ_BUFFER_PATH, index=False)
print("✅ [INIT] Buffer prêt.")

# =========================
# 3. Chargement Modèles
# =========================
try:
    kmeans_model = KMeansModel.load(MODEL_PATH)
    scaler_model = StandardScalerModel.load(SCALER_PATH)
    cluster_centers = kmeans_model.clusterCenters()
except Exception as e:
    print(f"❌ ERREUR MODÈLES : {e}")
    spark.stop()
    exit(1)

features_list = ['co', 'humidity', 'light', 'lpg', 'motion', 'smoke', 'temp']
ANOMALY_THRESHOLD = 3.0


@udf(StringType())
def analyze_anomaly(features, prediction):
    if features is None: return "ERROR|0|NONE"
    center = cluster_centers[prediction]
    dist = math.sqrt(sum([(f - c) ** 2 for f, c in zip(features, center)]))

    if dist < ANOMALY_THRESHOLD:
        return f"NORMAL|{dist:.2f}|RAS"

    diffs = [abs(f - c) for f, c in zip(features, center)]
    cause = features_list[diffs.index(max(diffs))]
    return f"ANOMALY|{dist:.2f}|{cause}"


# =========================
# 4. Pipeline Streaming
# =========================
schema = StructType([
    StructField("device_id", StringType()),
    StructField("co", FloatType()), StructField("humidity", FloatType()),
    StructField("light", FloatType()), StructField("lpg", FloatType()),
    StructField("motion", FloatType()), StructField("smoke", FloatType()),
    StructField("temp", FloatType())
])

kafka_stream = spark.readStream.format("kafka") \
    .option("kafka.bootstrap.servers", "kafka:9092") \
    .option("subscribe", "iot_data").load()

df = kafka_stream.select(from_json(col("value").cast("string"), schema).alias("data")).select("data.*").na.fill(0.0)

assembler = VectorAssembler(inputCols=features_list, outputCol="raw_features")
vec_df = assembler.transform(df)
scaled_df = scaler_model.transform(vec_df)
pred_df = kmeans_model.transform(scaled_df)

# On prépare le timestamp en STRING pour le CSV
final_df = pred_df.withColumn("analysis", analyze_anomaly(col("features"), col("cluster"))) \
    .withColumn("ts_obj", current_timestamp()) \
    .withColumn("date", date_format(col("ts_obj"), "yyyy-MM-dd")) \
    .withColumn("timestamp_str", date_format(col("ts_obj"), "yyyy-MM-dd HH:mm:ss"))


# =========================
# 5. Sauvegarde
# =========================
def save_batch(batch_df, batch_id):
    batch_df.persist()
    cnt = batch_df.count()
    if cnt > 0:
        print(f"⚡ Batch {batch_id} : {cnt} événements")

        # A. HDFS (Parquet avec objet timestamp pour partitionnement correct)
        try:
            (batch_df.select("device_id", "ts_obj", "date", "temp", "humidity", "smoke", "cluster", "analysis")
             .withColumnRenamed("ts_obj", "timestamp")
             .write.mode("append").partitionBy("date", "device_id").parquet(HISTORY_PATH))
        except:
            pass

        # B. Local Buffer (CSV pour Dashboard)
        try:
            # 1. Extraction en Pandas
            # On renomme timestamp_str en 'timestamp' pour l'affichage
            pdf = batch_df.select("device_id", "temp", "humidity", "smoke", "co", "lpg", "motion", "light",
                                  "cluster", "analysis", col("timestamp_str").alias("timestamp")).toPandas()

            # 2. Parsing de la colonne Analysis
            pdf[['status', 'score', 'cause']] = pdf['analysis'].str.split('|', expand=True)
            pdf['score'] = pdf['score'].astype(float)

            # 3. REORGANISATION STRICTE DES COLONNES (LE FIX EST ICI)
            # On force le DataFrame à suivre exactement l'ordre du header créé au début
            pdf_final = pdf[COLUMNS_ORDER]

            # 4. Écriture sans en-tête (mode append)
            pdf_final.to_csv(VIZ_BUFFER_PATH, mode='a', header=False, index=False)
            print("   -> CSV Synchronisé OK")
        except Exception as e:
            print(f"❌ Erreur Buffer CSV: {e}")

    batch_df.unpersist()


query = final_df.writeStream \
    .foreachBatch(save_batch) \
    .trigger(processingTime='2 seconds') \
    .start()

query.awaitTermination()