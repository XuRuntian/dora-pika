"""example of using dora-pyrealsense node with enhanced visualization"""
import logging
import os

import cv2
import numpy as np
from config import GSConfig  # 导入GSConfig用于加载JSON配置
from dora import Node

from utilities.image_processing import (
    apply_cmap,
    color_map_from_txt,
    normalize_array,
    stack_label_above_image,
    trim_outliers,
)

logger = logging.getLogger(__name__)


def main() -> None:
    try:
        node = Node()
        frame_count = 0
        start_time = None

        # 获取当前脚本所在目录
        script_dir = os.path.dirname(os.path.abspath(__file__))

        # 加载配置文件
        config_path = os.path.join(script_dir, "default_config.json")
        logger.info(f"Loading config from: {config_path}")

        # 使用GSConfig加载配置文件
        gs_config = GSConfig(config_path)
        config = gs_config.config

        # 加载颜色映射文件（从配置路径或默认路径）
        cmap_path = config.cmap_txt_path
        if not os.path.isabs(cmap_path):
            cmap_path = os.path.join(script_dir, cmap_path)

        logger.info(f"Loading colormap from: {cmap_path}")
        cmap = color_map_from_txt(
            path=cmap_path,
            is_bgr=config.cmap_in_bgr_format
        )

        for event in node:
            if event["type"] == "INPUT":
                struct = event["value"][0]
                if start_time is None:
                    start_time = struct["timestamp"].as_py()
                timestamp = struct["timestamp"].as_py()
                elapsed = (timestamp - start_time) / 1000000000 + 0.00000000000001

                if event["id"] == "data":
                    frame_count += 1
                    fps = frame_count / elapsed
                    # 提取和处理数据
                    image = struct["image"]
                    image = np.array(image.values).reshape(
                        config.camera_height,
                        config.camera_width,
                        3
                    ).astype(np.uint8)

                    depth_map = struct["depth_map"]
                    depth_map = np.array(depth_map.values).reshape(
                        config.camera_height,
                        config.camera_width
                    ).astype(np.float64)

                    contact_mask = struct["contact_mask"]
                    contact_mask = np.array(contact_mask.values).reshape(
                        config.camera_height,
                        config.camera_width
                    ).astype(np.bool_)

                    gradients = struct["gradients"]
                    gradients = np.array(gradients.values).reshape(
                        config.camera_height,
                        config.camera_width,
                        2
                    ).astype(np.float64)

                    # 处理深度图用于显示
                    depth_map_trimmed = trim_outliers(depth_map, 1, 99)
                    depth_map_normalized = normalize_array(
                        array=depth_map_trimmed,
                        min_divider=10
                    )
                    depth_rgb = apply_cmap(data=depth_map_normalized, cmap=cmap)

                    # 转换掩码为8位灰度图
                    contact_mask = (contact_mask * 255).astype(np.uint8)

                    # 将灰度图转换为3通道以便堆叠
                    contact_mask_rgb = cv2.cvtColor(contact_mask, cv2.COLOR_GRAY2BGR)

                    # 在图像上方添加标签
                    frame_labeled = stack_label_above_image(
                        image, f"Camera Feed {fps:.2f} FPS", 30
                    )

                    depth_labeled = stack_label_above_image(depth_rgb, "Depth", 30)
                    contact_mask_labeled = stack_label_above_image(
                        contact_mask_rgb, "Contact Mask", 30
                    )

                    # 添加间隔
                    spacing_size = 30
                    horizontal_spacer = np.zeros(
                        (frame_labeled.shape[0], spacing_size, 3), dtype=np.uint8
                    )

                    # 水平堆叠图像
                    top_row = np.hstack(
                        (
                            frame_labeled,
                            horizontal_spacer,
                            contact_mask_labeled,
                            horizontal_spacer,
                            depth_labeled,
                        )
                    )

                    display_frame = top_row

                    # 缩放显示帧
                    display_frame = cv2.resize(
                        display_frame,
                        (
                            int(display_frame.shape[1] * config.cv_image_stack_scale),
                            int(display_frame.shape[0] * config.cv_image_stack_scale),
                        ),
                        interpolation=cv2.INTER_NEAREST,
                    )
                    display_frame = display_frame.astype(np.uint8)

                    # 显示组合图像
                    cv2.imshow('GelSight Data Visualization', display_frame)

                    # 处理按键事件
                    key = cv2.waitKey(1)
                    if key == ord('q'):
                        break

            elif event["type"] == "STOP":
                break
            elif event["type"] == "INPUT_CLOSED":
                break

    except KeyboardInterrupt:
        logger.info("\nExiting dora_vive_example...")
    except Exception as e:
        logger.error(f"Error: {e}")
        # 打印堆栈跟踪信息，便于调试
        import traceback
        logger.error(traceback.format_exc())
        raise e
    finally:
        # 确保关闭所有窗口
        cv2.destroyAllWindows()

    logger.info("dora_pyrealsense_example Exit")


if __name__ == "__main__":
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    main()
