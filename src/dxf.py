import math

from typing import Sequence
import ezdxf
import ezdxf.math
from ezdxf import select
from ezdxf.layouts.layout import Modelspace
from ezdxf.entities.lwpolyline import LWPolyline
from ezdxf.entities.polyline import Polyline
from ezdxf.select import Window

from ifcopenshell import entity_instance
from ifcopenshell.util.shape_builder import ShapeBuilder

TOL: int = 6


def get_vector_length(p1: Sequence[float], p2: Sequence[float]) -> float:
    """
    Функция get_vector_length вычисляет длину вектора между двумя точками.

    :param p1: первая точка
    :type p1: Sequence[float]
    :param p2: вторая точка
    :type p2: Sequence[float]
    :return: длина вектора
    :rtype: float
    """
    return round(math.sqrt((p2[0]-p1[0])**2 + (p2[1]-p1[1])**2), TOL)


def get_arc_length(p1: Sequence[float], p2: Sequence[float], pc: Sequence[float]):
    r = get_vector_length(p1, pc)  # длина радиуса
    c = get_vector_length(p1, p2)  # длина хорды
    a = round(c / (2 * r), TOL)
    return 2 * math.asin(a) * r


def get_poly_length(pline: LWPolyline | Polyline) -> float:
    """
    Функция get_poly_length принимает объект LWPolyline или Polyline и вычисляет длину полилинии (без учёта арок).

    :param pline: объект LWPolyline или Polyline
    :type pline: LWPolyline | Polyline
    :return: длина полилинии
    :rtype: float
    """
    _length: float = 0
    _points: list[Sequence[float]] = []
    if isinstance(pline, LWPolyline):
        _points = pline.get_points("xyb")
    else:
        for pnt in pline.vertices:
            _points.append(pnt.format("xyb"))
    for i in range(len(_points)):
        j = i+1 if i < len(_points)-1 else 0
        if _points[i][2] != 0:
            pc: Sequence[float] = list(ezdxf.math.bulge_center(
                (_points[i][0], _points[i][1]), (_points[j][0], _points[j][1]), _points[i][2]))
            _length += get_arc_length(_points[i], _points[j], pc)
        else:
            _length += get_vector_length(_points[i], _points[j])
    return _length


def check_polys(pline: LWPolyline | Polyline, polys: list[LWPolyline | Polyline]) -> bool:
    """
    Функция check_polys принимает объект LWPolyline или Polyline и список полилиний и проверяет, есть ли уже в списке полилиния с такой же длиной (с учётом арок).

    :param pline: объект LWPolyline или Polyline
    :type pline: LWPolyline | Polyline
    :param polys: список полилиний
    :type polys: list[LWPolyline | Polyline]
    :return: True, если длина полилинии совпадает с длиной хотя бы одной полилинии в списке, False в противном случае
    :rtype: bool
    """
    _length: float = get_poly_length(pline)
    _llength: float = 0
    for p in polys:
        _llength = get_poly_length(p)
        if _length == _llength:
            return True
    return False


def get_min_coords(pline: LWPolyline | Polyline) -> tuple[float, float]:
    """
    Функция get_min_coords принимает объект LWPolyline или Polyline и возвращает кортеж из двух чисел: минимальной x-координаты и минимальной y-координаты.

    :param pline: объект LWPolyline или Polyline
    :type pline: LWPolyline | Polyline
    :return: кортеж из двух чисел: минимальной x-координаты и минимальной y-координаты
    :rtype: tuple[float, float]
    """
    _points: list[Sequence[float]] = []
    if isinstance(pline, LWPolyline):
        _points = pline.get_points()
    else:
        for v in pline.vertices:
            _points.append(v.format("xyseb"))
    _x = min(_points[i][0] for i in range(len(_points)))
    _y = min(_points[i][1] for i in range(len(_points)))
    return _x, _y


def get_max_coords(pline: LWPolyline | Polyline) -> tuple[float, float]:
    """
    Функция get_min_coords принимает объект LWPolyline или Polyline и возвращает кортеж из двух чисел: максимальной x-координаты и максимальной y-координаты.

    :param pline: объект LWPolyline или Polyline
    :type pline: LWPolyline | Polyline
    :return: кортеж из двух чисел: максимальной x-координаты и максимальной y-координаты
    :rtype: tuple[float, float]
    """
    _points: list[Sequence[float]] = []
    if isinstance(pline, LWPolyline):
        _points = pline.get_points()
    else:
        for v in pline.vertices:
            _points.append(v.format("xyseb"))
    _x = max(_points[i][0] for i in range(len(_points)))
    _y = max(_points[i][1] for i in range(len(_points)))
    return _x, _y


