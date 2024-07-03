from typing import Sequence, Any
import sys
import ezdxf
from ezdxf.document import Drawing, Modelspace
from ezdxf.entities import DXFEntity, Layer, LWPolyline
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

for layer in dwg.layers:
    print(f"{layer.dxf.name} - {layer.dxf.color}")

blue_polys: list[LWPolyline] = []
for entity in msp.query("LWPOLYLINE"):
    _layerE: str = entity.dxf.layer
    _layer: Layer = dwg.layers.get(_layerE)
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

xy: tuple[float, float] = get_min_coords(blue_polys[0])
nullify_coords(blue_polys[0], xy[0], xy[1])


dwg.saveas(f"./drawings/{FILENAME}_.dxf")