import logging
import os
import threading
import time
from dataclasses import dataclass, field
from typing import Optional, tuple

import cv2
import numpy as np
import pyarrow as pa
from dora import Node
from typing_extensions import Self

from dora_xense.pa_schema import pa_xense_schema as xense_schema
from xensesdk.xenseInterface.XenseSensor import Sensor

logger = logging.getLogger(__name__)


@dataclass
class XenseData:
    """"""
    _lock: threading.Lock = field(default_factory=threading.Lock)
    _has_data: bool = False

    # 图像数据
    rectify_img: Optional[np.ndarray] = field(default_factory=lambda: np.zeros((400, 700, 3), dtype=np.uint8))
    bgr_img: Optional[np.ndarray] = field(default_factory=lambda: np.zeros((400, 700, 3), dtype=np.uint8))
    # 深度数据
    depth: Optional[np.ndarray] = field(default_factory=lambda: np.zeros((400, 700), dtype=np.float32))
    # 力数据
    force_resultant: Optional[np.ndarray] = field(default_factory=lambda: np.zeros((6, ), dtype=np.double))
    # 3D网格流数据
    mesh3d_flow: Optional[np.ndarray] = field(default_factory=lambda: np.zeros((35, 20, 3), dtype=np.double))
    timestamp: int = 0

    def update_data(
        self: Self,
        rectify_img: np.ndarray,
        depth: np.ndarray,
        force_resultant: np.ndarray,
        mesh3d_flow: np.ndarray,
        timestamp: int,

    ) -> None:
        """更新传感器数据"""
        with self._lock:
            self.rectify_img = rectify_img
            self.depth = depth
            self.force_resultant = force_resultant
            self.mesh3d_flow = mesh3d_flow
            self.timestamp = timestamp

            # 转换图像格式为BGR
            if rectify_img.shape[2] == 3:
                self.bgr_img = cv2.cvtColor(rectify_img, cv2.COLOR_RGB2BGR)
            else:
                self.bgr_img = rectify_img

            self._has_data = True

    def read_data(self: Self) -> tuple[bool, dict, np.ndarray, np.ndarray, np.ndarray, np.ndarray, int]:
        """读取传感器数据"""
        with self._lock:
            return (
                self._has_data,
                self.bgr_img.copy() if self.bgr_img is not None else None,
                self.depth.copy() if self.depth is not None else None,
                self.force_resultant.copy() if self.force_resultant is not None else None,
                self.mesh3d_flow.copy() if self.mesh3d_flow is not None else None,
                self.timestamp,
            )


def initialize_sensor(sensor_id: str, use_gpu: bool, rectify_size: tuple) -> Optional[Sensor]:
    """初始化Xense传感器"""
    try:
        sensor = Sensor.create(
            cam_id=sensor_id,
            use_gpu=use_gpu,
            rectify_size=rectify_size,
            check_serial=False
        )
        logger.info(f"成功初始化Xense传感器，ID: {sensor_id}")
        return sensor
    except Exception as e:
        logger.error(f"传感器初始化失败: {str(e)}")
        return None


def receive_data_from_xense(
    xense_data: XenseData,
    config: dict,
    dora_stop_event: threading.Event,
    sensor_close_event: threading.Event
) -> None:
    """从Xense传感器接收数据的线程函数"""
    sensor_id = str(config["sensor_id"])
    use_gpu = str(config["use_gpu"]).lower() == "true"
    rectify_size = tuple(map(int, str(config["rectify_size"]).strip("[]").split(",")))

    sensor = initialize_sensor(sensor_id, use_gpu, rectify_size)
    if not sensor:
        sensor_close_event.set()
        return

    try:
        while not dora_stop_event.is_set():
            try:
                # 获取传感器数据
                rectify_img, depth, force_resultant, mesh3d_flow = sensor.selectSensorInfo(
                    Sensor.OutputType.Rectify,
                    Sensor.OutputType.Depth,
                    Sensor.OutputType.ForceResultant,
                    Sensor.OutputType.Mesh3DFlow
                )
            except Exception as e:
                logger.error(f"传感器数据获取错误: {str(e)}")
                time.sleep(0.1)  # 错误时延长休眠时间

            # 确保数据有效
            if rectify_img is not None and depth is not None:
                # 确保数据连续
                rectify_img = np.ascontiguousarray(rectify_img)
                depth = np.ascontiguousarray(depth)
                force_resultant = np.ascontiguousarray(force_resultant)
                mesh3d_flow = np.ascontiguousarray(mesh3d_flow)
                timestamp = int(time.time_ns())
                # 更新数据
                xense_data.update_data(
                    rectify_img, depth, force_resultant, mesh3d_flow, timestamp
                )
            else:
                time.sleep(0.01)  # 无数据时短暂休眠



    except Exception as e:
        logger.exception(f"传感器数据接收线程异常: {str(e)}")
        sensor_close_event.set()
    finally:
        # 释放资源
        if sensor:
            sensor.release()
            logger.info("传感器资源已释放")
        sensor_close_event.set()


def send_data_through_dora(
    xense_data: XenseData,
    dora_stop_event: threading.Event,
    sensor_close_event: threading.Event
) -> None:
    """通过Dora发送数据的线程函数"""
    node = Node()
    try:
        for event in node:
            # 检查传感器是否已关闭
            if sensor_close_event.is_set():
                dora_stop_event.set()
                break

            # 处理Dora输入事件
            if event["type"] == "INPUT" and event["id"] == "tick":
                has_data, bgr_img, depth, force, mesh, timestamp = xense_data.read_data()

                if has_data:
                    image_batch = pa.record_batch(
                        {
                            "image": [bgr_img.ravel()],
                            "depth": [depth.ravel()],
                            "force": [force.ravel()],
                            "mesh" : [mesh.ravel()],
                            "timestamp": [timestamp]
                        },
                        schema = xense_schema
                    )
                    node.send_output("xense_data", image_batch)

                time.sleep(0.001)  # 控制发送频率

            elif event["type"] == "STOP":
                dora_stop_event.set()
                break

    except Exception as e:
        logger.exception(f"Dora数据发送线程异常: {str(e)}")
        dora_stop_event.set()


def main() -> None:
    """主函数，启动传感器节点"""
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # 传感器配置
    config = {
        "sensor_id": os.getenv("sensor_id", ""),
        "use_gpu": os.getenv("use_gpu", ""),
        "rectify_size": os.getenv("rectify_size", "")
    }

    # 初始化数据存储类
    xense_data = XenseData()
    dora_stop_event = threading.Event()
    sensor_close_event = threading.Event()

    # 启动线程
    sensor_thread = threading.Thread(
        target=receive_data_from_xense,
        args=(xense_data, config, dora_stop_event, sensor_close_event),
        daemon=True
    )
    dora_thread = threading.Thread(
        target=send_data_through_dora,
        args=(xense_data, dora_stop_event, sensor_close_event),
        daemon=True
    )

    try:
        logger.info("Xense传感器节点启动中...")
        sensor_thread.start()
        dora_thread.start()

        # 等待线程结束
        sensor_thread.join()
        dora_thread.join()

    except KeyboardInterrupt:
        logger.info("接收到中断信号，正在关闭传感器节点...")
        dora_stop_event.set()
    finally:
        logger.info("Xense传感器节点已停止")


if __name__ == "__main__":
    main()
