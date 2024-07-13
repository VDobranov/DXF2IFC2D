from src.dxf import check_polys, get_min_coords, get_max_coords, nullify_coords, group_polys_by_details, convert_detail_polys_to_Profiles

import sys

import ezdxf
from ezdxf.document import Drawing, Modelspace
from ezdxf.entities import Layer, LWPolyline, Polyline
import ezdxf.math
from ezdxf.addons.drawing import Frontend, RenderContext, svg, layout

import ifcopenshell as ios
from ifcopenshell import entity_instance, validate
from ifcopenshell.api import run
from ifcopenshell.util import representation, shape_builder

from pprint import pprint

DXFFILENAME: str = "SKYLARK250_WINDOW-XL2_cnc"
# DXFFILENAME: str = "tiny1"
BLOCKNAME: str = DXFFILENAME.removeprefix("SKYLARK250_").removesuffix("_cnc")
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
        yellow_polys.append(e)  # type: ignore
    if _layer.color == 3:
        green_polys.append(e)  # type: ignore
    if _layer.color == 4:
        lblue_polys.append(e)  # type: ignore
    if _layer.color == 5:
        if not check_polys(e, blue_polys):
            blue_polys.append(e)  # type: ignore

details_polys: list[list[LWPolyline | Polyline]] = []
for bp in blue_polys:
    group: list[LWPolyline | Polyline] = group_polys_by_details(
        poly=bp,
        msp=msp,
        blue_polys=blue_polys,
        green_polys=green_polys,
        lblue_polys=lblue_polys,
        yellow_polys=yellow_polys
    )
    details_polys.append(group)
    yellow: list[LWPolyline | Polyline] = []
    for p in group:
        if p in yellow_polys:
            yellow.append(p)
    context = RenderContext(dwg)
    backend = svg.SVGBackend()
    frontend = Frontend(context, backend)
    frontend.draw_entities(yellow)
    page = layout.Page(0, 0, layout.Units.mm, margins=layout.Margins.all(20))
    svg_string = backend.get_string(page)
    with open(f"{DXFPATH}/svgs/{bp.dxf.handle}.svg", "wt", encoding="utf8") as fp:
        fp.write(svg_string)

