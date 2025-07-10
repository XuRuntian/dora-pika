"""example of using dora-pyrealsense node"""
import logging

import cv2
import numpy as np
from dmrobotics import put_arrows_on_image
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
                elapsed = (timestamp - start_time) / 1000000000 + + 0.00000000000001
                if event["id"] == "touch_data":
                    frame_count += 1
                    fps = frame_count / elapsed

                    print(f"当前帧率: {fps:.2f} FPS, 收到帧数{frame_count}， 运行时间{elapsed}")

                    img = struct["img"]
                    img = np.array(img.values).reshape(240, 320).astype(np.uint8)
                    black_img = np.zeros_like(img)
                    black_img = np.stack([black_img]*3, axis=-1)

                    shear = struct["shear"]
                    shear = np.array(shear.values).reshape(240, 320,2).astype(np.float32)

                    depth = struct["depth"]
                    depth = np.array(depth.values).reshape(240, 320).astype(np.float32)
                    depth_img = cv2.applyColorMap((depth*0.25* 255.0).astype('uint8'), cv2.COLORMAP_HOT)


                    deformation = struct["deformation"]
                    deformation = np.array(deformation.values).reshape(240, 320,2).astype(np.float32)

                    # 显示图像
                    cv2.imshow('depth', depth_img)
                    cv2.imshow('img', img)
                    cv2.imshow('deformation', put_arrows_on_image(black_img, deformation*20))
                    cv2.imshow('shear', put_arrows_on_image(black_img, shear*20))
                    cv2.waitKey(3)


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
