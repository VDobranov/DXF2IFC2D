import ifcopenshell as ios
from ifcopenshell import entity_instance, validate
from ifcopenshell.api import run
from ifcopenshell.util import representation
from ifcopenshell.util.shape_builder import ShapeBuilder


def check_CartesianPoint(model: ios.file, coords: list[float]) -> bool:
    """
    Функция check_CartesianPoint проверяет, существует ли уже в модели объект IfcCartesianPoint с заданными координатами.

    :param coords: список координат
    :type coords: list[float]
    :return: True, если объект существует, False в противном случае
    :rtype: bool
    """
    for p in model.by_type("IfcCartesianPoint"):
        if coords == list(p.Coordinates):
            return True
    return False


def create_CartesianPoint(model: ios.file, coords: list[float]) -> entity_instance:  # type: ignore
    """
    Функция create_CartesianPoint создает объект IfcCartesianPoint с заданными координатами.

    :param coords: список координат
    :type coords: list[float]
    :return: объект IfcCartesianPoint
    :rtype: entity_instance
    """
    found = check_CartesianPoint(model, coords)
    if found:
        for p in model.by_type("IfcCartesianPoint"):
            if coords == list(p.Coordinates):
                return p
    else:
        return model.createIfcCartesianPoint(coords)


def check_Direction(model: ios.file, d_ratios: list[float]) -> bool:
    for p in model.by_type("IfcDirection"):
        if d_ratios == list(p.DirectionRatios):
            return True
    return False

def create_Direction(model: ios.file, d_ratios: list[float]) -> entity_instance:  # type: ignore
    found = check_Direction(model, d_ratios)
    if found:
        for p in model.by_type("IfcDirection"):
            if d_ratios == list(p.DirectionRatios):
                return p
    else:
        return model.createIfcDirection(d_ratios)


def check_Axis2Placement2D(model: ios.file, point: entity_instance, dir_x: entity_instance) -> bool:
    """
    Функция check_Axis2Placement2D проверяет, существует ли уже в модели объект IfcAxis2Placement2D с заданными координатами и направлением оси x.

    :param point: объект IfcCartesianPoint, представляющий координаты
    :type point: entity_instance
    :param dir_x: объект IfcDirection, представляющий направление оси x
    :type dir_x: entity_instance
    :return: True, если объект существует, False в противном случае
    :rtype: bool
    """
    for p in model.by_type("IfcAxis2Placement2D"):
        if point == p.Location and dir_x == p.RefDirection:
            return True
    return False


def create_Axis2Placement2D(model: ios.file, point: entity_instance, dir_x: entity_instance) -> entity_instance:  # type: ignore
    found = check_Axis2Placement2D(model, point, dir_x)
    if found:
        for p in model.by_type("IfcAxis2Placement2D"):
            if point == p.Location and dir_x == p.RefDirection:
                return p
    else:
        return model.createIfcAxis2Placement2D(point, dir_x)


def check_Axis2Placement3D(model: ios.file, point: entity_instance, dir_z: entity_instance, dir_x: entity_instance) -> bool:
    """
    Функция check_Axis2Placement3D проверяет, существует ли уже в модели объект IfcAxis2Placement3D с заданными координатами, направлением оси z и направлением оси x.

    :param point: объект IfcCartesianPoint, представляющий координаты
    :type point: entity_instance
    :param dir_z: объект IfcDirection, представляющий направление оси z
    :type dir_z: entity_instance
    :param dir_x: объект IfcDirection, представляющий направление оси x
    :type dir_x: entity_instance
    :return: True, если объект существует, False в противном случае
    :rtype: bool
    """
    for p in model.by_type("IfcAxis2Placement3D"):
        if point == p.Location and dir_z == p.Axis and dir_x == p.RefDirection:
            return True
    return False


