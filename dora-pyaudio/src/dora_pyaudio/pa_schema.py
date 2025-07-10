import pyarrow as pa

pa_audio = pa.list_(pa.int16(), 1024)

# 定义 image_schema
pa_audio_fields = [
  pa.field("audio_data", pa_audio),
  pa.field("timestamp", pa.int64()),
  pa.field("sample_rate", pa.int32()),
  pa.field("channels", pa.int32()),
  pa.field("format", pa.int32()),
  pa.field("chunk_size", pa.int32()),

]
pa_audio_schema = pa.schema(pa_audio_fields)