detail_profiles: list[list[entity_instance]] = []
for group in details_polys:
    blue: LWPolyline | Polyline
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
    detail_name = f"{BLOCKNAME}/{details_polys.index(group)}"
    detail_profiles.append(convert_detail_polys_to_Profiles(
        polys=group,
        builder=builder,
        blue_polys=blue_polys,
        lblue_polys=lblue_polys,
        green_polys=green_polys,
        yellow_polys=yellow_polys,
        name=detail_name
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


def check_CartesianPoint(coords: list[float]) -> bool:
    for p in model.by_type("IfcCartesianPoint"):
        if coords == list(p.Coordinates):
            return True
    return False


def create_CartesianPoint(coords: list[float]) -> entity_instance:
    found = check_CartesianPoint(coords)
    if found:
        for p in model.by_type("IfcCartesianPoint"):
            if coords == list(p.Coordinates):
                return p
    else:
        return model.createIfcCartesianPoint(coords)


def check_Axis2Placement3D(point: entity_instance, dir_z: entity_instance, dir_x: entity_instance) -> bool:
    for p in model.by_type("IfcAxis2Placement3D"):
        if point == p.Location and dir_z == p.Axis and dir_x == p.RefDirection:
            return True
    return False


def create_Axis2Placement3D(point: entity_instance, dir_z: entity_instance, dir_x: entity_instance) -> entity_instance:
    found = check_Axis2Placement3D(point, dir_z, dir_x)
    if found:
        for p in model.by_type("IfcAxis2Placement3D"):
            if point == p.Location and dir_z == p.Axis and dir_x == p.RefDirection:
                return p
    else:
        return model.createIfcAxis2Placement3D(point, dir_z, dir_x)


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

# print(*local_placements.keys())


'''
Этот код создает объект IfcLocalPlacement на основе заданных параметров. Если точка не задана, используется точка по умолчанию. Если объект IfcLocalPlacement уже существует в словаре local_placements, он берется из словаря. В противном случае, создается новый объект IfcLocalPlacement и добавляется в словарь. Затем возвращается созданный или существующий объект IfcLocalPlacement.
1. Проверяем, задана ли точка. Если нет, присваиваем ей значение по умолчанию.
2. Если объект IfcLocalPlacement связан с другим объектом (placement_rel), формируем строку, содержащую идентификаторы этого объекта. Если объект IfcLocalPlacement не связан с другим объектом, в строку включается строка "None".
3. Формируем уникальное имя для объекта IfcLocalPlacement, используя идентификаторы объектов, связанных с ним.
4. Проверяем, есть ли уже такой объект IfcLocalPlacement в словаре local_placements. Если нет, создаем новый объект и добавляем его в словарь. Если есть, берем существующий объект из словаря.
5. Возвращаем созданный или существующий объект IfcLocalPlacement.
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
        placement = create_Axis2Placement3D(point, dir_z, dir_x)
        local_placement = model.createIfcLocalPlacement(
            placement_rel, placement)
        local_placements[name] = local_placement
    else:
        local_placement = local_placements[name]
    return local_placement


# def create_IfcArbitraryProfileDefWithVoids(ProfileName: str, OuterCurve: entity_instance, InnerCurves: list[entity_instance]) -> entity_instance:
#     return model.createIfcArbitraryProfileDefWithVoids("AREA", ProfileName, OuterCurve, InnerCurves)


def create_IfcExtrudedAreaSolid(
        sweptArea: entity_instance,
        depth: float,
        placement: entity_instance | None = None
) -> entity_instance:
    return model.createIfcExtrudedAreaSolid(sweptArea, placement, dir_z, depth)


def create_PlateType(profiles: list[entity_instance], name: str):
    _cuts: list[entity_instance] = []
    _sheet: entity_instance = None
    for profile in profiles:
        if "cut" in profile.ProfileName:
            _point: entity_instance = create_CartesianPoint(
                [0., 0., THICKNESS/2])
            _placement: entity_instance = create_Axis2Placement3D(
                _point, dir_z, dir_x)
            _cuts.append(create_IfcExtrudedAreaSolid(
                sweptArea=profile, depth=THICKNESS/2+1, placement=_placement))
        else:
            _sheet = create_IfcExtrudedAreaSolid(
                sweptArea=profile, depth=THICKNESS)
    for cut in _cuts:
        _sheet = model.createIfcBooleanResult(
            Operator="DIFFERENCE", FirstOperand=_sheet, SecondOperand=cut)
    if _sheet.is_a("IfcBooleanResult"):
        _rtype: str = "CSG"
    else:
        _rtype: str = "SweptSolid"
    representation = model.createIfcShapeRepresentation(
        ContextOfItems=body, RepresentationIdentifier="Body", RepresentationType=_rtype, Items=[_sheet])
    local_placement = create_LocalPlacement(local_placements=local_placements)
    placement = local_placement.RelativePlacement
    representationmap = model.createIfcRepresentationMap(
        placement, representation)

    plate_type = run("root.create_entity", model,
                     ifc_class="IfcPlateType", predefined_type="PART", name=name)
    plate_type.RepresentationMaps = [representationmap]
    pset1 = run("pset.add_pset", model, product=plate_type,
                name="Pset_ManufacturerTypeInformation")
    pset2 = run("pset.add_pset", model, product=plate_type,
                name="Pset_PlateCommon")
    run("pset.edit_pset", model, pset=pset1, properties={
        "ModelReference": "SKYLARK250",
        "ModelLabel": f"{name}",
        "AssemblyPlace": "FACTORY",
        "OperationalDocument": "Wikihouse Design Guide"
    })
    run("pset.edit_pset", model, pset=pset2, properties={
        "Status": "NEW",
    })
    return plate_type


# def create_FoundationStud(L, l, R, d, l0) -> entity_instance:
#     stud_type = create_FoundationStudType(L, l, R, d, l0)
#     stud = run("root.create_entity", model, ifc_class="IfcMechanicalFastener")
#     run("type.assign_type", model, related_objects=[
#         stud], relating_type=stud_type)
#     run("geometry.edit_object_placement", model, product=stud)
#     run("attribute.edit_attributes", model, product=stud, attributes={
#         "Name": stud_type.Name,
#         "ObjectType": stud_type.ElementType,
#         "PredefinedType": stud_type.PredefinedType,
#         "NominalDiameter": stud_type.NominalDiameter,
#         "NominalLength": stud_type.NominalLength
#     })
#     return stud

for p in detail_profiles:
    create_PlateType(p, p[0].ProfileName)
# print(*local_placements.keys())

# eas = model.by_type("IfcExtrudedAreaSolid")
# pprint(eas)
# for e in eas:
#     if e.SweptArea.ProfileName == "90":
#         b1 = e
#     if e.SweptArea.ProfileName == "90_cut_64":
#         b2 = e

# br = model.createIfcBooleanResult(Operator="DIFFERENCE", FirstOperand=b1, SecondOperand=b2)
# stud = run("root.create_entity", model, ifc_class="IfcPlateType",
#             predefined_type="STUD", name="name")
# representation = model.createIfcShapeRepresentation(
#         ContextOfItems=body, RepresentationIdentifier="Body", RepresentationType="CSG",Items=[br])
# local_placement = create_LocalPlacement(local_placements=local_placements)
# placement = local_placement.RelativePlacement
# representationmap = model.createIfcRepresentationMap(placement, representation)
# stud.RepresentationMaps = [representationmap]


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
