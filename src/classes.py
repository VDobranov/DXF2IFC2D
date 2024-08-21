
from src.ifc import create_Plate, create_PlateType, gather_LocalPlacements

from src.dxf import convert_poly_to_PointList, convert_poly_to_Polygon, get_poly_length, get_centroid, nullify_coords

import copy

import ezdxf
from ezdxf.document import Drawing
from ezdxf.entities.layer import Layer
from ezdxf.entities.lwpolyline import LWPolyline
from ezdxf.entities.polyline import Polyline
from ezdxf.layouts.layout import Modelspace
from ezdxf.math import BoundingBox

import ifcopenshell as ifcos
from ifcopenshell import entity_instance
from ifcopenshell.util import representation
from ifcopenshell.util.shape_builder import ShapeBuilder

# import matplotlib.pylab as plt

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


class Model:
    def __init__(self, settings: Settings = None, ifcFile: ifcos.file = None):
        self.ifcFile: ifcos.file = ifcFile
        self.settings: Settings = settings
        self.builder: ShapeBuilder = ShapeBuilder(ifcFile)
        self.body: entity_instance | None = representation.get_context(ifcFile, "Model", "Body", "MODEL_VIEW")
        self.history: entity_instance = ifcFile.by_type("IfcOwnerHistory")[0]
        self.site: entity_instance = ifcFile.by_type('IfcSite')[0]
        self.storey: entity_instance = ifcFile.by_type('IfcBuildingStorey')[0]
        self.origin: entity_instance = ifcFile.by_type('IfcCartesianPoint')[0]
        self.placement3d: entity_instance = ifcFile.by_type("IfcAxis2Placement3D")[0]
        self.placement2d: entity_instance = ifcFile.by_type("IfcAxis2Placement2D")[0]
        for dir in ifcFile.by_type("IfcDirection"):
            if list(dir.DirectionRatios) == [1, 0, 0]:
                self.dir_x: entity_instance = dir
                break
        for dir in ifcFile.by_type("IfcDirection"):
            if list(dir.DirectionRatios) == [0, 1, 0]:
                self.dir_y: entity_instance = dir
                break
        for dir in ifcFile.by_type("IfcDirection"):
            if list(dir.DirectionRatios) == [0, 0, 1]:
                self.dir_z: entity_instance = dir
                break
        self.local_placements: dict[str, entity_instance] = gather_LocalPlacements(ifcFile)


class Path:
    def __init__(self, polyline: LWPolyline | Polyline = None):
        self.polyline: LWPolyline | Polyline = polyline


