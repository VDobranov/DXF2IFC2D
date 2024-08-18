

from src.ifc import create_Plate, create_PlateType, gather_LocalPlacements
from src.dxf import cosine_similarity, cosine_similarity_of_roads, get_poly_length, get_min_coords, get_max_coords, get_poly_length, get_vector_length, nullify_coords, group_polys_by_details, convert_detail_polys_to_Profiles, get_centroid
from src.classes import Block, Settings, Sheet

import sys
import time
import numpy as np

import ezdxf
from ezdxf.filemanagement import readfile
from ezdxf.lldxf.const import DXFStructureError
from ezdxf.document import Drawing
from ezdxf.layouts.layout import Modelspace
from ezdxf.math import BoundingBox
from ezdxf.entities.layer import Layer
from ezdxf.entities.lwpolyline import LWPolyline
from ezdxf.entities.polyline import Polyline

import ifcopenshell as ios
from ifcopenshell import entity_instance, validate
from ifcopenshell.util import representation
from ifcopenshell.util.shape_builder import ShapeBuilder

from pprint import pprint

start = time.time()
print('Старт: ' + time.ctime(start))

# DXFFILENAME: str = "SKYLARK250_CORNER-S_cnc"
# DXFFILENAME: str = "SKYLARK250_WINDOW-XL2_cnc"
DXFFILENAME: str = "SKYLARK250_END-S-0_cnc"
# DXFFILENAME: str = "SKYLARK250_SKYLIGHT-XXS_cnc"
# DXFFILENAME: str = "tiny1"
BLOCKNAME: str = DXFFILENAME.removeprefix("SKYLARK250_").removesuffix("_cnc")
IFCFILENAME: str = DXFFILENAME
DXFPATH: str = "./drawings"
IFCPATH: str = "./models"
THICKNESS: float = 18  # толщина листа, мм
BEAT: float = 4  # диаметр сверла, мм

model = ios.open(f"{IFCPATH}/TEMPLATE.ifc")
builder = ShapeBuilder(model)

try:
    dwg: Drawing = readfile(f"{DXFPATH}/{DXFFILENAME}.dxf")
except IOError:
    print(f"File {DXFFILENAME} not found.")
    sys.exit(1)
except DXFStructureError:
    print(f"File {DXFFILENAME} is not a DXF file.")
    sys.exit(2)






settings = Settings(thickness=THICKNESS, outerColor=5, innerColor=4, millColor=3)
sheet = Sheet(settings, dwg)
block = Block(BLOCKNAME, [sheet])




msp: Modelspace = dwg.modelspace()

# Сбор «цветных» полилиний
red_polys: list[LWPolyline | Polyline] = []
yellow_polys: list[LWPolyline | Polyline] = []
green_polys: list[LWPolyline | Polyline] = []
lblue_polys: list[LWPolyline | Polyline] = []
blue_polys: list[LWPolyline | Polyline] = []
for e in msp.query("LWPOLYLINE POLYLINE"):
    _layerE: str = e.dxf.layer
    _layer: Layer = dwg.layers.get(_layerE)
    if _layer.color == 1:
        red_polys.append(e)  # type: ignore
    if _layer.color == 2:
        # letter: LWPolyline | Polyline = convert_letter_to_poly(e, msp, BEAT/2) # type: ignore
        # yellow_polys.append(letter)
        yellow_polys.append(e)  # type: ignore
    if _layer.color == 3:
        green_polys.append(e)  # type: ignore
    if _layer.color == 4:
        lblue_polys.append(e)  # type: ignore
    if _layer.color == 5:
        blue_polys.append(e)  # type: ignore

details_polys: list[list[LWPolyline | Polyline]] = []
for bp in blue_polys:
    group: list[LWPolyline | Polyline] = group_polys_by_details(
        poly=bp,
        green_polys=green_polys,
        lblue_polys=lblue_polys,
        yellow_polys=yellow_polys
    )
    details_polys.append(group)


