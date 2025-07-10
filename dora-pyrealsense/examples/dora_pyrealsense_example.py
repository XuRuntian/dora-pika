"""example of using dora-pyrealsense node"""

import logging

from dora import Node

logger = logging.getLogger(__name__)


def main() -> None:
  try:
    node = Node()
    frame_count_right_image = 0
    frame_count_left_image = 0
    frame_count_right_depth = 0
    frame_count_left_depth = 0
    start_time = None

    for event in node:
      if event["type"] == "INPUT":
        struct = event["value"][0]

        if start_time is None:
            start_time = struct["timestamp"].as_py()
        timestamp = struct["timestamp"].as_py()
        elapsed = (timestamp - start_time) / 1000000000 + + 0.00000000000001


        if event["id"]  == "image_left":

          frame_count_left_image += 1
          fps = frame_count_left_image / elapsed
          print(f"左RGB相机当前帧率: {fps:.2f} FPS, 收到帧数{frame_count_left_image}， 运行时间{elapsed}")
          # image = struct["image"]
          # frame = np.array(image.values).reshape(480, 640, 3).astype(np.uint8)
          # cv2.imshow("left_image", frame)
          # cv2.waitKey(1)  # 刷新显示

        if event["id"] == "depth_left":
          frame_count_left_depth += 1
          fps = frame_count_left_image / elapsed
          print(f"左深度相机当前帧率: {fps:.2f} FPS, 收到帧数{frame_count_left_image}， 运行时间{elapsed}")
          # depth = struct["depth"]
          # frame = np.array(depth.values).reshape(480, 640).astype(np.uint16)
          # cv2.imshow("left_depth", frame)
          # cv2.waitKey(1)  # 刷新显示
        if event["id"]  == "image_right":
          frame_count_right_image += 1
          fps = frame_count_right_image / (elapsed + 0.00000000000001)
          print(f"右RGB相机当前帧率: {fps:.2f} FPS, 收到帧数{frame_count_left_image}， 运行时间{elapsed}")
          # image = struct["image"]
          # frame = np.array(image.values).reshape(480, 640, 3).astype(np.uint8)
          # cv2.imshow("right_image", frame)
          # cv2.waitKey(1)  # 刷新显示
        if event["id"] == "depth_right":
          frame_count_right_depth += 1
          fps = frame_count_right_image / elapsed
          print(f"右深度相机当前帧率: {fps:.2f} FPS, 收到帧数{frame_count_left_image}， 运行时间{elapsed}")
          # depth = struct["depth"]
          # frame = np.array(depth.values).reshape(480, 640).astype(np.uint16)
          # cv2.imshow("right_depth", frame)
          # cv2.waitKey(1)  # 刷新显示
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
