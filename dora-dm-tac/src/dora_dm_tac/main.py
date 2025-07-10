import logging
import os
import threading
import time
from dataclasses import dataclass, field

import numpy as np
import pyarrow as pa
from dmrobotics import Sensor
from dora import Node
from pa_shema import pa_sensor_schema as sensor_schema
from typing_extensions import Self

logger = logging.getLogger(__name__)

@dataclass
class SensorData:
    """"""
    _lock: threading.Lock = field(default_factory=threading.Lock)
    _has_data: bool = False
    img: np.ndarray = field(default_factory=lambda: np.zeros((240, 320), dtype=np.uint8))
    shear: np.ndarray = field(default_factory=lambda: np.zeros((240, 320, 2), dtype=np.float32))
    depth: np.ndarray = field(default_factory=lambda: np.zeros((240, 320), dtype=np.float32))
    deformation: np.ndarray = field(default_factory=lambda: np.zeros((240, 320, 2), dtype=np.float32))
    timestamp: int = 0
    serial_number: str = ""

    def update_data(
        self: Self,
        serial_number:str,
        img: np.ndarray,
        shear: np.ndarray,
        depth: np.ndarray,
        deformation: np.ndarray,
        timestamp: int,
    ) -> None:
        """更新数据"""
        with self._lock:
            self.serial_number = serial_number
            self.img = img
            self.shear = shear
            self.depth = depth
            self.deformation = deformation
            self.timestamp = timestamp
            self._has_data = True

    def read_data(self: Self) -> tuple[bool, str, np.ndarray, np.ndarray, np.ndarray, int]:
        with self._lock:
            return (
                self._has_data,
                self.serial_number,
                self.img,
                self.shear,
                self.depth,
                self.deformation,
                self.timestamp,
            )
def configure_sensor(
    serial_number: str,
    ) -> Sensor:
    try:
        sensor = Sensor(serial_number)
    except Exception as e:
        sensor.disconnect()
        print(f"触觉传感器配置失败{str(e)}")
    return sensor

def capture_sensor_data(
    sensor_data:SensorData,
    dora_stop_event: threading.Event,
    sensor_close_event:threading.Event,
    serial_number: str,
    ) -> None:
    sensor = None  # 初始化为 None
    try:
        sensor = configure_sensor(serial_number)
        while not dora_stop_event.is_set():
            img = sensor.getRawImage()
            shear = sensor.getShear()
            deformation = sensor.getDeformation2D()
            depth = sensor.getDepth() # output the deformed depth

            timestamp = int(time.time_ns())
            sensor_data.update_data(
                serial_number,
                img,
                shear,
                depth,
                deformation,
                timestamp,
            )

    except Exception as e:
        print(f"触觉传感器错误: {e}")

        sensor_close_event.set()

    finally:
        if sensor is not None:
            print("关闭传感器")
            sensor.disconnect()

def send_data_through_dora(
    sensor_data: SensorData,
    dora_stop_event: threading.Event,
    sensor_close_event: threading.Event,
    ) -> None:
    node = Node()
    try:
        for event in node:
            if sensor_close_event.is_set():
                dora_stop_event.set()
                print("停止发送了")
                break
            if event["type"] == "INPUT" and event["id"] == "tick":
                has_data, serial_number, img, shear, depth, deformation, timestamp =  sensor_data.read_data()
                if  has_data:
                    sensor_batch = pa.record_batch(
                        {
                            "serial_number": [serial_number],
                            "img": [img.ravel()],
                            "shear": [shear.ravel()],
                            "depth": [depth.ravel()],
                            "deformation": [deformation.ravel()],
                            "timestamp": [timestamp],
                        },
                        schema = sensor_schema,
                    )
                    node.send_output("touch_sensor_data", sensor_batch)
                time.sleep(0.001)
            elif event["type"] == "STOP":
                dora_stop_event.set()
                break
    except Exception as e:
        logger.exception("Dora error: %s", e)
def main()-> None:
    """Main entry point"""
    logging.basicConfig(level=logging.INFO)
    serial_number = os.getenv("DEVICE_SERIAL", "")
    sensor_data = SensorData()
    dora_stop_event = threading.Event()
    sensor_close_event = threading.Event()
    sensor_thread = threading.Thread(
        target=capture_sensor_data,
        args=(sensor_data, dora_stop_event, sensor_close_event, serial_number),
         daemon=True,
    )

    dora_thread = threading.Thread(
        target=send_data_through_dora,
        args=(sensor_data, dora_stop_event, sensor_close_event),
         daemon=True,
    )
    dora_thread.start()
    sensor_thread.start()
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
    sensor_thread.join(timeout=2.0)  # 设置超时时间
    dora_thread.join(timeout=2.0)

    # 确认所有资源已释放
    if sensor_thread.is_alive():
        logger.warning("dm_tac thread is still running after timeout.")
    if dora_thread.is_alive():
        logger.warning("Dora thread is still running after timeout.")

    logger.info("Program exited gracefully.")
if __name__ == "__main__":
    main()
