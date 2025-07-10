# """TODO: Add docstring."""
import logging
import os
import threading
import time
from dataclasses import dataclass, field

import cv2
import numpy as np
import pyarrow as pa
from dora import Node
from typing_extensions import Self

from dora_fisheye_camera.pa_schema import pa_image_schema as image_schema

logger = logging.getLogger(__name__)

@dataclass
class FisheyeImageData:
    """Stores Fisheye Image data from Fisheye Camera with thread-safe access."""
    _lock: threading.Lock = field(default_factory=threading.Lock)
    _has_data: bool = False
    frame: np.ndarray = field(default_factory=lambda: np.zeros((480, 640, 3), dtype=np.uint8))
    width: int = 640
    height: int = 480
    encoding: str = "rgb8"
    timestamp: int = 0
    camera_id: str = ""
    def updata_data(
        self: Self,
        camera_id: str,
        frame: np.ndarray,
        width: int,
        height: int,
        encoding: str,
        timestamp: int,
    ) -> None:
        """Update Fisheye Image data."""
        with self._lock:
            self.camera_id = camera_id
            self.frame = frame
            self.width =width
            self.height = height
            self.encoding = encoding
            self.timestamp = timestamp
            self._has_data = True

    def read_data(self: Self) -> tuple[bool, np.ndarray, int, int, str, int]:
        """Read Fisheye Image data"""
        with self._lock:
            return (
                self._has_data,
                self.camera_id,
                self.frame.copy(),
                self.width,
                self.height,
                self.encoding,
                self.timestamp,
            )
def configure_fisheye_camera(
    camera_id: str,
    image_width: int,
    image_height: int,
    ) -> cv2.VideoCapture :
    "Configure and initialize fisheye camera"
    cap = cv2.VideoCapture(camera_id)
    if not cap.isOpened():
        raise ConnectionError(f"无法打开相机设备 {camera_id}")
    # 获取相机信息
    backend = cap.getBackendName()
    logger.info(f"已连接相机 (ID: {camera_id}, 后端: {backend})")
    # 应用配置
    try:
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, image_width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, image_height)
        return cap
    except Exception as e:
        cap.release()
        raise ConnectionError(f"相机配置失败: {str(e)}")

def capture_fisheye_camera_data(
    image_data: FisheyeImageData,
    dora_stop_event: threading.Event,
    fisheye_camera_close_event: threading.Event,
    camera_id: str,
    image_width: int,
    image_height: int,
    flip: str,
    encoding: str,
    ) -> None:
    """Capture and process fisheye camera data in a separate thread."""

    try:
        cap = configure_fisheye_camera(camera_id, image_width, image_height)
        while not dora_stop_event.is_set():
            # 捕获一帧图像
            ret, frame = cap.read()
            if not ret:
                logger.warning("无法获取图像帧，继续尝试...")
                time.sleep(0.1)
                continue

            # 应用图像翻转
            if flip == "VERTICAL":
                frame = cv2.flip(frame, 0)
            elif flip == "HORIZONTAL":
                frame = cv2.flip(frame, 1)
            elif flip == "BOTH":
                frame = cv2.flip(frame, -1)

            if encoding == "bgr8":
                # BGR格式 (OpenCV默认格式)
                pass
            elif encoding in ["jpeg", "jpg", "jpe", "bmp", "webp", "png"]:
                # 编码为指定格式
                ret, encoded_frame = cv2.imencode("." + encoding, frame)
                if not ret:
                    logger.error(f"图像编码失败: {encoding}")
                    continue
             # 更新图像数据
            timestamp = int(time.time_ns())
            image_data.updata_data(
                camera_id,
                frame,
                image_width,
                image_height,
                encoding,
                timestamp,
            )
    except Exception as e:
        logger.exception(f"鱼眼相机错误: {e}")
        fisheye_camera_close_event.set()
    finally:
        # 确保释放相机资源
        if 'cap' in locals() and cap.isOpened():
            cap.release()
        logger.info(f"鱼眼相机 (ID:{camera_id}) 已关闭")

def send_data_through_dora(
    image_data: FisheyeImageData,
    dora_stop_event: threading.Event,
    fisheye_camera_close_event: threading.Event,
    ) -> None:
    """Sends image and depth data."""

    node = Node()
    try:
        for event in node:
            if fisheye_camera_close_event.is_set():
                dora_stop_event.set()
                break
            if event["type"] == "INPUT" and event["id"] == "tick":
                has_data, camera_id, frame, width, height, encoding, timestamp = image_data.read_data()
                if has_data:
                    image_batch = pa.record_batch(
                        {
                            "camera_id": [camera_id],
                            "image": [frame.ravel()],
                            "timestamp": [timestamp],
                            "width": [width],
                            "height": [height],
                            "encoding": [encoding],
                        },
                        schema = image_schema,
                    )
                    node.send_output("image", image_batch)

                time.sleep(0.01)

            elif event["type"] == "STOP":
                dora_stop_event.set()
                break
    except Exception as e:
        logger.exception("Dora error: %s", e)

def main()-> None:
    """Main entry point"""
    logging.basicConfig(level=logging.INFO)
    flip = os.getenv("FLIP", "")
    camera_id = os.getenv("CAMERA_ID", "")
    image_height = int(os.getenv("IMAGE_HEIGHT", "480"))
    image_width = int(os.getenv("IMAGE_WIDTH", "640"))
    encoding = os.getenv("ENCODING", "rgb8")

    # Initialize data classes
    image_data = FisheyeImageData()
    dora_stop_event = threading.Event()
    fisheye_camera_close_event = threading.Event()
    # Start threads
    fisheye_camera_thread = threading.Thread(
        target=capture_fisheye_camera_data,
        args=(image_data,  dora_stop_event, fisheye_camera_close_event,
              camera_id, image_width, image_height, flip, encoding),
        daemon=True,

    )

    dora_thread = threading.Thread(
        target=send_data_through_dora,
        args=(image_data, dora_stop_event, fisheye_camera_close_event),
        daemon=True,

    )

    fisheye_camera_thread.start()
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
    fisheye_camera_thread.join(timeout=2.0)  # 设置超时时间
    dora_thread.join(timeout=2.0)

    # 确认所有资源已释放
    if fisheye_camera_thread.is_alive():
        logger.warning("fisheye thread is still running after timeout.")
    if dora_thread.is_alive():
        logger.warning("Dora thread is still running after timeout.")

    logger.info("Program exited gracefully.")
if __name__ == "__main__":
    main()
