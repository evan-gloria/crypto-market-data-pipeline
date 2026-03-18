import sys
from awsglue.transforms import ApplyMapping
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from awsglue.context import GlueContext
from awsglue.job import Job

# 1. Initialize Glue Context (Now expecting DB and Table parameters)
args = getResolvedOptions(sys.argv, ['JOB_NAME', 'S3_SILVER_PATH', 'GLUE_DB_NAME', 'GLUE_TABLE_NAME'])
sc = SparkContext.getOrCreate()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args['JOB_NAME'], args)

# 2. Extract: Read from the dynamically injected Catalog Database and Table
bronze_dynamic_frame = glueContext.create_dynamic_frame.from_catalog(
    database=args['GLUE_DB_NAME'],
    table_name=args['GLUE_TABLE_NAME'],
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

glueContext.write_dynamic_frame.from_options(
    frame=mapped_dynamic_frame,
    connection_type="s3",
    connection_options={
        "path": silver_path,
        "partitionKeys": ["year", "month", "day"]
    },
    format="parquet",
    transformation_ctx="silver_write"
)

job.commit()