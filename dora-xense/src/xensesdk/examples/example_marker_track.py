import sys

from xensesdk.omni.widgets import ExampleView
from xensesdk.xenseInterface.XenseSensor import Sensor


def main():
    sensor_0 = Sensor.create("OP00000F", config_path="/home/linux/xensesdk/deprecated_example/config/OP00000F")
    View = ExampleView(sensor_0)
    View2d = View.create2d(Sensor.OutputType.Difference, Sensor.OutputType.Depth, Sensor.OutputType.Marker2D)

    def callback():
        src, depth, marker3DInit, marker3D = sensor_0.selectSensorInfo(
            Sensor.OutputType.Difference,
            Sensor.OutputType.Depth,
            Sensor.OutputType.Marker3DInit,
            Sensor.OutputType.Marker3D
        )
        marker_img = sensor_0.drawMarkerMove(src)
        View2d.setData(Sensor.OutputType.Marker2D, marker_img)
        View2d.setData(Sensor.OutputType.Difference, src)
        View2d.setData(Sensor.OutputType.Depth, depth)
        View.setMarker(marker3D)
        View.setMarkerFlow(marker3DInit, marker3D)
        View.setDepth(depth)

    View.setCallback(callback)
    View.show()
    sensor_0.release()
    sys.exit()


if __name__ == '__main__':
    main()
