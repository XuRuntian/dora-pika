import pyarrow as pa

pa_vec3 = pa.list_(pa.float64(), 3) 
pa_image = pa.list_(pa.uint8(), 480*640*3) 
pa_depth = pa.list_(pa.uint16(), 480*640) 

# 定义 image_schema
pa_image_fields = [
  pa.field("serial_number", pa.string()),
  pa.field("image", pa_image),
  pa.field("timestamp", pa.int64()),
  pa.field("width", pa.int16()),
  pa.field("height", pa.int16()),
  pa.field("encoding", pa.string()),
]
pa_image_schema = pa.schema(pa_image_fields)

# 定义depth_schema
pa_depth_fileds = [
  pa.field("serial_number", pa.string()),
  pa.field("depth", pa_depth),
  pa.field("timestamp", pa.int64()),
  pa.field("width", pa.int16()),
  pa.field("height", pa.int16()),
]

pa_depth_schema = pa.schema(pa_depth_fileds)
