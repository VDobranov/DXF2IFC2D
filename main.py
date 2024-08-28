

from src.ifc import create_CartesianPoint, create_Direction, create_LocalPlacement
from src.classes import Block, Model, Settings, Sheet

import sys
import time

import csv
# import ezdxf
from ezdxf.filemanagement import readfile
from ezdxf.lldxf.const import DXFStructureError
from ezdxf.document import Drawing

import ifcopenshell as ios
from ifcopenshell import validate
from ifcopenshell.api import run

from pprint import pprint


start = time.time()
print('Старт: ' + time.ctime(start))

DXFFILENAME: str = "SKYLARK250_CORNER-S_cnc"
# DXFFILENAME: str = "SKYLARK250_WINDOW-XL2_cnc"
DXFFILENAME: str = "SKYLARK250_END-S-0_cnc"
DXFFILENAME: str = "SKYLARK250_END-XXS-0_cnc"
# DXFFILENAME: str = "SKYLARK250_SKYLIGHT-XXS_cnc"
# DXFFILENAME: str = "SKYLARK250_FLOOR-S-0_cnc"
# DXFFILENAME: str = "tiny1"
BLOCKNAME: str = DXFFILENAME.removeprefix("SKYLARK250_").removesuffix("_cnc")
IFCFILENAME: str = DXFFILENAME
DXFPATH: str = "./drawings"
IFCPATH: str = "./models"
CSVPATH: str = "./models/coord_data"
THICKNESS: float = 18  # толщина листа, мм

ifcFile = ios.open(f"{IFCPATH}/TEMPLATE.ifc")

try:
    dwg: Drawing = readfile(f"{DXFPATH}/{DXFFILENAME}.dxf")
except IOError:
    print(f"File {DXFFILENAME} not found.")
    sys.exit(1)
except DXFStructureError:
    print(f"File {DXFFILENAME} is not a DXF file.")
    sys.exit(2)

csvData: list = []
with open(f"{CSVPATH}/{BLOCKNAME}.csv") as csvfile:
    csvData = list(csv.DictReader(csvfile))


settings = Settings(thickness=THICKNESS, outerColor=5, innerColor=4, millColor=3)
model = Model(settings=settings, ifcFile=ifcFile)
sheet = Sheet(settings, dwg)
block = Block(settings, model, BLOCKNAME, [sheet])

for plateType in block.plateTypes:
    _data: dict[str, str] = None
    for row in csvData:
        if plateType.template.name == row['Name']:
            _data = row
            break
    if _data != None:
        if _data['trueName'] != "":
            plateType.template.name = _data['trueName']
            plateType.ifcPlateType.Name = _data['trueName']
            _pset = plateType.ifcPlateType.HasPropertySets[0]
            run("pset.edit_pset", ifcFile, pset=_pset, properties={
                "ModelLabel": _data['trueName']
            })

for plate in block.plates:
    _data: dict[str, str] = None
    for row in csvData:
        if plate.ifcPlate.Name == row['Name']:
            _data = row
            csvData.remove(row)
            break
    if _data != None:
        _x, _y, _z = float(_data['x']), float(_data['y']), float(_data['z'])
        _axisD = [float(_data['Axis.X']), float(_data['Axis.Y']), float(_data['Axis.Z'])]
        _refD = [float(_data['RefDirection.X']), float(_data['RefDirection.Y']), float(_data['RefDirection.Z'])]
        _axis = create_Direction(model=ifcFile, d_ratios=_axisD)
        _ref = create_Direction(model=ifcFile, d_ratios=_refD)
        _lp = create_LocalPlacement(
            model = ifcFile,
            local_placements=model.local_placements,
            point=create_CartesianPoint(model=ifcFile, coords=[_x, _y, _z]),
            dir_z=_axis,
            dir_x=_ref
        )
        plate.ifcPlate.ObjectPlacement = _lp
        if _data['trueName'] != "":
            plate.ifcPlate.Name = _data['trueName']



model.ifcFile.write(f"{IFCPATH}/{IFCFILENAME}.ifc")

# валидация
logger = validate.json_logger()
validate.validate(model.ifcFile, logger, express_rules=True)  # type: ignore
pprint(logger.statements)


finish = time.time()
print('Финиш: ' + time.ctime(finish))
spent_time = time.strftime("%H:%M:%S", time.gmtime(finish - start))
print('Затрачено времени: ' + spent_time)