class DrillPath(Path):
    def __init__(self, polyline: LWPolyline | Polyline = None):
        super().__init__(polyline)
        self.length: float = self.setLength()
        self.bbox: BoundingBox = self.setBbox()
        self.centroid: tuple[float, float] = self.setCentroid()

    def setLength(self) -> float:
        return get_poly_length(self.polyline)

    def setBbox(self) -> BoundingBox:
        return ezdxf.bbox.extents([self.polyline])

    def setCentroid(self) -> tuple[float, float]:
        return get_centroid([self.polyline])


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
        self.contourLoc: DrillPath = self.normalizeDrillPath(self.contour)
        self.cutsLoc: list[DrillPath] = [self.normalizeDrillPath(c) for c in self.cuts]
        self.millsLoc: list[DrillPath] = [self.normalizeDrillPath(m) for m in self.mills]
        self.millsCentroidShape: MultiPoint = self.formMillsCentroidShape()

    def calculateDrillLength(self) -> float:
        _length = self.contour.length
        _length += sum([_drill.length for _drill in self.cuts])
        _length += sum([_drill.length for _drill in self.mills])
        _length = round(_length, 3)
        return _length

    def normalizeDrillPath(self, drillPath: DrillPath) -> DrillPath:
        _x, _y = self.contour.bbox.center[0], self.contour.bbox.center[1]
        _drillPathPolyline = drillPath.polyline.copy()
        nullify_coords(_drillPathPolyline, _x, _y)
        _drillPath = DrillPath(_drillPathPolyline)
        return _drillPath

    def formMillsCentroidShape(self) -> MultiPoint:
        _centroids: list[tuple[float, float]] = [_drill.centroid for _drill in self.millsLoc]
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
        builder: ShapeBuilder = None,
        name: str = None,
        contour: DrillPath = None,
        cuts: list[DrillPath] = None,
        mills: list[DrillPath] = None,
        drillLength: float = None,
        millsCentroidShape: MultiPoint = None
    ):
        self.builder: ShapeBuilder = builder
        self.name: str = name
        self.details: list[Detail] = []
        self.contour: DrillPath = contour
        self.cuts: list[DrillPath] = cuts
        self.mills: list[DrillPath] = mills
        self.drillLength: float = drillLength
        self.millsCentroidShape: MultiPoint = millsCentroidShape
        self.cuttingThroughProfile: entity_instance = self.createCuttingThroughProfile()
        self.millingProfiles: list[entity_instance] = self.createMillingProfile()

    def addDetail(self, detail: Detail) -> None:
        self.details.append(detail)

    def createCuttingThroughProfile(self) -> entity_instance:
        _outerCurvePoints: tuple[list[tuple[float, float]], list[int]] = convert_poly_to_PointList(self.contour.polyline)
        _outerCurve = Curve(self.builder, _outerCurvePoints[0], _outerCurvePoints[1]).makeIfcCurve()
        _innerCurves: list[entity_instance] = []
        for cut in self.cuts:
            _innerCurvePoints: tuple[list[tuple[float, float]], list[int]] = convert_poly_to_PointList(cut.polyline)
            _innerCurve = Curve(self.builder, _innerCurvePoints[0], _innerCurvePoints[1]).makeIfcCurve()
            _innerCurves.append(_innerCurve)
        _profile = Profile(
            builder=self.builder,
            name=f"{self.name}_cutting",
            outer_curve=_outerCurve,
            inner_curves=_innerCurves,
        )
        return _profile.makeIfcProfile()

    def createMillingProfile(self) -> list[entity_instance]:
        _profiles: list[entity_instance] = []
        for mill in self.mills:
            _outerCurvePoints: tuple[list[tuple[float, float]], list[int]] = convert_poly_to_PointList(mill.polyline)
            _outerCurve = Curve(self.builder, _outerCurvePoints[0], _outerCurvePoints[1]).makeIfcCurve()
            _profile = Profile(
                builder=self.builder,
                name=f"{self.name}_milling_{len(_profiles) + 1}",
                outer_curve=_outerCurve
            ).makeIfcProfile()
            _profiles.append(_profile)
        return _profiles


class DetailComparer:
    def __init__(
        self,
        builder: ShapeBuilder = None,
        blockName: str = None,
        details: list[Detail] = None
    ):
        self.builder: ShapeBuilder = builder
        self.blockName: str = blockName
        self.details: list[Detail] = details
        self.templates: list[Template] = []
        self.goThroughDetails()

    def goThroughDetails(self) -> None:
        for _detail in self.details:
            self.recognizeTemplateForDetail(_detail)

    def recognizeTemplateForDetail(self, detail: Detail) -> None:
        for _template in self.templates:
            _checkResult = self.checkDetailAgainstTemplate(detail, _template)
            if _checkResult:
                _template.addDetail(detail)
                return
        _newTemplate = Template(
            builder=self.builder,
            name=f"{self.blockName}/{len(self.templates) + 1}",
            contour=detail.contourLoc,
            cuts=detail.cutsLoc,
            mills=detail.millsLoc,
            drillLength=detail.drillLength,
            millsCentroidShape=detail.millsCentroidShape
        )
        _newTemplate.addDetail(detail)
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
        shape1 = self.sortMultiPoint(shape1)
        shape2 = self.sortMultiPoint(shape2)
        if shape1.equals_exact(shape2, 1):
            return True
        # plotting.plot_points(shape2)
        # plotting.plot_points(shape1)
        # plt.show()
        _shape11: MultiPoint = affinity.rotate(shape1, 90, center)
        _shape11 = self.sortMultiPoint(_shape11)
        if _shape11.equals_exact(shape2, 1):
            return True
        _shape12: MultiPoint = affinity.rotate(shape1, 180, center)
        _shape12 = self.sortMultiPoint(_shape12)
        if _shape12.equals_exact(shape2, 1):
            return True
        _shape13: MultiPoint = affinity.rotate(shape1, 270, center)
        _shape13 = self.sortMultiPoint(_shape13)
        if _shape13.equals_exact(shape2, 1):
            return True
        return False

    @staticmethod
    def sortMultiPoint(shape: MultiPoint) -> MultiPoint:
        _shapeCoords: list[list[float]] = [list([round(c, 0) for c in p.coords[0]]) for p in shape.geoms]
        _shapeCoords = sorted(_shapeCoords)
        return MultiPoint(_shapeCoords)