def create_Axis2Placement3D(model: ios.file, point: entity_instance, dir_z: entity_instance, dir_x: entity_instance) -> entity_instance:  # type: ignore
    '''
    Функция create_Axis2Placement3D создает объект IfcAxis2Placement3D с заданными координатами, направлением оси z и направлением оси x. Если такой объект уже существует в модели, функция возвращает его. В противном случае, функция создает новый объект и возвращает его.

    :param point: объект IfcCartesianPoint, представляющий координаты
    :type point: entity_instance
    :param dir_z: объект IfcDirection, представляющий направление оси z
    :type dir_z: entity_instance
    :param dir_x: объект IfcDirection, представляющий направление оси x
    :type dir_x: entity_instance
    :return: объект IfcAxis2Placement3D
    :rtype: entity_instance
    '''
    found = check_Axis2Placement3D(model, point, dir_z, dir_x)
    if found:
        for p in model.by_type("IfcAxis2Placement3D"):
            if point == p.Location and dir_z == p.Axis and dir_x == p.RefDirection:
                return p
    else:
        return model.createIfcAxis2Placement3D(point, dir_z, dir_x)


def gather_LocalPlacements(model: ios.file) -> dict[str, entity_instance]:
    '''
    Этот код создает словарь local_placements, где ключами являются строки, сформированные из идентификаторов объектов IfcLocalPlacement, и значениями - сами объекты IfcLocalPlacement. Он проходит по всем объектам IfcLocalPlacement в модели и для каждого объекта формирует строку, содержащую идентификаторы объектов, связанных с этим объектом IfcLocalPlacement, и добавляет эту строку в словарь как ключ с соответствующим объектом IfcLocalPlacement в качестве значения.
    '''
    local_placements: dict[str, entity_instance] = dict()
    for lp in model.by_type("IfcLocalPlacement"):
        name1: str
        if isinstance(lp.PlacementRelTo, entity_instance):
            _rel = lp.PlacementRelTo.RelativePlacement
            name1 = f"{_rel.Location.id()}-{_rel.Axis.id()}-{_rel.RefDirection.id()}"
        else:
            name1 = "None"
        _rel = lp.RelativePlacement
        name2: str = f"{_rel.Location.id()}-{_rel.Axis.id()}-{_rel.RefDirection.id()}"
        name: str = f"{name1}/{name2}"
        local_placements[name] = lp
    return local_placements


def create_LocalPlacement(
        model: ios.file,
        local_placements: dict[str, entity_instance],
        point: entity_instance,
        dir_z: entity_instance,
        dir_x: entity_instance,
        placement_rel: entity_instance | None = None
) -> entity_instance:
    '''
    Этот код создает объект IfcLocalPlacement на основе заданных параметров. Если точка не задана, используется точка по умолчанию. Если объект IfcLocalPlacement уже существует в словаре local_placements, он берется из словаря. В противном случае, создается новый объект IfcLocalPlacement и добавляется в словарь. Затем возвращается созданный или существующий объект IfcLocalPlacement.
    1. Проверяем, задана ли точка. Если нет, присваиваем ей значение по умолчанию.
    2. Если объект IfcLocalPlacement связан с другим объектом (placement_rel), формируем строку, содержащую идентификаторы этого объекта. Если объект IfcLocalPlacement не связан с другим объектом, в строку включается строка "None".
    3. Формируем уникальное имя для объекта IfcLocalPlacement, используя идентификаторы объектов, связанных с ним.
    4. Проверяем, есть ли уже такой объект IfcLocalPlacement в словаре local_placements. Если нет, создаем новый объект и добавляем его в словарь. Если есть, берем существующий объект из словаря.
    5. Возвращаем созданный или существующий объект IfcLocalPlacement.
    '''
    name1: str
    if isinstance(placement_rel, entity_instance):
        name1 = f"{placement_rel.Location.id()}-{placement_rel.Axis.id()}-{placement_rel.RefDirection.id()}"
    else:
        name1 = "None"
    name2: str = f"{point.id()}-{dir_z.id()}-{dir_x.id()}"
    name: str = f"{name1}/{name2}"
    if name not in local_placements:
        placement = create_Axis2Placement3D(model, point, dir_z, dir_x)
        local_placement = model.createIfcLocalPlacement(placement_rel, placement)
        local_placements[name] = local_placement
    else:
        local_placement = local_placements[name]
    return local_placement


