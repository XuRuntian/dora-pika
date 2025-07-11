"""TODO: Add docstring."""

import logging
import os
import threading
import time
from dataclasses import dataclass, field

import numpy as np
import pyarrow as pa
from dora import Node
from pika import sense
from typing_extensions import Self

from dora_pika_gripper.pa_schema import pa_pika_gripper_schema as pika_gripper_schema

logger = logging.getLogger(__name__)


@dataclass
class PikaData:
    """线程安全的 Pika 数据存储"""
    _lock: threading.Lock = field(default_factory=threading.Lock)
    angle: float = 0.0
    rad: float = 0.0
    command_state: str = ""
    has_data: bool = False
    timestamp: int = 0
    def update_data(self: Self, angle: float, rad: float, command_state: int, timestamp: int) -> None:
        """更新数据"""
        with self._lock:
            self.angle = angle
            self.rad = rad
            self.command_state = command_state
            self.has_data = True
            self.timestamp = timestamp
    def read_data(self: Self) -> tuple[bool, float, float, int, int]:
        """获取数据"""
        with self._lock:
            return (
                self.has_data,
                self.angle,
                self.rad,
                self.command_state,
                self.timestamp
            )

def config_pika(serial_path: str) -> sense:
    """读取 Pika 设备数据的线程"""
    logger.info(f"连接设备: {serial_path}")
    pika = sense(serial_path)
    if not pika.connect():
        logger.error("连接失败！")
        pika_stop_event.set()
        return None
    return pika

def pika_reader(pika_data: PikaData, pika_stop_event: threading, serial_path: str) -> None:
    pika = config_pika(serial_path)
    try:
        while not pika_stop_event.is_set():
            # 读取编码器和命令状态
            encoder = pika.get_encoder_data()
            state = pika.get_command_state()
            timestamp = time.time_ns()
            pika_data.update_data(encoder["angle"], encoder["rad"], state, timestamp)
            time.sleep(0.001)  # 10ms 间隔
    except Exception as e:
        logger.error(f"读取失败: {e}")
        pika_stop_event.set()
    finally:
        pika.disconnect()  # 断开连接
        pika_stop_event.set()


def dora_sender(pika_data: PikaData, pika_stop_event: threading, dora_stop_event: threading) -> None:
    """通过 Dora 发送数据的线程"""
    node = Node()
    try:
        for event in node:
            if  pika_stop_event.is_set():
                break
            if event["type"] == "INPUT" and event["id"] == "tick":
                has_data, angle, rad, state, timestamp = pika_data.read_data()
                print
                if has_data:
                    # 构建并发送数据
                    batch = pa.record_batch(
                        {
                            "angle" : [np.float16(angle)],
                            "rad" : [np.float16(rad)],
                            "state": [state],
                            "timestamp": [timestamp],
                        },
                        schema=pika_gripper_schema
                    )
                    node.send_output("encoder_data", batch)
                time.sleep(0.001)  # 避免CPU使用率过高
            elif event["type"] == "STOP":
                dora_stop_event.set()
                break

    except Exception as e:
        logger.exception(f"Dora发送过程中发生错误: {e}")
        pika_stop_event.set()
    finally:
        # 标记线程停止
        dora_stop_event.set()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    serial_path = os.getenv("SERIAL_PATH", "/dev/ttyUSB81")  # 设备串口

    # 初始化数据和事件
    pika_data = PikaData()
    dora_stop_event = threading.Event()
    pika_stop_event = threading.Event()


    # 启动线程
    reader_thread = threading.Thread(
        target=pika_reader,
        args=(pika_data, pika_stop_event, serial_path),
        daemon=True
    )
    sender_thread = threading.Thread(
        target=dora_sender,
        args=(pika_data, pika_stop_event, dora_stop_event),
        daemon=True
    )
    reader_thread.start()
    sender_thread.start()

    # 等待退出
    try:
        while not dora_stop_event.is_set():
            time.sleep(0.1)
    finally:
        # 等待线程结束
        reader_thread.join(2)
        sender_thread.join(2)
        logger.info("程序退出")
