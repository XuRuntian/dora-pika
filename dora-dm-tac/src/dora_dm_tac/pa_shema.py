import pyarrow as pa

pa_vec3 = pa.list_(pa.float64(), 3)
pa_image = pa.list_(pa.uint8(), 240*320)
pa_shear = pa.list_(pa.float32(), 240*320*2)
pa_depth = pa.list_(pa.float32(), 240*320)
pa_deformation = pa.list_(pa.float32(), 240*320*2)

# 定义 image_schema
pa_sensor_fields = [
  pa.field("serial_number", pa.string()),
  pa.field("img", pa_image),
  pa.field("shear", pa_shear),
  pa.field("depth", pa_depth),
  pa.field("deformation", pa_deformation),
  pa.field("timestamp", pa.int64()),
]
pa_sensor_schema = pa.schema(pa_sensor_fields)
