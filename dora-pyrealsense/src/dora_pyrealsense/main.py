"""vive node for Dora.

This module provides a Dora node that sends pyrealsense data, include image, depth.
"""
import logging
import sys
import threading
from dataclasses import dataclass, field

import os
import time

import cv2
import numpy as np
import pyarrow as pa
import pyrealsense2 as rs
from dora import Node

from pa_schema import pa_image_schema as image_schema
from pa_schema import pa_depth_schema as depth_schema

logger = logging.getLogger(__name__)

@dataclass
class ImageData:
    """Stores Image data from Realsense with thread-safe access."""
    _lock: threading.Lock = field(default_factory=threading.Lock)
    _has_data: bool = False
    frame: np.ndarray = field(default_factory=lambda: np.zeros((480, 640, 3), dtype=np.uint8))
    width: int = 640
    height: int = 480
    encoding: str = "rgb8"
    timestamp: int = 0
    serial_number: str = ""
    resolution: list[int] = field(default_factory=lambda: [0, 0])
    focal_length: list[int] = field(default_factory=lambda: [0, 0]) 

    def update_data(
        self,
        serial_number: str, 
        frame: np.ndarray, 
        width: int,
        height: int,
        encoding: str,
        timestamp: int,
        resolution: list[int],
        focal_length: list[int],
    ) -> None:
        """更新数据"""
        with self._lock:
            self.serial_number = serial_number
            self.frame = frame
            self.width = width
            self.height = height
            self.encoding = encoding
            self.timestamp = timestamp
            self.resolution = resolution
            self.focal_length = focal_length
            self._has_data = True

    
    def read_data(self) -> tuple[bool, str, np.ndarray, int, int, str, int, int, list[int], list[int]]:
        """读取Image数据"""
        with self._lock:
            return (
                self._has_data,
                self.serial_number,
                self.frame.copy(),
                self.width,
                self.height,
                self.encoding,
                self.timestamp,
                self.resolution,
                self.focal_length,
            )

@dataclass
class DepthData:
    """Stores Depth data from Realsense with thread-safe access."""
    _lock: threading.Lock = field(default_factory=threading.Lock)
    _has_data: bool = False
    frame: np.ndarray = field(default_factory=lambda: np.zeros((480, 640), dtype=np.uint16))
    width: int = 640
    height: int = 480
    encoding: str = "mono16"
    timestamp: int = 0
    serial_number: str = ""

    def update_data(
        self,
        serial_number: str,
        frame: np.ndarray,
        width: int,
        height: int,
        timestamp: int,
    ) -> None:
        """Update depth data."""
        with self._lock:
            self.serial_number = serial_number
            self.frame = frame
            self.width = width
            self.height = height
            self.timestamp = timestamp
            self._has_data = True

    def read_data(self) -> tuple[bool, str, np.ndarray, int, int, str, int]:
        """Read depth data."""
        with self._lock:
            return (
                self._has_data,
                self.serial_number,
                self.frame.copy(),
                self.width,
                self.height,
                self.encoding,
                self.timestamp,
            )
        

def configure_realsense(
    device_serial: str,
    image_width: int,
    image_height: int,
) -> tuple[rs.pipeline, rs.align, rs.config, rs.context]:
    """Configure and initialize RealSense camera."""
    ctx = rs.context()
    devices = ctx.query_devices()
    
    if devices.size() == 0:
        raise ConnectionError("No realsense camera connected.")
    
    serials = [device.get_info(rs.camera_info.serial_number) for device in devices]
    if device_serial and (device_serial not in serials):
        raise ConnectionError(
            f"Device with serial {device_serial} not found within: {serials}.",
        )
    logger.info(f"Connected RealSense devices: {serials}")
    
    pipeline = rs.pipeline()
    config = rs.config()
    
    if device_serial:
        config.enable_device(device_serial)
    
    config.enable_stream(rs.stream.color, image_width, image_height, rs.format.rgb8, 30)
    config.enable_stream(rs.stream.depth, image_width, image_height, rs.format.z16, 30)
    
    align_to = rs.stream.color
    align = rs.align(align_to)
    
    return pipeline, align, config, ctx