detail_profiles: list[list[entity_instance]] = []
# словарь с деталями, в котором: имя детали, её длина, вектор между центром и вырезами и требуемое количество для блока
detail_data: dict[str, list[float | int | np.ndarray]] = {}
detail_num: int = 0
for group in details_polys:
    brk: bool = False
    blue: LWPolyline | Polyline
    for ee in group:
        if ee in blue_polys:
            blue = ee
            break
    bbox: BoundingBox = ezdxf.bbox.extents([blue])
    group_length: float = round(sum(get_poly_length(poly) for poly in group), 1)
    group_cuts_centroid: tuple[float, float] = get_centroid(set(group).intersection(green_polys))
    # coords1: tuple[float, float] = [bbox.extmin[0], bbox.extmin[1]]
    coords: tuple[float, float] = [group_cuts_centroid[0][0], group_cuts_centroid[0][1]]
    if coords == [0, 0]:
        coords = [bbox.center[0], bbox.center[1]]
    # group_cut_vec: float = get_vector_length(bbox.center, coords)
    group_cut_vec: tuple[tuple[float], tuple[float]] = [[bbox.center.x, bbox.center.y], coords]
    for k, v in detail_data.items():
        cos = cosine_similarity_of_roads(v[1], group_cut_vec)
        if v[0] == group_length and round(cos, 9) == 0.999999:
            v[2] += 1
            brk = True
    if brk:
        continue
    detail_num += 1
    detail_name: str = f"{BLOCKNAME}/{detail_num}"
    detail_data[detail_name] = [group_length, group_cut_vec, 1]
    _x = bbox.center[0]
    _y = bbox.center[1]
    for ee in group:
        nullify_coords(ee, _x, _y)
    detail_profiles.append(convert_detail_polys_to_Profiles(
        polys=group,
        builder=builder,
        blue_polys=blue_polys,
        lblue_polys=lblue_polys,
        green_polys=green_polys,
        yellow_polys=yellow_polys,
        name=detail_name
    ))


body: entity_instance | None = representation.get_context(model, "Model", "Body", "MODEL_VIEW")
history: entity_instance = model.by_type("IfcOwnerHistory")[0]
site: entity_instance = model.by_type('IfcSite')[0]
storey: entity_instance = model.by_type('IfcBuildingStorey')[0]
origin: entity_instance = model.by_type('IfcCartesianPoint')[0]

placement3d: entity_instance = model.by_type("IfcAxis2Placement3D")[0]
placement2d: entity_instance = model.by_type("IfcAxis2Placement2D")[0]

for dir in model.by_type("IfcDirection"):
    if list(dir.DirectionRatios) == [1, 0, 0]:
        dir_x: entity_instance = dir
        break

for dir in model.by_type("IfcDirection"):
    if list(dir.DirectionRatios) == [0, 1, 0]:
        dir_y: entity_instance = dir
        break

for dir in model.by_type("IfcDirection"):
    if list(dir.DirectionRatios) == [0, 0, 1]:
        dir_z: entity_instance = dir
        break

local_placements: dict[str, entity_instance] = gather_LocalPlacements(model)

for p in detail_profiles:
    name = p[0].ProfileName
    type = create_PlateType(
        model=model,
        body=body,
        origin=origin,
        local_placements=local_placements,
        dir_z=dir_z,
        dir_x=dir_x,
        profiles=p,
        name=name,
        THICKNESS=THICKNESS,
    )
    amount = detail_data[name][2]
    for i in range(int(amount)):
        name2 = name
        if amount > 1:
            name2 = f"{name}_{i+1}"
        plate = create_Plate(model=model, storey=storey, name=name2, type=type)


dwg.saveas(f"{DXFPATH}/{DXFFILENAME}_.dxf")
model.write(f"{IFCPATH}/{IFCFILENAME}.ifc")

# валидация
logger = validate.json_logger()
validate.validate(model, logger, express_rules=True)  # type: ignore
pprint(logger.statements)


finish = time.time()
print('Финиш: ' + time.ctime(finish))
spent_time = time.strftime("%H:%M:%S", time.gmtime(finish - start))
print('Затрачено времени: ' + spent_time)
