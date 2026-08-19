"""H3 grid construction clipped to a municipal boundary."""

from __future__ import annotations

from typing import Any


def _cells_for_geometry(geometry: Any, resolution: int) -> set[str]:
    import h3
    from shapely.geometry import mapping

    geo = mapping(geometry)
    cells: set[str] = set()
    polygons = geo["coordinates"] if geo["type"] == "MultiPolygon" else [geo["coordinates"]]
    for coordinates in polygons:
        exterior = [(float(y), float(x)) for x, y in coordinates[0]]
        holes = [[(float(y), float(x)) for x, y in ring] for ring in coordinates[1:]]
        if hasattr(h3, "polygon_to_cells") and hasattr(h3, "LatLngPoly"):
            cells.update(map(str, h3.polygon_to_cells(h3.LatLngPoly(exterior, *holes), resolution)))
        elif hasattr(h3, "polyfill"):
            cells.update(map(str, h3.polyfill(geo, resolution, geo_json_conformant=True)))
    # H3 center containment can omit very small/sliver polygons. Always include the
    # representative point's cell so a valid boundary produces a useful grid.
    point = geometry.representative_point()
    if hasattr(h3, "latlng_to_cell"):
        cells.add(str(h3.latlng_to_cell(point.y, point.x, resolution)))
    else:
        cells.add(str(h3.geo_to_h3(point.y, point.x, resolution)))
    return cells


def _cell_polygon(cell: str) -> Any:
    import h3
    from shapely.geometry import Polygon

    boundary = h3.cell_to_boundary(cell) if hasattr(h3, "cell_to_boundary") else h3.h3_to_geo_boundary(cell)
    return Polygon([(float(lng), float(lat)) for lat, lng in boundary])


def build_h3_grid(boundary: Any, resolution: int = 8) -> Any:
    """Return sorted H3 cells clipped to *boundary* as an EPSG:4326 GeoDataFrame.

    The ``geometry`` column contains clipped polygons, while ``cell_geometry``
    retains complete hexagons for reproducible area/centroid calculations.
    """
    import geopandas as gpd

    if resolution < 0 or resolution > 15:
        raise ValueError("H3 resolution must be between 0 and 15")
    if hasattr(boundary, "geometry") and not hasattr(boundary, "geom_type"):
        source_crs = getattr(boundary, "crs", None)
        frame = boundary.to_crs("EPSG:4326") if source_crs and str(source_crs).upper() != "EPSG:4326" else boundary
        geometry = frame.geometry.union_all() if hasattr(frame.geometry, "union_all") else frame.geometry.unary_union
    else:
        geometry = boundary
    if geometry is None or geometry.is_empty:
        raise ValueError("boundary must be a non-empty polygon")
    if geometry.geom_type not in {"Polygon", "MultiPolygon"}:
        raise TypeError("boundary must be a Polygon or MultiPolygon")

    records = []
    for cell in sorted(_cells_for_geometry(geometry, resolution)):
        polygon = _cell_polygon(cell)
        clipped = polygon.intersection(geometry)
        if not clipped.is_empty:
            records.append({"cell": cell, "resolution": resolution, "cell_geometry": polygon.wkb, "geometry": clipped})
    return gpd.GeoDataFrame(records, geometry="geometry", crs="EPSG:4326")