def capture_realsense_data(
    image_data: ImageData,
    depth_data: DepthData,
    dora_stop_event: threading.Event,
    realsense_close_event: threading.Event,
    device_serial: str,
    image_width: int,
    image_height: int,
    flip: str,
    encoding: str,
) -> None:
    """Capture and process RealSense data in a separate thread."""
    try:
        pipeline, align, config, ctx = configure_realsense(device_serial, image_width, image_height)
        profile = pipeline.start(config)
        rgb_profile = profile.get_stream(rs.stream.color)
        depth_profile = profile.get_stream(rs.stream.depth)
        rgb_intr = rgb_profile.as_video_stream_profile().get_intrinsics()
        while not dora_stop_event.is_set():
            frames = pipeline.wait_for_frames()
            aligned_frames = align.process(frames)
            
            aligned_depth_frame = aligned_frames.get_depth_frame()
            color_frame = aligned_frames.get_color_frame()

            if not aligned_depth_frame or not color_frame:
                continue
            
            depth_image = np.asanyarray(aligned_depth_frame.get_data())
            scaled_depth_image = depth_image
            color_frame = np.asanyarray(color_frame.get_data())
            # Apply flip if needed
            if flip == "VERTICAL":
                color_frame = cv2.flip(color_frame, 0)
            elif flip == "HORIZONTAL":
                color_frame = cv2.flip(color_frame, 1)
            elif flip == "BOTH":
                color_frame = cv2.flip(color_frame, -1)
            
            # Apply encoding if needed
            if encoding == "bgr8":
                color_frame = cv2.cvtColor(color_frame, cv2.COLOR_RGB2BGR)
            elif encoding in ["jpeg", "jpg", "jpe", "bmp", "webp", "png"]:
                ret, color_frame = cv2.imencode("." + encoding, color_frame)
                if not ret:
                    logger.error("Error encoding image...")
                    continue

            
            # Update image data
            resolution = [int(rgb_intr.ppx), int(rgb_intr.ppy)]
            focal_length = [int(rgb_intr.fx), int(rgb_intr.fy)]
            timestamp = int(time.time_ns())
            image_data.update_data(
                device_serial,
                color_frame,
                image_width,
                image_height,
                encoding,
                timestamp,
                resolution,
                focal_length,
            )

            # Update depth data
            scaled_depth_image[scaled_depth_image > 5000] = 0
            depth_data.update_data(
                device_serial,
                scaled_depth_image,
                image_width,
                image_height,
                timestamp,
            )
            time.sleep(0.001)
            
    except Exception as e:
        logger.exception("RealSense error: %s", e)
        realsense_close_event.set()
    finally:
        pipeline.stop()
        # realsense_close_event.set()


def send_data_through_dora(
    image_data: ImageData,
    depth_data: DepthData,
    dora_stop_event: threading.Event,
    realsense_close_event: threading.Event,
    ) -> None:
    """Sends image and depth data."""
    node = Node()
    try:
        for event in node:
            if realsense_close_event.is_set():
                dora_stop_event.set()
                break
            
            if event["type"] == "INPUT" and event["id"] == "tick":
                # Read image data

                has_image, sn, frame, width, height, encoding, timestamp, resolution, focal_length  = image_data.read_data()
                # print(f"发送的序列号为:{sn}")
                # Read depth data
                has_depth, d_sn, depth_frame, d_width, d_height, d_encoding, d_timestamp = depth_data.read_data()
                if has_image:
                    # Create image batch

                    image_batch = pa.record_batch(
                        {
                            "serial_number": [sn],
                            "image": [frame.ravel()],
                            "timestamp": [timestamp],
                            "width": [width],
                            "height": [height],
                            "encoding": [encoding],
                        },
                        schema = image_schema,
                    )
                    # cv2.imshow("rgb", frame)
                    # cv2.waitKey(1)  # 刷新显示
                    # image_batch = pa.array(frame.ravel())
                    node.send_output("image", image_batch)
                if has_depth:
                    # Create depth batch
                    depth_batch = pa.record_batch(
                        {
                            "serial_number": [d_sn],
                            "depth": [depth_frame.ravel()],
                            "timestamp": [d_timestamp],
                            "width": [width],
                            "height": [height],
                        },
                        schema = depth_schema,
                    )

                    # cv2.imshow("depth", depth_frame)
                    # cv2.waitKey(1)  # 刷新显示
                    node.send_output("depth", depth_batch)
                
                time.sleep(0.001)
            
            elif event["type"] == "STOP":
                dora_stop_event.set()
                break
    except Exception as e:
        logger.exception("Dora error: %s", e)
    

def main() -> None:
    """Main entry point for the RealSense node."""
    logging.basicConfig(level=logging.INFO)
    
    # Get environment variables
    flip = os.getenv("FLIP", "")
    device_serial = os.getenv("DEVICE_SERIAL", "")
    image_height = int(os.getenv("IMAGE_HEIGHT", "480"))
    image_width = int(os.getenv("IMAGE_WIDTH", "640"))
    encoding = os.getenv("ENCODING", "rgb8")
    
    # Initialize data classes
    image_data = ImageData()
    depth_data = DepthData()
    dora_stop_event = threading.Event()
    realsense_close_event = threading.Event()
    # Start threads
    realsense_thread = threading.Thread(
        target=capture_realsense_data,
        args=(image_data, depth_data, dora_stop_event, realsense_close_event, 
            device_serial, image_width, image_height, flip, encoding),
    )
    dora_thread = threading.Thread(
        target=send_data_through_dora,
        args=(image_data, depth_data, dora_stop_event, realsense_close_event),
    )
    
    realsense_thread.start()
    dora_thread.start()
    
    realsense_thread.join()
    dora_thread.join()

if __name__ == "__main__":
    main()