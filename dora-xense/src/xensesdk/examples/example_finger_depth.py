import sys

from xensesdk.omni.widgets import ExampleView
from xensesdk.xenseInterface.XenseSensor import Sensor


def main():
    sensor_0 = Sensor.create(0, config_path=r"J:\pack\xensesdk\xensesdk\examples\finger4")
    View = ExampleView(sensor_0)
    View2d = View.create2d(Sensor.OutputType.Difference, Sensor.OutputType.Depth)

    def callback():
        diff, depth = sensor_0.selectSensorInfo(
            Sensor.OutputType.Difference,
            Sensor.OutputType.Depth,
        )
        View2d.setData(Sensor.OutputType.Difference, diff)
        View2d.setData(Sensor.OutputType.Depth, depth)
        View.setDepth(depth)

    View.setCallback(callback)
    View.show()
    sensor_0.release()
    sys.exit()

if __name__ == '__main__':
    main()
