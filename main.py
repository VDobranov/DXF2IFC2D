from src.dxf import get_min_coords, get_max_coords, nullify_coords, group_polys_by_details, convert_detail_polys_to_Profiles

import sys

import ezdxf
from ezdxf.document import Drawing, Modelspace
from ezdxf.entities import Layer, LWPolyline
import ezdxf.math

import ifcopenshell as ios
from ifcopenshell import entity_instance, validate
from ifcopenshell.api import run
from ifcopenshell.util import representation, shape_builder

from pprint import pprint

DXFFILENAME: str = "SKYLARK250_CORNER-S_cnc"
# DXFFILENAME: str = "tiny1"
IFCFILENAME: str = DXFFILENAME
DXFPATH: str = "./drawings"
IFCPATH: str = "./models"
THICKNESS: float = 18

model = ios.open(f"{IFCPATH}/TEMPLATE.ifc")
builder = shape_builder.ShapeBuilder(model)

try:
    dwg: Drawing = ezdxf.readfile(f"{DXFPATH}/{DXFFILENAME}.dxf")
except IOError:
    print(f"File {DXFFILENAME} not found.")
    sys.exit(1)
except ezdxf.DXFStructureError:
    print(f"File {DXFFILENAME} is not a DXF file.")
    sys.exit(2)

msp: Modelspace = dwg.modelspace()

# Сбор «цветных» полилиний
red_polys: list[LWPolyline] = []
yellow_polys: list[LWPolyline] = []
green_polys: list[LWPolyline] = []
lblue_polys: list[LWPolyline] = []
blue_polys: list[LWPolyline] = []
for e in msp.query("LWPOLYLINE"):
    _layerE: str = e.dxf.layer
    _layer: Layer = dwg.layers.get(_layerE)
    if _layer.color == 1:
        red_polys.append(e)  # type: ignore
    if _layer.color == 2:
        yellow_polys.append(e)  # type: ignore
    if _layer.color == 3:
        green_polys.append(e)  # type: ignore
    if _layer.color == 4:
        lblue_polys.append(e)  # type: ignore
    if _layer.color == 5:
        blue_polys.append(e)  # type: ignore

details_polys: list[list[LWPolyline]] = []
for bp in blue_polys:
    details_polys.append(group_polys_by_details(
        poly=bp,
        msp=msp,
        blue_polys=blue_polys,
        green_polys=green_polys,
        lblue_polys=lblue_polys
    ))

detail_profiles: list[list[entity_instance]] = []
for group in details_polys:
    blue: LWPolyline
    for ee in group:
        if ee in blue_polys:
            blue = ee
            break
    mins: tuple[float, float] = get_min_coords(blue)
    maxs: tuple[float, float] = get_max_coords(blue)
    _x = (maxs[0] - mins[0]) / 2 + mins[0]
    _y = (maxs[1] - mins[1]) / 2 + mins[1]
    for ee in group:
        nullify_coords(ee, _x, _y)
    detail_profiles.append(convert_detail_polys_to_Profiles(
        polys=group,
        builder=builder,
        blue_polys=blue_polys,
        lblue_polys=lblue_polys,
        green_polys=green_polys,
        yellow_polys=yellow_polys
    ))

body: entity_instance = representation.get_context(
    model, "Model", "Body", "MODEL_VIEW")
history: entity_instance = model.by_type("IfcOwnerHistory")[0]
site: entity_instance = model.by_type('IfcSite')[0]
storey: entity_instance = model.by_type('IfcBuildingStorey')[0]
origin: entity_instance = model.by_type('IfcCartesianPoint')[0]

placement3d: entity_instance = model.by_type("IfcAxis2Placement3D")[0]
placement2d: entity_instance = model.by_type("IfcAxis2Placement2D")[0]

for dir in model.by_type("IfcDirection"):
    if dir.DirectionRatios[0] == 1 and dir.DirectionRatios[1] == 0 and dir.DirectionRatios[2] == 0:
        dir_x: entity_instance = dir
        break

for dir in model.by_type("IfcDirection"):
    if dir.DirectionRatios[0] == 0 and dir.DirectionRatios[1] == 1 and dir.DirectionRatios[2] == 0:
        dir_z: entity_instance = dir
        break

for dir in model.by_type("IfcDirection"):
    if dir.DirectionRatios[0] == 0 and dir.DirectionRatios[1] == 0 and dir.DirectionRatios[2] == 1:
        dir_z: entity_instance = dir
        break

'''
Этот код создает словарь local_placements, где ключами являются строки, сформированные из идентификаторов объектов IfcLocalPlacement, и значениями - сами объекты IfcLocalPlacement. Он проходит по всем объектам IfcLocalPlacement в модели и для каждого объекта формирует строку, содержащую идентификаторы объектов, связанных с этим объектом IfcLocalPlacement, и добавляет эту строку в словарь как ключ с соответствующим объектом IfcLocalPlacement в качестве значения.
'''
local_placements: dict[str, entity_instance] = dict()
for lp in model.by_type("IfcLocalPlacement"):
    if lp.PlacementRelTo != None:
        _rel = lp.PlacementRelTo.RelativePlacement
        name1: str = f"{_rel.Location.id()}-{_rel.Axis.id()}-{_rel.RefDirection.id()}"
    else:
        name1: str = "None"
    _rel = lp.RelativePlacement
    name2: str = f"{_rel.Location.id()}-{_rel.Axis.id()}-{_rel.RefDirection.id()}"
    name: str = f"{name1}/{name2}"
    local_placements[name] = lp

