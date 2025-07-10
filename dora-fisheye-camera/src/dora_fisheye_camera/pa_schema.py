import pyarrow as pa

pa_image = pa.list_(pa.uint8(), 480*640*3)

# 定义 image_schema
pa_image_fields = [
  pa.field("camera_id", pa.string()),
  pa.field("image", pa_image),
  pa.field("timestamp", pa.int64()),
  pa.field("width", pa.int16()),
  pa.field("height", pa.int16()),
  pa.field("encoding", pa.string()),
]
pa_image_schema = pa.schema(pa_image_fields)
