"""example of using dora-pyrealsense node"""

import logging

from dora import Node

logger = logging.getLogger(__name__)


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


        if event["id"]  == "pika_gripper_data":
          frame_count += 1
          data = struct["rad"]
          fps = frame_count / (elapsed + 0.00000000000001)
          print(f"gripper当前帧率: {fps:.2f} FPS, 收到帧数{frame_count}， 运行时间{elapsed}")
          print(data)
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
