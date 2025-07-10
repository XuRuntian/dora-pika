import pyarrow as pa

pa_image = pa.list_(pa.uint8(), 240*320*3)
pa_depth = pa.list_(pa.float64(), 240*320)
pa_contact_mask = pa.list_(pa.bool_(), 240*320)
pa_gradients = pa.list_(pa.float64(), 240*320*2)
# 定义 image_schema
pa_gelsight_fields = [
  pa.field("image", pa_image),
  pa.field("depth_map", pa_depth),
  pa.field("contact_mask", pa_contact_mask),
  pa.field("gradients", pa_gradients),
  pa.field("timestamp", pa.int64()),
]
pa_gelsight_schema = pa.schema(pa_gelsight_fields)
