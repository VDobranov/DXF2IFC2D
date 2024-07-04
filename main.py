from typing import Sequence, Any
import sys
import ezdxf
from ezdxf import select
from ezdxf.document import Drawing, Modelspace
from ezdxf.entities import DXFEntity, Layer, LWPolyline
from ezdxf.select import Window
import ifcopenshell as ios

FILENAME: str = "SKYLARK250_CORNER-S_cnc"

try:
    dwg: Drawing = ezdxf.readfile(f"./drawings/{FILENAME}.dxf")
except IOError:
    print(f"File {FILENAME} not found.")
    sys.exit(1)
except ezdxf.DXFStructureError:
    print(f"File {FILENAME} is not a DXF file.")
    sys.exit(2)

msp: Modelspace = dwg.modelspace()

# Сбор «цветных» полилиний
red_polys: list[LWPolyline] = []
yellow_polys: list[LWPolyline] = []
green_polys: list[LWPolyline] = []
lblue_polys: list[LWPolyline] = []
blue_polys: list[LWPolyline] = []
for entity in msp.query("LWPOLYLINE"):
    _layerE: str = entity.dxf.layer
    _layer: Layer = dwg.layers.get(_layerE)
    if _layer.color == 1:
        red_polys.append(entity) # type: ignore
    if _layer.color == 2:
        yellow_polys.append(entity) # type: ignore
    if _layer.color == 3:
        green_polys.append(entity) # type: ignore
    if _layer.color == 4:
        lblue_polys.append(entity) # type: ignore
    if _layer.color == 5:
        blue_polys.append(entity) # type: ignore
        
print(f"Number of blue polylines: {len(blue_polys)}")

def get_min_coords(pline: LWPolyline) -> tuple[float, float]:
    """
    Функция get_min_coords принимает объект LWPolyline и возвращает кортеж из двух чисел: минимальной x-координаты и минимальной y-координаты.

    :param pline: объект LWPolyline
    :type pline: LWPolyline
    :return: кортеж из двух чисел: минимальной x-координаты и минимальной y-координаты
    :rtype: tuple[float, float] 
    """
    _points: list[Sequence[float]]  = pline.get_points()
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
    _points: list[Sequence[float]]  = pline.get_points()
    _x = max(_points[i][0] for i in range(len(_points)))
    _y = max(_points[i][1] for i in range(len(_points)))
    return _x, _y

def nullify_coords(pline: LWPolyline, x:float, y: float) -> None:
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
    _points: list[Sequence[float]]  = pline.get_points()
    __points: list[list[float]] = []
    for p in _points:
        p = list(p)
        p[0] -= x
        p[1] -= y
        __points.append(p)
    pline.set_points(__points)

details_polys: list[list[LWPolyline]] = []

def group_polys_by_details(poly:LWPolyline) -> None:
    maxs: tuple[float, float] = get_max_coords(poly)
    mins: tuple[float, float] = get_min_coords(poly)
    window: Window = select.Window(mins, maxs)
    details_polys.append([])
    for e in select.bbox_overlap(window, msp):
        i: int = blue_polys.index(poly)
        details_polys[i].append(e) # type: ignore

for bp in blue_polys:
    group_polys_by_details(bp)

mins: tuple[float, float] = get_min_coords(blue_polys[-1])
for e in details_polys[-1]:
    nullify_coords(e, mins[0], mins[1]) # type: ignore

dwg.saveas(f"./drawings/{FILENAME}_.dxf")