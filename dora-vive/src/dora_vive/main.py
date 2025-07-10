"""vive node for Dora.

This module provides a Dora node that sends vive data, include imu, pose.
"""

import logging
import signal
import sys
import threading
import time
from dataclasses import dataclass, field

import pyarrow as pa
import pysurvive
from dora import Node
from typing_extensions import Self

from dora_vive.pa_schema import pa_imu_schema as imu_schema
from dora_vive.pa_schema import pa_pose_schema as pose_schema

logger = logging.getLogger(__name__)


@dataclass
class IMUData:
    """Stores IMU data from Vive trackers with thread-safe access."""

    _lock: threading.Lock = field(default_factory=threading.Lock)
    _has_data: bool = False
    acc: list[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])
    gyro: list[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])
    mag: list[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])
    serial_number: str = ""

    def update_data(
        self: Self,
        serial_number: str,
        acc: list[float],
        gyro: list[float],
        mag: list[float],
    ) -> None:
        """Update IMU data."""
        with self._lock:
            self.serial_number = serial_number
            self.acc = acc
            self.gyro = gyro
            self.mag = mag
            self._has_data = True

    def read_data(self: Self) -> tuple[bool, str, list[float], list[float], list[float]]:
        """Read IMU data."""
        with self._lock:
            return (
                self._has_data,
                self.serial_number,
                self.acc,
                self.gyro,
                self.mag,
            )


@dataclass
class PoseData:
    """Stores Pose data from Vive trackers with thread-safe access."""

    _lock: threading.Lock = field(default_factory=threading.Lock)
    _has_data: bool = False
    position: list[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])
    rotation: list[float] = field(default_factory=lambda: [1.0, 0.0, 0.0, 0.0])
    serial_number: str = ""

    def update_data(
        self: Self,
        serial_number: str,
        position: list[float],
        rotation: list[float],
    ) -> None:
        """Update pose data."""
        with self._lock:
            self.position = position
            self.rotation = rotation
            self.serial_number = serial_number
            self._has_data = True

    def read_data(self: Self) -> tuple[bool, str, list[float], list[float]]:
        """Read pose data."""
        with self._lock:
            return self._has_data, self.serial_number, self.position, self.rotation


def make_imu_func(imu_data: IMUData):  # noqa: ANN201
    """Returns a closure that handles IMU callbacks from pysurvive."""

    def imu_func(ctx, _mode, accelgyro: list[float], _timecode, _dev_id) -> None:  # noqa: ANN001
        acc = accelgyro[:3]
        gyro = accelgyro[3:6]
        mag = accelgyro[6:]
        serial_number = ctx.contents.serial_number.decode("utf-8")
        imu_data.update_data(serial_number, acc, gyro, mag)

    return imu_func


def make_pose_func(pose_data: PoseData):  # noqa: ANN201
    """Returns a closure that handles Pose callbacks from pysurvive."""

    def pose_func(ctx, _timecode, pose: list[float]) -> None:  # noqa: ANN001
        position = pose[:3]
        rotation = pose[3:]
        serial_number = ctx.contents.serial_number.decode("utf-8")
        pose_data.update_data(serial_number, position, rotation)

    return pose_func


def receive_data_from_survive(
    imu_data: IMUData,
    pose_data: PoseData,
    dora_stop_event: threading.Event,
    survive_close_event: threading.Event,
) -> None:
    """Polls pysurvive context for IMU and Pose data."""
    ctx = pysurvive.init(sys.argv)
    if ctx is None:
        logger.error("Vive device not connected.")
        survive_close_event.set()
        return

    try:
        pysurvive.install_imu_fn(ctx, make_imu_func(imu_data))
        pysurvive.install_pose_fn(ctx, make_pose_func(pose_data))

        while not dora_stop_event.is_set():
            if pysurvive.survive_poll(ctx) != 0:
                logger.error("Error polling from pysurvive.")
                survive_close_event.set()
                break
            time.sleep(0.001)
    except Exception as e:
        logger.exception("Survive error: %s", e)
    finally:
        # 确保资源释放
        logger.info("Closing pysurvive context...")
        pysurvive.survive_close(ctx)
        survive_close_event.set()


def send_data_through_dora(
    imu_data: IMUData,
    pose_data: PoseData,
    dora_stop_event: threading.Event,
    survive_close_event: threading.Event,
) -> None:
    """Sends IMU and Pose data via Dora outputs."""
    node = Node()
    try:
        for event in node:
            if survive_close_event.is_set():
                dora_stop_event.set()
                break
            if event["type"] == "INPUT" and event["id"] == "tick":
                has_imu, sn_imu, acc, gyro, mag = imu_data.read_data()
                has_pose, sn_pose, pos, rot = pose_data.read_data()
                if has_imu:
                    imu_batch = pa.record_batch(
                        {
                            "serial_number": [sn_imu],
                            "acc": [acc],
                            "gyro": [gyro],
                            "mag": [mag],
                        },
                        schema=imu_schema,
                    )
                    node.send_output("imu", imu_batch)
                if has_pose:
                    # print(f"pos:{pos}")
                    pose_batch = pa.record_batch(
                        {
                            "serial_number": [sn_pose],
                            "position": [pos],
                            "rotation": [rot],
                        },
                        schema=pose_schema,
                    )
                    node.send_output("pose", pose_batch)

                time.sleep(0.001)

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
    imu_data = IMUData()
    pose_data = PoseData()
    dora_stop_event = threading.Event()
    survive_close_event = threading.Event()

    # 设置信号处理
    signal.signal(signal.SIGINT, signal_handler)
    logger.info("Press Ctrl+C to exit...")

    # 启动线程
    survive_thread = threading.Thread(
        target=receive_data_from_survive,
        args=(imu_data, pose_data, dora_stop_event, survive_close_event),
        daemon=True,  # 设置为守护线程，主线程退出时自动终止
    )
    dora_thread = threading.Thread(
        target=send_data_through_dora,
        args=(imu_data, pose_data, dora_stop_event, survive_close_event),
        daemon=True,
    )

    survive_thread.start()
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
    survive_thread.join(timeout=2.0)  # 设置超时时间
    dora_thread.join(timeout=2.0)

    # 确认所有资源已释放
    if survive_thread.is_alive():
        logger.warning("Survive thread is still running after timeout.")
    if dora_thread.is_alive():
        logger.warning("Dora thread is still running after timeout.")

    logger.info("Program exited gracefully.")
