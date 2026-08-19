from __future__ import annotations

import h3
from shapely.geometry import Point, Polygon

from city_os.spatial.h3_grid import build_h3_grid


def test_grid_covers_centroid_clips_edges_and_is_sorted() -> None:
    boundary = Polygon(
        [(-46.665, -23.575), (-46.615, -23.575), (-46.615, -23.525), (-46.665, -23.525)]
    )
    cells = build_h3_grid(boundary, resolution=8)

    assert str(cells.crs) == "EPSG:4326"
    assert cells["cell"].tolist() == sorted(set(cells["cell"]))
    centroid = boundary.centroid
    centroid_cell = (
        h3.latlng_to_cell(centroid.y, centroid.x, 8)
        if hasattr(h3, "latlng_to_cell")
        else h3.geo_to_h3(centroid.y, centroid.x, 8)
    )
    assert centroid_cell in set(cells["cell"])
    assert any(row.geometry.area < __import__("shapely").wkb.loads(row.cell_geometry).area for row in cells.itertuples())
    assert all(boundary.covers(row.geometry.representative_point()) for row in cells.itertuples())


def test_tiny_boundary_always_has_a_cell() -> None:
    point = Point(-46.6333, -23.5505)
    cells = build_h3_grid(point.buffer(0.00001), resolution=8)
    assert len(cells) == 1
