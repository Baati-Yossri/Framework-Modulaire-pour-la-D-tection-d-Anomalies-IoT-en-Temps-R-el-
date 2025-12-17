from pyspark.sql import SparkSession
from pyspark.sql.functions import col, sqrt, pow
from pyspark.sql.types import FloatType
from pyspark.ml.feature import VectorAssembler, StandardScaler
from pyspark.ml.clustering import KMeans

# =========================
# 1. Spark session
# =========================
spark = SparkSession.builder \
    .appName("IoT_KMeans_Training") \
    .master("spark://spark-master:7077") \
    .getOrCreate()

# =========================
# 2. Chargement TRAIN depuis HDFS
# =========================
hdfs_path = "hdfs://namenode:9000/iot/data/train/train.csv"
df = spark.read.csv(hdfs_path, header=True, inferSchema=True)

# =========================
# 3. Features ML
# =========================
features = ['co', 'humidity', 'light', 'lpg', 'motion', 'smoke', 'temp']

for c in features:
    df = df.withColumn(c, col(c).cast(FloatType()))

df = df.na.fill(0.0)

# =========================
# 4. Vectorisation + normalisation
# =========================
assembler = VectorAssembler(inputCols=features, outputCol="raw_features")
df_vec = assembler.transform(df)

scaler = StandardScaler(
    inputCol="raw_features",
    outputCol="features",
    withStd=True,
    withMean=True
)

scaler_model = scaler.fit(df_vec)
df_scaled = scaler_model.transform(df_vec)

# =========================
# 5. Entraînement KMeans
# =========================
kmeans = KMeans(
    k=2,                     # normal / rare
    seed=42,
    featuresCol="features",
    predictionCol="cluster"
)

model = kmeans.fit(df_scaled)

# =========================
# 6. Sauvegarde modèle + scaler
# =========================
model_path = "hdfs://namenode:9000/iot/models/kmeans_iot"
scaler_path = "hdfs://namenode:9000/iot/models/scaler_kmeans"

model.write().overwrite().save(model_path)
scaler_model.write().overwrite().save(scaler_path)

print("✅ Modèle KMeans et scaler sauvegardés dans HDFS")

spark.stop()
