import math

from typing import Sequence
import ezdxf
import ezdxf.math
from ezdxf import select
from ezdxf.document import Modelspace
from ezdxf.entities import LWPolyline
from ezdxf.select import Window

from ifcopenshell import entity_instance


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


def group_polys_by_details(
        poly: LWPolyline,
        msp: Modelspace,
        blue_polys: list[LWPolyline],
        green_polys: list[LWPolyline],
        lblue_polys: list[LWPolyline],
) -> list[LWPolyline]:
    """
    Функция группирует полилинии, попавшие в описываемый прямоугольник вокруг рассматриваемой полилинии.

    :param poly: полилиния, внутри которой нужно сгруппировать прочии полилинии
    :type poly: LWPolyline
    :param msp: пространство модели, в котором нужно искать полилинии
    :type msp: Modelspace
    :param blue_polys: список полилиний, которые нужно проверить
    :type blue_polys: list[LWPolyline]
    :param green_polys: список полилиний, которые нужно проверить
    :type green_polys: list[LWPolyline]
    :param lblue_polys: список полилиний, которые нужно проверить
    :type lblue_polys: list[LWPolyline]
    :return: список полилиний, которые попали в прямоугольник вокруг рассматриваемой полилинии
    :rtype: list[LWPolyline]
    """
    maxs: tuple[float, float] = get_max_coords(poly)
    mins: tuple[float, float] = get_min_coords(poly)
    window: Window = select.Window(mins, maxs)
    group: list[LWPolyline] = []
    for e in select.bbox_overlap(window, msp):
        if e not in blue_polys and e not in green_polys and e not in lblue_polys:
            continue
        if e.dxftype() == "LWPOLYLINE":
            group.append(e)  # type: ignore
    return group


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
    x1, y1 = p1[0], p1[1]
    x2, y2 = p2[0], p2[1]

    center: tuple[float, float] = ezdxf.math.bulge_center(
        (x1, y1), (x2, y2), p1[4])
    xc, yc = center[0], center[1]
    radius: float = ezdxf.math.bulge_radius((x1, y1), (x2, y2), p1[4])
    alpha: float = 0
    if x2 != x1:
        alpha = math.pi/2 - math.atan((y2 - y1)/(x2 - x1))
    xr = abs(radius * math.cos(alpha))
    yr = abs(radius * math.sin(alpha))
    if p1[4] < 0:
        if y2 > y1:
            x = xc - xr
        else:
            x = xc + xr
        if x2 > x1:
            y = yc + yr
        else:
            y = yc - yr
    else:
        if y2 > y1:
            x = xc + xr
        else:
            x = xc - xr
        if x2 > x1:
            y = yc - yr
        else:
            y = yc + yr
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
    arc_middles: list[int] = []
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
            arc_middles.append(len(ifc_points)-1)
    return ifc_points, arc_middles


def convert_detail_polys_to_Profiles(
        polys: list[LWPolyline],
        builder: entity_instance,
        blue_polys: list[LWPolyline],
        lblue_polys: list[LWPolyline],
        green_polys: list[LWPolyline],
        yellow_polys: list[LWPolyline],
) -> list[entity_instance]:
    """
    Функция преобразует полилинии в профили.

    :param polys: список полилиний
    :type polys: list[LWPolyline]
    :param builder: объект для создания профилей
    :type builder: entity_instance
    :param blue_polys: список полилиний, которые нужно преобразовать в синий профили
    :type blue_polys: list[LWPolyline]
    :param lblue_polys: список полилиний, которые нужно преобразовать в светло-синие профили
    :type lblue_polys: list[LWPolyline]
    :param green_polys: список полилиний, которые нужно преобразовать в зеленые профили
    :type green_polys: list[LWPolyline]
    :param yellow_polys: список полилиний, которые нужно преобразовать в желтые профили
    :type yellow_polys: list[LWPolyline]
    :return: список профилей
    :rtype: list[entity_instance]
    """
    profiles: list[entity_instance] = []
    blue_curves: dict[str, entity_instance] = dict()
    lblue_curves: dict[str, entity_instance] = dict()
    green_curves: dict[str, entity_instance] = dict()
    yellow_curves: dict[str, entity_instance] = dict()
    name: str = ""
    for p in polys:
        ifc_points, arc_middles = convert_poly_to_PointList(p)
        curve = builder.polyline(
            ifc_points, arc_points=arc_middles, closed=True)
        curve.SelfIntersect = False
        if p in blue_polys:
            blue_curves[p.dxf.handle] = curve
            name = p.dxf.handle
        elif p in lblue_polys:
            lblue_curves[p.dxf.handle] = curve
        elif p in green_polys:
            green_curves[p.dxf.handle] = curve
        elif p in yellow_polys:
            yellow_curves[p.dxf.handle] = curve
    profile = builder.profile(list(blue_curves.values())[0], inner_curves=list(
        lblue_curves.values()), name=f"{name}")
    profiles.append(profile)
    for k, v in green_curves.items():
        cut = builder.profile(v, name=f"{name}_cut_{k}")
        profiles.append(cut)
    return profiles