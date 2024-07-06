import math
import sys
from typing import Sequence, Any
import ezdxf
from ezdxf import select
from ezdxf.document import Drawing, Modelspace
from ezdxf.entities import DXFEntity, Layer, LWPolyline
import ezdxf.math
from ezdxf.select import Window
import ifcopenshell as ios
import ifcopenshell.validate
import ifcopenshell.util.shape_builder
from ifcopenshell import entity_instance
from pprint import pprint

# DXFFILENAME: str = "SKYLARK250_CORNER-S_cnc"
DXFFILENAME: str = "tiny"
IFCFILENAME: str = DXFFILENAME
DXFPATH = "./drawings"
IFCPATH = "./models"

model = ios.open(f"{IFCPATH}/TEMPLATE.ifc")
builder = ios.util.shape_builder.ShapeBuilder(model)

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

# print(f"Number of blue polylines: {len(blue_polys)}")


def get_min_coords(pline: LWPolyline) -> tuple[float, float]:
    """
    Функция get_min_coords принимает объект LWPolyline и возвращает кортеж из двух чисел: минимальной x-координаты и минимальной y-координаты.

    :param pline: объект LWPolyline
    :type pline: LWPolyline
    :return: кортеж из двух чисел: минимальной x-координаты и минимальной y-координаты
    :rtype: tuple[float, float] 
    """
    _points: list[Sequence[float]] = pline.get_points()
    _x = min(_points[i][0] for i in range(len(_points)))
    _y = min(_points[i][1] for i in range(len(_points)))
    return _x, _y


def get_max_coords(pline: LWPolyline) -> tuple[float, float]:
    """
    Функция get_max_coords принимает объект LWPolyline и возвращает кортеж из двух чисел: максимальной x-координаты и максимальной y-координаты.

    :param pline: объект LWPolyline
    :type pline: LWPolyline
    :return: кортеж из двух чисел: максимальной x-координаты и максимальной y-координаты
    :rtype: tuple[float, float] 
    """
    _points: list[Sequence[float]] = pline.get_points()
    _x = max(_points[i][0] for i in range(len(_points)))
    _y = max(_points[i][1] for i in range(len(_points)))
    return _x, _y


def nullify_coords(pline: LWPolyline, x: float, y: float) -> None:
    """
    Функция nullify_coords принимает объект LWPolyline и два числа (x и y) и нормализует координаты объекта LWPolyline, вычитая x и y из каждого x-координаты и y-координаты соответственно.

    :param pline: LWPolyline объект
    :type pline: LWPolyline
    :param x: число, которое вычитается из каждой x-координаты
    :type x: float
    :param y: число, которое вычитается из каждой y-координаты
    :type y: float
    :return: None
    :rtype: None
    """
    _points: list[Sequence[float]] = pline.get_points()
    __points: list[list[float]] = []
    for p in _points:
        p = list(p)
        p[0] -= x
        p[1] -= y
        __points.append(p)
    pline.set_points(__points)


details_polys: list[list[LWPolyline]] = []


def group_polys_by_details(poly: LWPolyline) -> None:
    """
    Функция группирует полилинии, попавшие в описываемый прямоугольник вокруг рассматриваемой полилинии.

    :param poly: полилиния, внутри которой нужно сгруппировать прочии полилинии
    :type poly: LWPolyline
    :return: None
    """
    maxs: tuple[float, float] = get_max_coords(poly)
    mins: tuple[float, float] = get_min_coords(poly)
    window: Window = select.Window(mins, maxs)
    details_polys.append([])
    for e in select.bbox_overlap(window, msp):
        i: int = blue_polys.index(poly)
        details_polys[i].append(e)  # type: ignore


for bp in blue_polys:
    group_polys_by_details(bp)


def find_center_on_arc(p1: Sequence[float], p2: Sequence[float]) -> Sequence[float]:
    """
    Функция находит центр на дуге.

    :param p1: первая точка дуги
    :type p1: Sequence[float]
    :param p2: вторая точка дуги
    :type p2: Sequence[float]
    :return: центр дуги
    :rtype: Sequence[float]
    """
    x1 = p1[0]
    y1 = p1[1]
    x2 = p2[0]
    y2 = p2[1]
    center: tuple[float, float] = ezdxf.math.bulge_center(
        (x1, y1), (x2, y2), p1[4])
    xc = center[0]
    yc = center[1]
    middle: tuple[float, float] = (x1 + (x2 - x1) / 2, y1 + (y2-y1) / 2)
    xm = middle[0]
    ym = middle[1]
    part_radius: float = math.sqrt((xc - xm) ** 2 + (yc - ym) ** 2)
    radius: float = ezdxf.math.bulge_radius((x1, y1), (x2, y2), p1[4])
    coeff: float = radius / part_radius
    x = xc - (xc - xm) * coeff
    y = yc - (yc - ym) * coeff
    point: tuple[float, float] = (x, y)
    return point


def convert_poly_to_PointList(poly: LWPolyline) -> tuple[list, list]:
    """
    Функция преобразует полилинию в список точек с указанием, какие точки являются вершинами дуг.

    :param poly: полилиния, которую нужно преобразовать
    :type poly: LWPolyline
    :return: список точек и индексы дуг
    :rtype: tuple[list, list]
    """
    ifc_points: list[tuple[float, float]] = []
    arc_indexes: list[int] = []
    dxf_points: list[Sequence[float]] = poly.get_points()
    for p in dxf_points:
        ifc_points.append((float(p[0]), float(p[1])))
        if p[4] != 0:
            if p != dxf_points[-1]:
                p_next = dxf_points[dxf_points.index(p)+1]
            else:
                p_next = dxf_points[0]
            p_center = find_center_on_arc(p, p_next)
            ifc_points.append((float(p_center[0]), float(p_center[1])))
            arc_indexes.append(dxf_points.index(p)+1)
    return ifc_points, arc_indexes


mins: tuple[float, float] = get_min_coords(blue_polys[-1])
for e in details_polys[-1]:
    nullify_coords(e, mins[0], mins[1])  # type: ignore

ifc_points, arc_indexes = convert_poly_to_PointList(blue_polys[-1])
curve = builder.polyline(ifc_points, arc_points=arc_indexes, closed=True)
curve.SelfIntersect = False

profile = builder.profile(curve, name="test")

dwg.saveas(f"{DXFPATH}/{DXFFILENAME}_.dxf")
model.write(f"{IFCPATH}/{IFCFILENAME}.ifc")

logger = ios.validate.json_logger()
ios.validate.validate(model, logger, express_rules=True)  # type: ignore
pprint(logger.statements)
