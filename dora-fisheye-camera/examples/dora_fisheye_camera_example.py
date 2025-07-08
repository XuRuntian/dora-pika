"""example of using dora-pyrealsense node"""

import logging

from dora import Node
import sys
import pprint
import cv2
import numpy as np
import time 
logger = logging.getLogger(__name__)


def main() -> None:
  try:
    node = Node()
    frame_count_right = 0
    frame_count_left = 0
    start_time = None
    for event in node:

      if event["type"] == "INPUT":

        if start_time is None:
           start_time = struct["timestamp"].as_py()
        timestamp = struct["timestamp"].as_py()
        elapsed = (timestamp - start_time) / 1000000000

        struct = event["value"][0]

        if event["id"]  == "image_left":
          frame_count_left += 1
          fps = frame_count_left / (elapsed + 0.00000000000001)
          print(f"左鱼眼相机当前帧率: {fps:.2f} FPS, 收到帧数{frame_count_right}， 运行时间{elapsed}")
          image = struct["image"]
          frame = np.array(image.values).reshape(480, 640, 3).astype(np.uint8)
          cv2.imshow("left", frame)
          cv2.waitKey(1)  # 刷新显示

        if event["id"]  == "image_right":
          frame_count_right += 1
          fps = frame_count_right / (elapsed + 0.00000000000001)
          print(f"右鱼眼相机当前帧率: {fps:.2f} FPS, 收到帧数{frame_count_right}， 运行时间{elapsed}")
          image = struct["image"]
          frame = np.array(image.values).reshape(480, 640, 3).astype(np.uint8)
          cv2.imshow("right", frame)
          cv2.waitKey(1)  # 刷新显示
          

      elif event["type"] == "STOP":
        break
      elif event["type"] == "INPUT_CLOSED":
        break

  except KeyboardInterrupt:
        logger.info("\nExiting dora_vive_example...")
  except Exception as e:
        logger.info(f"error: {e}")
        raise e

  logger.info("dora_pyrealsense_example Exit")


if __name__ == "__main__":
  main()