class Block:
    def __init__(
        self,
        settings: Settings = None,
        model: Model = None,
        name: str = None,
        sheets: list[Sheet] = None
    ):
        self.settings: Settings = settings
        self.model: Model = model
        self.name: str = name
        self.sheets: list[Sheet] = sheets
        self.templates: list[Template] = self.formTemplates()
        self.plateTypes: list[PlateType] = self.makePlateTypes()
        self.plates: list[Plate] = self.makePlates()

    def formTemplates(self) -> list[Template]:
        _detailComparer: DetailComparer = DetailComparer(self.model.builder, self.name, self.sheets[0].getDetails())
        return _detailComparer.templates

    def makePlateTypes(self) -> None:
        _types: list[entity_instance] = []
        for template in self.templates:
            _types.append(PlateType(self.settings, self.model, template))
        return _types
    
    def makePlates(self) -> None:
        _plates: list[entity_instance] = []
        for plateType in self.plateTypes:
            for _ in range(len(plateType.template.details)):
                _plates.append(Plate(self.model, plateType))
        return _plates


class Profile:
    def __init__(
        self,
        builder: ShapeBuilder = None,
        name: str = None,
        outer_curve: entity_instance = None,
        inner_curves: list[entity_instance] = []
    ):
        self.builder: ShapeBuilder = builder
        self.name: str = name
        self.outer_curve: Curve = outer_curve
        self.inner_curves: list[Curve] = inner_curves

    def makeIfcProfile(self) -> entity_instance:
        _profile = self.builder.profile(
            name=self.name,
            outer_curve=self.outer_curve,
            inner_curves=self.inner_curves
        )
        return _profile


class Curve:
    def __init__(
        self,
        builder: ShapeBuilder = None,
        ifc_points: list[tuple[float, float]] = None,
        arc_middles: list[int] = None
    ):
        self.builder: ShapeBuilder = builder
        self.ifc_points: list[tuple[float, float]] = ifc_points
        self.arc_middles: list[int] = arc_middles

    def makeIfcCurve(self) -> entity_instance:
        _curve = self.builder.polyline(
            points=self.ifc_points,
            arc_points=self.arc_middles,
            closed=True
        )
        _curve.SelfIntersect = False
        return _curve


class PlateType:
    def __init__(
        self,
        settings: Settings = None,
        model: Model = None,
        template: Template = None
    ):
        self.settings: Settings = settings
        self.model: Model = model
        self.template: Template = template
        self.ifcPlateType: entity_instance = self.makeIfcPlateType()
    
    def makeIfcPlateType(self) -> entity_instance:
        _profiles: list[entity_instance] = [self.template.cuttingThroughProfile] + self.template.millingProfiles
        _type: entity_instance = create_PlateType(
            model=self.model.ifcFile,
            body=self.model.body,
            origin=self.model.origin,
            local_placements=self.model.local_placements,
            dir_z=self.model.dir_z,
            dir_x=self.model.dir_x,
            profiles=_profiles,
            name=self.template.name,
            THICKNESS=self.settings.thickness
        )
        return _type

class Plate:
    def __init__(
        self,
        model: Model = None,
        type: PlateType = None
    ):
        self.model: Model = model
        self.type: PlateType = type
        self.ifcPlate: entity_instance = self.makeIfcPlate()
    
    def makeIfcPlate(self) -> entity_instance:
        _plate: entity_instance = create_Plate(
            model=self.model.ifcFile,
            storey=self.model.storey,
            name=self.type.template.name,
            type=self.type.ifcPlateType
        )
        return _plate