print(*local_placements.keys())


'''
Этот код создает объект IfcLocalPlacement на основе заданных параметров. Если точка не задана, используется точка по умолчанию. Если объект IfcLocalPlacement уже существует в словаре local_placements, он берется из словаря. В противном случае, создается новый объект IfcLocalPlacement и добавляется в словарь. Затем возвращается созданный или существующий объект IfcLocalPlacement. 
'''
def create_LocalPlacement(
        local_placements: dict[str, entity_instance],
        placement_rel: entity_instance | None = None,
        point: entity_instance = origin,
        dir_z: entity_instance = dir_z,
        dir_x: entity_instance = dir_x,
) -> entity_instance:
    if placement_rel != None:
        name1: str = f"{placement_rel.Location.id()}-{placement_rel.Axis.id()}-{placement_rel.RefDirection.id()}"
    else:
        name1: str = "None"
    name2: str = f"{point.id()}-{dir_z.id()}-{dir_x.id()}"
    name: str = f"{name1}/{name2}"
    if name not in local_placements:
        placement = model.createIfcAxis2placement3d(point, dir_z, dir_x)
        local_placement = model.createIfcLocalPlacement(
            placement_rel, placement)
        local_placements[name] = local_placement
    else:
        local_placement = local_placements[name]
    return local_placement


def create_IfcArbitraryProfileDefWithVoids(ProfileName: str, OuterCurve: entity_instance, InnerCurves: list[entity_instance]) -> entity_instance:
    return model.createIfcArbitraryProfileDefWithVoids("AREA", ProfileName, OuterCurve, InnerCurves)


def create_IfcExtrudedAreaSolid(SweptArea: entity_instance, Depth: float) -> entity_instance:
    return model.createIfcExtrudedAreaSolid(SweptArea, None, dir_z, Depth)


def create_FoundationStudType(profile: entity_instance):
    stud = run("root.create_entity", model, ifc_class="IfcMechanicalFastenerType",
               predefined_type="STUD", name=f"Ш")
    # # print(stud.Name)
    # stud.NominalLength = L
    # stud.NominalDiameter = d
    # plist = create_IfcCartesianPointList2D_stud(L, l, R, d)
    # pcurve = create_IfcIndexedPolyCurve_stud(plist, create_Segments_stud())
    # sds = create_IfcSweptDiskSolid(pcurve, d/2)
    sds = create_IfcExtrudedAreaSolid(SweptArea=profile, Depth=THICKNESS/2)
    representation = model.createIfcShapeRepresentation(
        ContextOfItems=body, RepresentationIdentifier="Body", RepresentationType="AdvancedSweptSolid", Items=[sds])
    # offset = model.createIfcCartesianPoint([0.0,0.0,float(l0)])
    # placement = model.createIfcAxis2placement3d(offset, dir_z, dir_x)
    local_placement = create_LocalPlacement(local_placements=local_placements)
    placement = local_placement.RelativePlacement
    representationmap = model.createIfcRepresentationMap(
        placement, representation)
    # run("geometry.assign_representation", model, product=stud, representation=representation)
    stud.RepresentationMaps = [representationmap]
    return stud


def create_FoundationStud(L, l, R, d, l0) -> entity_instance:
    stud_type = create_FoundationStudType(L, l, R, d, l0)
    stud = run("root.create_entity", model, ifc_class="IfcMechanicalFastener")
    run("type.assign_type", model, related_objects=[
        stud], relating_type=stud_type)
    run("geometry.edit_object_placement", model, product=stud)
    run("attribute.edit_attributes", model, product=stud, attributes={
        "Name": stud_type.Name,
        "ObjectType": stud_type.ElementType,
        "PredefinedType": stud_type.PredefinedType,
        "NominalDiameter": stud_type.NominalDiameter,
        "NominalLength": stud_type.NominalLength
    })
    return stud

for p in detail_profiles[3]:
    create_FoundationStudType(p)
print(*local_placements.keys())

# ex = builder.extrude(detail_profiles[0][0])
# ctx = model.by_id(15)
# rep = builder.get_representation(ctx, ex)

# # Create our element type. Types do not have an object placement.
# element_type = api.run("root.create_entity", model, ifc_class="IfcFurnitureType")

# # Let's create our representation!
# # See above sections for examples on how to create representations.
# representation = rep

# # Assign our representation to the element type.
# api.run("geometry.assign_representation", model, product=element_type, representation=representation)

# # Create our element occurrence with an object placement.
# element = api.run("root.create_entity", model, ifc_class="IfcFurniture")
# api.run("geometry.edit_object_placement", model, product=element)

# # Assign our furniture occurrence to the type.
# # That's it! The representation will automatically be mapped!
# api.run("type.assign_type", model, related_objects=[element], relating_type=element_type)


dwg.saveas(f"{DXFPATH}/{DXFFILENAME}_.dxf")
model.write(f"{IFCPATH}/{IFCFILENAME}.ifc")

# валидация
logger = validate.json_logger()
validate.validate(model, logger, express_rules=True)  # type: ignore
pprint(logger.statements)
