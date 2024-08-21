

from src.classes import Block, Model, Settings, Sheet

import sys
import time

import ezdxf
from ezdxf.filemanagement import readfile
from ezdxf.lldxf.const import DXFStructureError
from ezdxf.document import Drawing

import ifcopenshell as ios
from ifcopenshell import validate

from pprint import pprint


start = time.time()
print('Старт: ' + time.ctime(start))

# DXFFILENAME: str = "SKYLARK250_CORNER-S_cnc"
DXFFILENAME: str = "SKYLARK250_WINDOW-XL2_cnc"
# DXFFILENAME: str = "SKYLARK250_END-S-0_cnc"
# DXFFILENAME: str = "SKYLARK250_SKYLIGHT-XXS_cnc"
# DXFFILENAME: str = "tiny1"
BLOCKNAME: str = DXFFILENAME.removeprefix("SKYLARK250_").removesuffix("_cnc")
IFCFILENAME: str = DXFFILENAME
DXFPATH: str = "./drawings"
IFCPATH: str = "./models"
THICKNESS: float = 18  # толщина листа, мм
BEAT: float = 4  # диаметр сверла, мм

ifcFile = ios.open(f"{IFCPATH}/TEMPLATE.ifc")

try:
    dwg: Drawing = readfile(f"{DXFPATH}/{DXFFILENAME}.dxf")
except IOError:
    print(f"File {DXFFILENAME} not found.")
    sys.exit(1)
except DXFStructureError:
    print(f"File {DXFFILENAME} is not a DXF file.")
    sys.exit(2)


settings = Settings(thickness=THICKNESS, outerColor=5, innerColor=4, millColor=3)
model = Model(settings=settings, ifcFile=ifcFile)
sheet = Sheet(settings, dwg)
block = Block(settings, model, BLOCKNAME, [sheet])

# dwg2 = ezdxf.new()
# msp2 = dwg2.modelspace()
# for template in block.templates:
#     _drills = [template.contour] + template.cuts + template.mills
#     for _drill in _drills:
#         msp2.add_foreign_entity(_drill.polyline)
# dwg2.saveas(f"{DXFPATH}/{DXFFILENAME}_.dxf")
model.ifcFile.write(f"{IFCPATH}/{IFCFILENAME}.ifc")

# валидация
logger = validate.json_logger()
validate.validate(model.ifcFile, logger, express_rules=True)  # type: ignore
pprint(logger.statements)


finish = time.time()
print('Финиш: ' + time.ctime(finish))
spent_time = time.strftime("%H:%M:%S", time.gmtime(finish - start))
print('Затрачено времени: ' + spent_time)
