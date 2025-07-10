import logging
import os
import signal
import threading
import time
from dataclasses import dataclass, field

import cv2
import numpy as np
import pyarrow as pa
from config import GSConfig
from dora import Node
from typing_extensions import Self

from dora_gelsight.pa_schema import pa_gelsight_schema as sensor_schema
from utilities.gelsightmini import GelSightMini
from utilities.reconstruction import Reconstruction3D

logger = logging.getLogger(__name__)

RUNNER_CI = True if os.getenv("CI") == "true" else False
MAX_RETRIES = 5  # 最大重试次数
RETRY_DELAY = 0.1  # 重试延迟(秒)
# 从环境变量获取配置
DEVICE_INDEX = int(os.getenv("DEVICE_INDEX", "320"))
IMAGE_WIDTH = int(os.getenv("IMAGE_WIDTH", "320"))
IMAGE_HEIGHT = int(os.getenv("IMAGE_HEIGHT", "240"))
CONFIG_PATH = os.getenv("GS_CONFIG_PATH", "default_config.json")

@dataclass
class ImageData:
    """Stores image data from GelSight with thread-safe access."""

    _lock: threading.Lock = field(default_factory=threading.Lock)
    _has_data: bool = False
    raw_image: np.ndarray = None
    depth_map: np.ndarray = None
    contact_mask: np.ndarray = None
    gradients: np.ndarray = None
    timestamp: int = 0
    def update_data(
        self: Self,
        raw_image: np.ndarray,
        depth_map: np.ndarray,
        contact_mask: np.ndarray,
        gradients: np.ndarray,
        timestamp: int
    ) -> None:
        """Update image data."""
        with self._lock:
            self.raw_image = raw_image
            self.depth_map = depth_map
            self.contact_mask = contact_mask
            self.gradients = gradients
            self._has_data = True
            self.timestamp = timestamp
    def read_data(self: Self) -> tuple[bool, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Read image data."""
        with self._lock:
            return (
                self._has_data,
                self.raw_image,
                self.depth_map,
                self.contact_mask,
                self.gradients,
                self.timestamp,
            )

def receive_data_from_gelsight(
    image_data: ImageData,
    dora_stop_event: threading.Event,
    gelsight_close_event: threading.Event,
) -> None:
    """Polls GelSight camera for image data and processes it."""
    try:


        # 加载配置
        gs_config = GSConfig(CONFIG_PATH)
        config = gs_config.config

        # 初始化GelSight相机
        cam_stream = GelSightMini(
            target_width=IMAGE_WIDTH,
            target_height=IMAGE_HEIGHT
        )

        # 获取设备列表并选择指定设备
        devices = cam_stream.get_device_list()
        if not devices:
            logger.error("No GelSight Mini camera connected.")
            gelsight_close_event.set()
            return

        if DEVICE_INDEX >= len(devices):
            logger.error(f"Device index {DEVICE_INDEX} out of range for {len(devices)} devices.")
            gelsight_close_event.set()
            return

        cam_stream.select_device(DEVICE_INDEX)
        cam_stream.start()

        # 初始化3D重建
        reconstruction = Reconstruction3D(
            image_width=IMAGE_WIDTH,
            image_height=IMAGE_HEIGHT,
            use_gpu=config.use_gpu
        )

        if reconstruction.load_nn(config.nn_model_path) is None:
            logger.error("Failed to load neural network model.")
            gelsight_close_event.set()
            return


        while not dora_stop_event.is_set():

            # 从相机获取帧(带重试逻辑)
            frame = None
            for _ in range(MAX_RETRIES):
                frame = cam_stream.update(dt=0)
                if frame is not None:
                    break
                time.sleep(RETRY_DELAY)
                if dora_stop_event.is_set():
                    break

            if frame is None:
                logger.warning("Failed to get frame after multiple retries")
                continue

            try:
                # 转换为RGB格式
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

                # 计算深度图、接触掩模和梯度
                depth_map, contact_mask, grad_x, grad_y = reconstruction.get_depthmap(
                    image=frame,
                    markers_threshold=(config.marker_mask_min, config.marker_mask_max)
                )
                gradients = np.stack([grad_x, grad_y], axis=-1)
                timestamp = time.time_ns()
                # 更新共享数据
                image_data.update_data(frame, depth_map, contact_mask, gradients, timestamp)

            except Exception as e:
                logger.exception("Error processing frame: %s", e)

    except Exception as e:
        logger.exception("GelSight error: %s", e)
    finally:
        # 确保资源释放
        logger.info("Closing GelSight camera...")
        if 'cam_stream' in locals() and cam_stream.camera is not None:
            cam_stream.camera.release()
        cv2.destroyAllWindows()
        gelsight_close_event.set()

def send_data_through_dora(
    image_data: ImageData,
    dora_stop_event: threading.Event,
    gelsight_close_event: threading.Event,
) -> None:
    """Sends image and processed data via Dora outputs."""
    node = Node()
    try:
        for event in node:
            if gelsight_close_event.is_set():
                dora_stop_event.set()
                break
            if event["type"] == "INPUT" and event["id"] == "tick":
                has_data, raw_image, depth_map, contact_mask, gradients,timestamp = image_data.read_data()
                if has_data:
                    sensor_batch = pa.record_batch(
                        {
                            "image": [raw_image.ravel()],
                            "depth_map": [depth_map.ravel()],
                            "contact_mask": [contact_mask.ravel()],
                            "gradients": [gradients.ravel()],
                            "timestamp": [timestamp],
                        },
                        schema = sensor_schema,
                    )
                    node.send_output("gelsight_data", sensor_batch)
                time.sleep(0.001)  # 控制发送频率

            elif event["type"] == "STOP":
                dora_stop_event.set()
                break
    except Exception as e:
        logger.exception("Dora error: %s", e)
    finally:
        # 标记线程停止
        dora_stop_event.set()

def signal_handler() -> None:
    """处理SIGINT信号（Ctrl+C）"""
    logger.info("Received Ctrl+C. Stopping gracefully...")
    dora_stop_event.set()

if __name__ == "__main__":
    # 配置日志
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # 创建事件和数据存储
    image_data = ImageData()
    dora_stop_event = threading.Event()
    gelsight_close_event = threading.Event()

    # 设置信号处理
    signal.signal(signal.SIGINT, signal_handler)
    logger.info("Press Ctrl+C to exit...")

    # 启动线程
    gelsight_thread = threading.Thread(
        target=receive_data_from_gelsight,
        args=(image_data, dora_stop_event, gelsight_close_event),
        daemon=True,  # 设置为守护线程，主线程退出时自动终止

    )
    dora_thread = threading.Thread(
        target=send_data_through_dora,
        args=(image_data, dora_stop_event, gelsight_close_event),
        daemon=True,  # 设置为守护线程，主线程退出时自动终止

    )

    gelsight_thread.start()
    dora_thread.start()

    # 主线程等待
    try:
        while not dora_stop_event.is_set():
            time.sleep(0.1)
    except KeyboardInterrupt:
        # 备用处理（虽然信号处理已注册）
        logger.info("KeyboardInterrupt received. Exiting...")
        dora_stop_event.set()

    # 等待线程结束
    logger.info("Waiting for threads to finish...")
    gelsight_thread.join(timeout=2.0)  # 设置超时时间
    dora_thread.join(timeout=2.0)

    # 确认所有资源已释放
    if gelsight_thread.is_alive():
        logger.warning("GelSight thread is still running after timeout.")
    if dora_thread.is_alive():
        logger.warning("Dora thread is still running after timeout.")

    logger.info("Program exited gracefully.")
