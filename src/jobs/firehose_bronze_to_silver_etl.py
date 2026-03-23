import sys
from awsglue.transforms import ApplyMapping
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from awsglue.context import GlueContext
from awsglue.job import Job

# 1. Initialize Glue Context (Now expecting DB and Table parameters)
args = getResolvedOptions(sys.argv, ['JOB_NAME', 'S3_SILVER_PATH', 'GLUE_DB_NAME', 'GLUE_TABLE_NAME', 'S3_BRONZE_PATH'])
sc = SparkContext.getOrCreate()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args['JOB_NAME'], args)

# 2. Extract: Read directly from the raw Bronze S3 Bucket
# We bypass the Glue Catalog entirely. Glue Job Bookmarks will automatically
# track which files in this S3 path have already been processed.
bronze_dynamic_frame = glueContext.create_dynamic_frame.from_options(
    connection_type="s3",
    connection_options={
        "paths": [args['S3_BRONZE_PATH']],
        "recurse": True,
        "enablePartitioning": True,
        "partitionKeys": ["year", "month", "day"]
    },
    format="json",
    transformation_ctx="bronze_read"
)
# 3. Transform: Ensure Schema Consistency
# Even though we fixed it in the catalog, this explicitly casts data types 
# for the Silver layer, which is a best practice for Parquet.
mapped_dynamic_frame = ApplyMapping.apply(
    frame=bronze_dynamic_frame,
    mappings=[
        ("E", "bigint", "event_time_ms", "long"),
        ("p", "string", "trade_price", "double"),
        ("q", "string", "trade_quantity", "double"),
        ("m", "boolean", "is_market_maker", "boolean"),
        ("year", "string", "year", "string"),
        ("month", "string", "month", "string"),
        ("day", "string", "day", "string")
    ],
    transformation_ctx="silver_mapping"
)

# 4. Load: Write to Silver Layer as Parquet
# This step automatically compacts the 44+ tiny JSON files into 
# a few highly optimized columnar Parquet files.
silver_path = args['S3_SILVER_PATH']
spark_df = mapped_dynamic_frame.toDF()

# Define the Iceberg target (Format: CatalogName.DatabaseName.TableName)
# Note: 'glue_catalog' is the catalog name we will inject via template.yaml arguments
iceberg_target = f"glue_catalog.{args['GLUE_DB_NAME']}.silver_firehose_trades_iceberg"

try:
    # Write directly to the Iceberg table using the Spark SQL V2 API
    spark_df.writeTo(iceberg_target).append()
    print("Successfully appended to existing Iceberg table.")
except Exception as e:
    if "Table or view not found" in str(e):
        print("First run detected! Creating new Iceberg table...")
        spark_df.writeTo(iceberg_target) \
            .tableProperty("format-version", "2") \
            .partitionedBy("year", "month", "day") \
            .create()
    else:
        # If it's a different error, we still want the job to fail and log it
        raise e

job.commit()