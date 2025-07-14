import cypack; cypack.init(__name__, set([]))
from pathlib import Path

PROJ_DIR = Path(__file__).resolve().parent

import platform

SYSTEM = platform.system().lower()
MACHINE = platform.machine().lower()
