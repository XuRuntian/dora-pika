import pyarrow as pa

# 定义 image_schema
pa_pika_gripper_fields = [
  pa.field("angle", pa.float16()),
  pa.field("rad", pa.float16()),
  pa.field("state", pa.int16()),
  pa.field("timestamp", pa.int64()),
]
pa_pika_gripper_schema = pa.schema(pa_pika_gripper_fields)
