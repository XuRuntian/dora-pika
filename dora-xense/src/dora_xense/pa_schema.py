import pyarrow as pa

pa_vec3 = pa.list_(pa.float64(), 3)
pa_image = pa.list_(pa.uint8(), 700*400*3)
pa_depth = pa.list_(pa.float32(), 700*400)
pa_mesh = pa.list_(pa.float64(), 35*20*3)
pa_force = pa.list_(pa.float64(), 6)

# 定义 image_schema
pa_xense_fields = [
  pa.field("image", pa_image),
  pa.field("depth", pa_depth),
  pa.field("force", pa_force),
  pa.field("mesh", pa_mesh),
  pa.field("timestamp", pa.int64()),
]
pa_xense_schema = pa.schema(pa_xense_fields)
