
from re import L
from src.dxf import convert_poly_to_Polygon, get_poly_length, get_centroid, nullify_coords

import ezdxf
from ezdxf.document import Drawing
from ezdxf.entities.layer import Layer
from ezdxf.entities.lwpolyline import LWPolyline
from ezdxf.entities.polyline import Polyline
from ezdxf.layouts.layout import Modelspace
from ezdxf.math import BoundingBox

import matplotlib.pylab as plt

from shapely import affinity, plotting, Polygon, MultiPoint


class Settings:
    def __init__(
            self,
            thickness: int = 18,
            outerColor: int = 5,
            innerColor: int = 4,
            millColor: int = 3,
            sheetBoundaryColor: int = 1
    ):
        self.thickness: int = thickness
        self.outerColor: int = outerColor
        self.innerColor: int = innerColor
        self.millColor: int = millColor
        self.sheetBoundaryColor: int = sheetBoundaryColor


class Path:
    def __init__(self, polyline: LWPolyline | Polyline = None):
        self.polyline: LWPolyline | Polyline = polyline


class DrillPath(Path):
    def __init__(self, polyline: LWPolyline | Polyline = None):
        super().__init__(polyline)
        self.length: float = self.setLength()
        self.bbox: BoundingBox = self.setBbox()
        self.centroidAbs: tuple[float, float] = self.setCentroidAbs()
        self.centroidLoc: tuple[float, float] = None
        self.polylineLoc: LWPolyline | Polyline = None

    def setLength(self) -> float:
        return get_poly_length(self.polyline)

    def setBbox(self) -> BoundingBox:
        return ezdxf.bbox.extents([self.polyline])

    def setPolylineLoc(self, x: float = 0.0, y: float = 0.0) -> None:
        _locPoly = self.polyline.copy()
        nullify_coords(_locPoly, x, y)
        self.polylineLoc = _locPoly

    def setCentroidAbs(self) -> tuple[float, float]:
        return get_centroid([self.polyline])

    def setCentroidLoc(self, x: float = 0.0, y: float = 0.0) -> None:
        _locPoly = self.polyline.copy()
        nullify_coords(_locPoly, x, y)
        self.centroidLoc = get_centroid([_locPoly])


class SheetBoundaryPath(Path):
    def __init__(self, polyline: LWPolyline | Polyline = None):
        super().__init__(polyline)


class PathFormer:
    def __init__(self, settings: Settings = None, dwg: Drawing = None):
        self.settings: Settings = settings
        self.dwg: Drawing = dwg
        self.outerDrillPaths: list[DrillPath] = []
        self.innerDrillPaths: list[DrillPath] = []
        self.shallowDrillPaths: list[DrillPath] = []
        self.sheetBoundaryPaths: list[SheetBoundaryPath] = []
        self.formPaths()

    def formPaths(self) -> None:
        _msp: Modelspace = self.dwg.modelspace()
        for e in _msp.query("LWPOLYLINE POLYLINE"):
            _entityLayer: str = e.dxf.layer
            _layer: Layer = self.dwg.layers.get(_entityLayer)
            _color: int = _layer.color
            if _color == self.settings.outerColor:
                self.outerDrillPaths.append(DrillPath(e))
            if _color == self.settings.innerColor:
                self.innerDrillPaths.append(DrillPath(e))
            if _color == self.settings.millColor:
                self.shallowDrillPaths.append(DrillPath(e))

    def getOuterDrillPaths(self) -> list[DrillPath]:
        return self.outerDrillPaths

    def getInnerDrillPaths(self) -> list[DrillPath]:
        return self.innerDrillPaths

    def getShallowDrillPaths(self) -> list[DrillPath]:
        return self.shallowDrillPaths


class Detail:
    def __init__(
            self,
            contour: DrillPath = None,
            cuts: list[DrillPath] = None,
            mills: list[DrillPath] = None
    ):
        self.contour: DrillPath = contour
        self.cuts: list[DrillPath] = cuts
        self.mills: list[DrillPath] = mills
        self.drillLength: float = self.calculateDrillLength()
        self.updateLocsForAllDrills()
        self.millsCentroidShape: MultiPoint = self.formMillsCentroidShape()

    def calculateDrillLength(self) -> float:
        _length = self.contour.length
        _length += sum([_drill.length for _drill in self.cuts])
        _length += sum([_drill.length for _drill in self.mills])
        return _length

    def updateLocsForAllDrills(self) -> None:
        _x, _y = self.contour.bbox.center[0], self.contour.bbox.center[1]
        _drills = [self.contour] + self.cuts + self.mills
        for _drill in _drills:
            _drill.setCentroidLoc(_x, _y)
            _drill.setPolylineLoc(_x, _y)

    def formMillsCentroidShape(self) -> MultiPoint:
        _centroids: list[tuple[float, float]] = [_drill.centroidLoc for _drill in self.mills]
        _mp = MultiPoint(_centroids)
        return _mp