def nullify_coords(pline: LWPolyline | Polyline, x: float, y: float) -> LWPolyline | Polyline:
    """
    Функция nullify_coords принимает объект LWPolyline или Polyline и два числа (x и y) и нормализует координаты объекта LWPolyline, вычитая x и y из каждого x-координаты и y-координаты соответственно.

    :param pline: объект LWPolyline или Polyline
    :type pline: LWPolyline | Polyline
    :param x: число, которое вычитается из каждой x-координаты
    :type x: float
    :param y: число, которое вычитается из каждой y-координаты
    :type y: float
    :return: None
    :rtype: None
    """
    ucs = ezdxf.math.UCS(origin=(-x, -y, 0))
    return pline.transform(ucs.matrix)


def group_polys_by_details(
        poly: LWPolyline | Polyline,
        msp: Modelspace,
        blue_polys: list[LWPolyline | Polyline],
        green_polys: list[LWPolyline | Polyline],
        lblue_polys: list[LWPolyline | Polyline],
        yellow_polys: list[LWPolyline | Polyline],
) -> list[LWPolyline | Polyline]:
    """
    Функция группирует полилинии, попавшие в описываемый прямоугольник вокруг рассматриваемой полилинии.

    :param poly: полилиния, вокруг которой группируются другие полилинии
    :type poly: LWPolyline | Polyline
    :param msp: объект Modelspace, в котором ищут полилинии
    :type msp: Modelspace
    :param blue_polys: список полилиний, которые должны быть найдены
    :type blue_polys: list[LWPolyline | Polyline]
    :param green_polys: список полилиний, которые должны быть найдены
    :type green_polys: list[LWPolyline | Polyline]
    :param lblue_polys: список полилиний, которые должны быть найдены
    :type lblue_polys: list[LWPolyline | Polyline]
    :return: список полилиний, попавших в описываемый прямоугольник вокруг рассматриваемой полилинии
    :rtype: list[LWPolyline | Polyline]
    """
    maxs: tuple[float, float] = get_max_coords(poly)
    mins: tuple[float, float] = get_min_coords(poly)
    window: Window = select.Window(mins, maxs)
    group: list[LWPolyline | Polyline] = []
    for e in select.bbox_overlap(window, msp):
        if e not in blue_polys and e not in green_polys and e not in lblue_polys and e not in yellow_polys:
            continue
        if isinstance(e, LWPolyline | Polyline):
            group.append(e)
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

    center: list[float] = list(ezdxf.math.bulge_center(
        (x1, y1), (x2, y2), p1[4]))
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


def convert_poly_to_PointList(poly: LWPolyline | Polyline) -> tuple[list, list]:
    """
    Функция преобразует полилинию в список точек с указанием, какие точки являются вершинами дуг.

    :param poly: полилиния, которую нужно преобразовать
    :type poly: LWPolyline | Polyline
    :return: список точек и список индексов точек, являющихся вершинами дуг
    :rtype: tuple[list, list]
    """
    ifc_points: list[tuple[float, float]] = []
    arc_middles: list[int] = []
    dxf_points: list[Sequence[float]] = []
    if isinstance(poly, LWPolyline):
        dxf_points = poly.get_points()
    else:
        for v in poly.vertices:
            dxf_points.append(v.format("xyseb"))
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
        polys: list[LWPolyline | Polyline],
        builder: ShapeBuilder,
        blue_polys: list[LWPolyline | Polyline],
        lblue_polys: list[LWPolyline | Polyline],
        green_polys: list[LWPolyline | Polyline],
        yellow_polys: list[LWPolyline | Polyline],
        name: str = ""
) -> list[entity_instance]:
    """
    Функция преобразует полилинии в профили.

    :param polys: список полилиний, которые нужно преобразовать
    :type polys: list[LWPolyline | Polyline]
    :param builder: объект, который создает профили
    :type builder: entity_instance
    :param blue_polys: список полилиний, которые должны быть частью профиля
    :type blue_polys: list[LWPolyline | Polyline]
    :param lblue_polys: список полилиний, которые должны быть частью профиля
    :type lblue_polys: list[LWPolyline | Polyline]
    :param green_polys: список полилиний, которые должны быть частью профиля
    :type green_polys: list[LWPolyline | Polyline]
    :param yellow_polys: список полилиний, которые должны быть частью профиля
    :type yellow_polys: list[LWPolyline | Polyline]
    :param name: имя профиля
    :type name: str
    :return: список профилей
    :rtype: list[entity_instance]
    """
    profiles: list[entity_instance] = []
    blue_curves: dict[str, entity_instance] = dict()
    lblue_curves: dict[str, entity_instance] = dict()
    green_curves: dict[str, entity_instance] = dict()
    yellow_curves: dict[str, entity_instance] = dict()
    for p in polys:
        ifc_points, arc_middles = convert_poly_to_PointList(p)
        curve = builder.polyline(
            ifc_points, arc_points=arc_middles, closed=True)
        curve.SelfIntersect = False
        if p in blue_polys:
            blue_curves[p.dxf.handle] = curve
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