def create_IfcExtrudedAreaSolid(
        model: ios.file,
        sweptArea: entity_instance,
        depth: float,
        dir_z: entity_instance,
        placement: entity_instance | None = None
) -> entity_instance:
    '''
    Функция create_IfcExtrudedAreaSolid создает объект IfcExtrudedAreaSolid с заданными параметрами. Она принимает модель IFC, объект sweptArea, глубину depth, объект dir_z и объект placement в качестве аргументов. Возвращает созданный объект IfcExtrudedAreaSolid.
    '''
    return model.createIfcExtrudedAreaSolid(sweptArea, placement, dir_z, depth)


def create_PlateType(
        model: ios.file,
        body: entity_instance | None,
        origin: entity_instance,
        local_placements: dict[str, entity_instance],
        profiles: list[entity_instance],
        name: str,
        dir_z: entity_instance,
        dir_x: entity_instance,
        THICKNESS: float = 1.
):
    '''
    Функция create_PlateType создает тип продукта IfcPlateType с заданными параметрами. Она принимает модель IFC, объект sweptArea, глубину depth, объект dir_z и объект placement в качестве аргументов. Возвращает созданный объект IfcPlateType.
    '''
    _cuts: list[entity_instance] = []
    _sheet: entity_instance
    for profile in profiles:
        _point: entity_instance
        _placement: entity_instance
        if "milling" in profile.ProfileName:
            _point = create_CartesianPoint(model, [0., 0., THICKNESS/2])
            _placement = create_Axis2Placement3D(model, _point, dir_z, dir_x)
            _cuts.append(create_IfcExtrudedAreaSolid(model=model, sweptArea=profile,
                         depth=THICKNESS/2+1, dir_z=dir_z, placement=_placement))
        elif "letter" in profile.ProfileName:
            _point = create_CartesianPoint(model, [0., 0., THICKNESS-1.])
            _placement = create_Axis2Placement3D(model, _point, dir_z, dir_x)
            _cuts.append(create_IfcExtrudedAreaSolid(model=model, sweptArea=profile,
                         depth=2, dir_z=dir_z, placement=_placement))
        else:
            _sheet = create_IfcExtrudedAreaSolid(model=model, sweptArea=profile, depth=THICKNESS, dir_z=dir_z)
    for cut in _cuts:
        _sheet = model.createIfcBooleanResult(Operator="DIFFERENCE", FirstOperand=_sheet, SecondOperand=cut)
    _rtype: str = "SweptSolid"
    if _sheet.is_a("IfcBooleanResult"):
        _rtype = "CSG"
    representation = model.createIfcShapeRepresentation(
        ContextOfItems=body, RepresentationIdentifier="Body", RepresentationType=_rtype, Items=[_sheet])
    local_placement = create_LocalPlacement(
        model=model, local_placements=local_placements, point=origin, dir_z=dir_z, dir_x=dir_x)
    placement = local_placement.RelativePlacement
    representationmap = model.createIfcRepresentationMap(placement, representation)

    plate_type = run("root.create_entity", model, ifc_class="IfcPlateType", predefined_type="PART", name=name)
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


def create_Plate(model: ios.file, storey: entity_instance, name: str = "Default Name", type: entity_instance | None = None):
    '''
    Функция create_Plate создает объект IfcPlate с заданными параметрами. Она принимает модель IFC, объект storey, имя name и объект type в качестве аргументов. Возвращает созданный объект IfcPlate.
    '''
    plate = run("root.create_entity", model, ifc_class="IfcPlate")
    run("geometry.edit_object_placement", model, product=plate)
    run("spatial.assign_container", model, products=[plate], relating_structure=storey)
    if type:
        run("type.assign_type", model, related_objects=[plate], relating_type=type)
        plate.Name = type.Name
    else:
        plate.Name = name
    return plate