class PathCombiner:
    def __init__(
            self,
            contour: Path | None = None,
            consideredPaths: list[Path] | None = None
    ):
        self.contour: Path = contour
        self.consideredPaths: list[Path] = consideredPaths
        self.combinedPaths: list[Path] = self.combinePaths()

    def setContour(self, contour: Path = None) -> None:
        self.contour: Path = contour
        self.combinedPaths = self.combinePaths()

    def setConsideredPaths(self, paths: list[Path] = None) -> None:
        self.consideredPaths: list[Path] = paths
        self.combinedPaths = self.combinePaths()

    def combinePaths(self) -> list[Path]:
        if self.contour is None or self.consideredPaths is None:
            return None
        _contourPolygon: Polygon = convert_poly_to_Polygon(self.contour.polyline)
        _outerPolygon: Polygon = _contourPolygon.buffer(1)
        _innerPolygon: Polygon = _contourPolygon.buffer(-1)
        _filteredPaths: list[Path] = []
        for path in self.consideredPaths:
            _pathPolygon: Polygon = convert_poly_to_Polygon(path.polyline)
            if _pathPolygon.intersects(_outerPolygon) or _pathPolygon.intersects(_innerPolygon):
                _filteredPaths.append(path)
        return _filteredPaths

    def getCombinedPaths(self) -> list[DrillPath]:
        return self.combinedPaths


class Sheet:
    def __init__(self, settings: Settings = None, dwg: Drawing = None):
        self.settings: Settings = settings
        self.dwg: Drawing = dwg
        self.thickness: float = self.settings.thickness
        self.width: float = 0.0
        self.length: float = 0.0
        self.details: list[Detail] = []
        self.pathFormer: PathFormer = PathFormer(settings, dwg)
        self.outerDrillPaths: list[DrillPath] = self.pathFormer.getOuterDrillPaths()
        self.innerDrillPaths: list[DrillPath] = self.pathFormer.getInnerDrillPaths()
        self.shallowDrillPaths: list[DrillPath] = self.pathFormer.getShallowDrillPaths()
        self.formDetails()

    def formDetails(self) -> None:
        _pathCombiner: PathCombiner = PathCombiner()
        for dp in self.outerDrillPaths:
            _pathCombiner.setContour(dp)
            _pathCombiner.setConsideredPaths(self.innerDrillPaths)
            _cuts = _pathCombiner.getCombinedPaths()
            _pathCombiner.setConsideredPaths(self.shallowDrillPaths)
            _mills = _pathCombiner.getCombinedPaths()
            _detail: Detail = Detail(
                contour=dp,
                cuts=_cuts,
                mills=_mills
            )
            self.details.append(_detail)

    def getDetails(self) -> list[Detail]:
        return self.details


class Template:
    def __init__(
        self,
        name: str = None,
        contour: DrillPath = None,
        cuts: list[DrillPath] = None,
        mills: list[DrillPath] = None,
        drillLength: float = None,
        millsCentroidShape: MultiPoint = None
    ):
        self.name: str = name
        self.details: list[Detail] = []
        self.contour: DrillPath = contour
        self.cuts: list[DrillPath] = cuts
        self.mills: list[DrillPath] = mills
        self.drillLength: float = drillLength
        self.millsCentroidShape: MultiPoint = millsCentroidShape

    def addDetail(self, detail: Detail) -> None:
        self.details.append(detail)


class DetailComparer:
    def __init__(self, details: list[Detail] = None):
        self.details: list[Detail] = details
        self.templates: list[Template] = []
        self.goThroughDetails()

    def goThroughDetails(self) -> None:
        for _detail in self.details:
            self.compareDetailAgainstTemplates(_detail)
    
    def compareDetailAgainstTemplates(self, detail: Detail) -> None:
        for _template in self.templates:
            _checkResult = self.checkDetailAgainstTemplate(detail, _template)
            if _checkResult:
                _template.addDetail(detail)
                return
        _newTemplate = Template(
            name = str(len(self.templates) + 1),
            contour = detail.contour,
            cuts = detail.cuts,
            mills = detail.mills,
            drillLength = detail.drillLength,
            millsCentroidShape = detail.millsCentroidShape
        )
        self.templates.append(_newTemplate)
    
    def checkDetailAgainstTemplate(self, detail: Detail, template: Template) -> bool:
        _lengthCheck = detail.drillLength == template.drillLength
        _millsCheck = True
        if _lengthCheck and len(detail.mills) > 0:
            _millsCheck = self.checkShapes(
                detail.millsCentroidShape,
                template.millsCentroidShape,
                [0, 0]
                )
        return _lengthCheck and _millsCheck
    
    def checkShapes(self, shape1: MultiPoint, shape2: MultiPoint, center: tuple[float, float]) -> bool:
        if shape1.equals_exact(shape2, 1): return True
        # plotting.plot_points(shape2)
        # plotting.plot_points(shape1)
        # plt.show()
        _shape11: MultiPoint = affinity.rotate(shape1, 90, center)
        plotting.plot_points(shape2)
        plotting.plot_points(_shape11)
        plt.show()
        if _shape11.equals_exact(shape2, 1): return True
        _shape12: MultiPoint = affinity.rotate(shape1, 180, center)
        plotting.plot_points(shape2)
        plotting.plot_points(_shape12)
        plt.show()
        if _shape12.equals_exact(shape2, 1): return True
        _shape13: MultiPoint = affinity.rotate(shape1, 270, center)
        plotting.plot_points(shape2)
        plotting.plot_points(_shape13)
        plt.show()
        if _shape13.equals_exact(shape2, 1): return True
        return False




class Block:
    def __init__(self, name: str = None, sheets: list[Sheet] = None):
        self.name: str = name
        self.sheets: list[Sheet] = sheets
        self.templates: list[Template] = self.formTemplates()

    def formTemplates(self) -> list[Template]:
        _detailComparer: DetailComparer = DetailComparer(self.sheets[0].getDetails())
        _templates: list[Template] = _detailComparer.templates.copy()
        for _template in _templates:
            _template.name = f"{self.name}/{_template.name}"
        return _templates
