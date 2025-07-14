import time

from xensesdk.xenseInterface.XenseSensor import Sensor

if __name__ == '__main__':
    sensor  = Sensor.create("OP00000F", config_path="/home/linux/xensesdk/deprecated_example/config/OP00000F")

    sensor.startSaveSensorInfo(r"/home/linux/xensesdk/xensesdk/examples/data", [Sensor.OutputType.Difference])
    time.sleep(5)
    sensor.stopSaveSensorInfo()
    print("save ok")

    sensor.release()
