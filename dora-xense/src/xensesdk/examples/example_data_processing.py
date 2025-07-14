import sys

from xensesdk.omni.widgets import ExampleView
from xensesdk.xenseInterface.XenseSensor import Sensor


def main(data_path):
    sensor_0 = Sensor.create(
        data_path,
        config_path= r"J:\xensesdk\xensesdk\examples\config\W1"
    )

    View = ExampleView(sensor_0)
    View2d = View.create2d(Sensor.OutputType.Rectify, Sensor.OutputType.Depth)

    def callback():
        src, depth= sensor_0.selectSensorInfo(Sensor.OutputType.Rectify, Sensor.OutputType.Depth)
        View2d.setData(Sensor.OutputType.Rectify, src)
        View2d.setData(Sensor.OutputType.Depth, depth)
        View.setDepth(depth)
    View.setCallback(callback)

    View.show()
    sensor_0.release()
    sys.exit()

if __name__ == '__main__':
    data_path = r"J:\xensesdk\data\sensor_0_rectify_video_2025_03_07_11_10_15.mp4"
    main(data_path)
