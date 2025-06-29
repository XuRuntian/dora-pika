#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
获取pika-sense的相机图像以及joint state 并发送出去
"""
from dora import Node
import numpy as np
import pyarrow as pa
import h5py

import time
import cv2
import numpy as np
from pika import sense

def main():
    # 创建 Sense 对象并连接
    print("正在连接 Pika Sense 设备...")
    my_sense = sense('/dev/ttyUSB81')  # 请根据实际情况修改串口路径,默认参数为：/dev/ttyUSB0
    
    if not my_sense.connect():
        print("连接 Pika Sense 设备失败，请检查设备连接和串口路径")
        return
    
    print("成功连接到 Pika Sense 设备")
    # 设置相机参数
    my_sense.set_camera_param(640, 480, 30)
    # 设置 Fisheye 相机索引
    my_sense.set_fisheye_camera_index(81)
    # 设置 Realsense 相机序列号
    my_sense.set_realsense_serial_number('230322270988')
    node = Node()
    for event in node:
        if event["type"] == "INPUT":
            # if event["id"] == 

            try:
                # 获取编码器数据
                encoder_data = my_sense.get_encoder_data()
                # print("\n--- 编码器数据 ---")
                # print(f"角度: {encoder_data['angle']:.2f}°")
                # print(f"弧度: {encoder_data['rad']:.2f} rad")
                # 获取命令状态
                # command_state = my_sense.get_command_state()
                # print(f"\n命令状态: {command_state}")
                node.send_output("encoder_data_angle", pa.array(encoder_data['angle']:.2f))
                node.send_output("encoder_data_angle", pa.array(encoder_data['rad']:.2f))

            except Exception as e:
                print(f"获取编码器数据异常: {e}") 
            
            # 尝试获取鱼眼相机图像
            try:
                fisheye_camera = my_sense.get_fisheye_camera()
                if fisheye_camera:
                    success, frame = fisheye_camera.get_frame()
                    if success:
                        print("\n成功获取鱼眼相机图像")
                        # 发送图像
                        node.send_output("fisheye_camera", pa.array(frame), {"encoding": "numpy.ndarray"})
            except Exception as e:
                print(f"获取鱼眼相机图像异常: {e}")
        
            # 尝试获取 RealSense 相机图像
            try:
                realsense_camera = my_sense.get_realsense_camera()
                if realsense_camera:
                    success, color_frame = realsense_camera.get_color_frame()
                    # print("D405相机参数信息：",realsense_camera.get_camera_info())
                    if success:
                        node.send_output("realsense_camera_color_frame", pa.array(color_frame))

                    success, depth_frame = realsense_camera.get_depth_frame()
                    if success:
                        # 将深度图像归一化以便显示
                        depth_colormap = cv2.applyColorMap(cv2.convertScaleAbs(depth_frame, alpha=0.03), cv2.COLORMAP_JET)
                        # 显示图像
                        node.send_output("realsense_camera_depth_frame", pa.array(depth_colormap))
            except Exception as e:
                print(f"获取 RealSense 相机图像异常: {e}")



if __name__ == "__main__":
    main()