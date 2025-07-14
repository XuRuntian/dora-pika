"""example of using dora-pyrealsense node"""

import logging

import cv2
import numpy as np
from dora import Node

logger = logging.getLogger(__name__)
# sensor_0 = Sensor
# View = ExampleView(None)
# View2d = View.create2d(Sensor.OutputType.Difference, Sensor.OutputType.Depth, Sensor.OutputType.Marker2D)
def main() -> None:
  try:
    node = Node()
    frame_count = 0
    start_time = None
    for event in node:

      if event["type"] == "INPUT":
        struct = event["value"][0]

        if start_time is None:
           start_time = struct["timestamp"].as_py()
        timestamp = struct["timestamp"].as_py()
        elapsed = (timestamp - start_time) / 1000000000


        if event["id"]  == "xense_data":
          frame_count += 1
          fps = frame_count / (elapsed + 0.00000000000001)
          print(f"xense传感器当前帧率: {fps:.2f} FPS, 收到帧数{frame_count}， 运行时间{elapsed}")
          image = struct["image"]
          frame = np.array(image.values).reshape(400, 700, 3).astype(np.uint8)
          cv2.imshow("left_image", frame)
          cv2.waitKey(1)  # 刷新显示
      elif event["type"] == "STOP":
        break
      elif event["type"] == "INPUT_CLOSED":
        break

  except KeyboardInterrupt:
        logger.info("\nExiting dora_xense_example...")
  except Exception as e:
        logger.info(f"error: {e}")
        raise e

  logger.info("dora_xense_example Exit")


if __name__ == "__main__":
  main()
