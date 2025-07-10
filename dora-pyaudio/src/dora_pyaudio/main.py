import logging
import os
import threading
import time
from dataclasses import dataclass, field

import numpy as np
import pyarrow as pa
import pyaudio
from dora import Node
from typing_extensions import Self

from dora_pyaudio.pa_schema import pa_audio_schema as audio_schema

logger = logging.getLogger(__name__)

# 配置参数
FORMAT = pyaudio.paInt16  # 16-bit PCM
CHANNELS = int(os.getenv("CHANNELS", "1"))
RATE = int(os.getenv("RATE", "44100"))# 采样率
CHUNK = int(os.getenv("CHUNK", "1024")) # 每次读取的帧数


@dataclass
class AudioData:
    """Stores audio data with thread-safe access."""

    _lock: threading.Lock = field(default_factory=threading.Lock)
    _has_data: bool = False
    data: bytes = b''
    sample_rate: int = RATE
    channels: int = CHANNELS
    format: int = FORMAT
    chunk_size: int = CHUNK
    timestamp: int = 0
    def update_data(self: Self, data: bytes, timestamp: int) -> None:
        """Update audio data."""
        with self._lock:
            self.data = data
            self._has_data = True
            self.timestamp = timestamp
    def read_data(self: Self) -> tuple[bool, bytes, int, int, int, int, int]:
        """Read audio data."""
        with self._lock:
            return (
                self._has_data,
                self.data,
                self.sample_rate,
                self.channels,
                self.format,
                self.chunk_size,
                self.timestamp
            )


def capture_audio_data(
    audio_data: AudioData,
    audio_close_event: threading.Event,
) -> None:
    """Records audio from microphone."""
    # 初始化PyAudio
    p = pyaudio.PyAudio()

    try:
        # 打开音频流
        stream = p.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=RATE,
            input=True,
            frames_per_buffer=CHUNK
        )

        frames = []
        while not audio_close_event.is_set():
            # 读取音频数据
            data = stream.read(CHUNK, exception_on_overflow=False)
            frames.append(data)
            timestamp = time.time_ns()
            # 更新音频数据
            audio_data.update_data(data, timestamp)

    except Exception as e:
        logger.exception("audio error: %s", e)
        audio_close_event.set()
    finally:
        # 停止并关闭流
        if 'stream' in locals():
            stream.stop_stream()
            stream.close()
        p.terminate()


def send_audio_through_dora(
    audio_data: AudioData,
    dora_stop_event: threading.Event,
    audio_close_event: threading.Event,
) -> None:
    """Sends audio data via Dora outputs."""
    node = Node()
    try:
        for event in node:
            if  audio_close_event.is_set():
                # 发送录制完成状态
                break

            if event["type"] == "INPUT" and event["id"] == "tick":
                has_data, data, sample_rate, channels, format, chunk_size, timestamp = audio_data.read_data()
                if has_data:
                    # 将音频数据发送出去
                    audio_array = np.frombuffer(data, dtype=np.int16)
                    audio_batch = pa.record_batch(
                        {
                            "audio_data": [audio_array],
                            "timestamp": [timestamp],
                            "sample_rate": [sample_rate],
                            "channels": [channels],
                            "format": [format],
                            "chunk_size": [chunk_size],

                        },
                        schema = audio_schema,
                    )
                    node.send_output("audio_data", audio_batch)

                time.sleep(0.001)  # 避免CPU使用率过高

            elif event["type"] == "STOP":
                dora_stop_event.set()
                break

    except Exception as e:
        logger.exception(f"Dora发送过程中发生错误: {e}")
    finally:
        # 标记线程停止
        dora_stop_event.set()




if __name__ == "__main__":
    # 配置日志
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # 创建事件和数据存储
    audio_data = AudioData()
    dora_stop_event = threading.Event()
    audio_close_event = threading.Event()



    # 启动线程
    audio_thread = threading.Thread(
        target=capture_audio_data,
        args=(audio_data,  audio_close_event),
    )
    dora_thread = threading.Thread(
        target=send_audio_through_dora,
        args=(audio_data, dora_stop_event, audio_close_event),
    )

    audio_thread.start()
    dora_thread.start()

    audio_thread.join()
    dora_thread.join()
    # 主线程等待
    try:
        while not dora_stop_event.is_set():
            time.sleep(0.1)
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt received. Exiting...")
        dora_stop_event.set()

    # 等待线程结束
    logger.info("Waiting for threads to finish...")
    audio_thread.join(timeout=2.0)
    dora_thread.join(timeout=2.0)

    # 确认所有资源已释放
    if audio_thread.is_alive():
        logger.warning("录音线程在超时后仍在运行.")
    if dora_thread.is_alive():
        logger.warning("Dora线程在超时后仍在运行.")

    logger.info("音频采集程序已退出.")
