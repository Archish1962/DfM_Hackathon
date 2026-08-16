import cadquery as cq
from typing import Dict, Optional, Tuple

class MoldSplitError(Exception):
    pass

def _make_box(xmin: float, xmax: float, ymin: float, ymax: float, zmin: float, zmax: float) -> cq.Workplane:
    """Helper to create a box from min/max coordinates."""
    xlen = xmax - xmin
    ylen = ymax - ymin
    zlen = zmax - zmin
    cx = (xmin + xmax) / 2.0
    cy = (ymin + ymax) / 2.0
    cz = (zmin + zmax) / 2.0
    return cq.Workplane("XY").box(xlen, ylen, zlen, centered=(True, True, True)).translate((cx, cy, cz))

def execute_four_block_split(
    part: cq.Workplane,
    pull_axis: Tuple[float, float, float] = (0.0, 0.0, 1.0),
    slider_z_min: float = 4.0,
    slider_z_max: float = 22.0,
    parting_z: float = 4.0,
    margin_ratio: float = 0.5
) -> Dict[str, cq.Workplane]:
    """
    Splits the space into a 4-block mold: Top Cavity, Bottom Core, Left Slider, Right Slider.
    The sliders extract the middle undercut section pulling along the X-axis.
    
    Args:
        part: The input solid Workplane.
        pull_axis: Primary mold opening direction (default Z).
        slider_z_min: Z-height where sliders begin. Default 0.004609m.
        slider_z_max: Z-height where sliders end. Default 0.022m.
        parting_z: Z-height where the top cavity and bottom core split.
        margin_ratio: Margin for the tooling block size relative to the part.
        
    Returns:
        Dict with keys: 'top_cavity', 'bottom_core', 'left_slider', 'right_slider'
    """
    # 1. Bounding Box & Tolerances
    bb = part.val().BoundingBox()
    
    margin = max(bb.xlen, bb.ylen, bb.zlen) * margin_ratio
    
    x_min_mold = bb.xmin - margin
    x_max_mold = bb.xmax + margin
    y_min_mold = bb.ymin - margin
    y_max_mold = bb.ymax + margin
    z_min_mold = bb.zmin - margin
    z_max_mold = bb.zmax + margin
    
    # 2. Master Negative Volume
    master_box = _make_box(x_min_mold, x_max_mold, y_min_mold, y_max_mold, z_min_mold, z_max_mold)
    negative_volume = master_box.cut(part)
    
    # 3. Side Sliders Boundaries
    # Left slider is -X side (from x_min_mold to 0). Right slider is +X side (from 0 to x_max_mold).
    split_x = (bb.xmin + bb.xmax) / 2.0
    
    left_slider_bound = _make_box(x_min_mold, split_x, y_min_mold, y_max_mold, slider_z_min, slider_z_max)
    right_slider_bound = _make_box(split_x, x_max_mold, y_min_mold, y_max_mold, slider_z_min, slider_z_max)
    
    # Exclude the central core pin region from the sliders so the Top Cavity can claim it.
    # We use a radius of 25% of the part's width, which safely covers the inner hole but clears the outer undercuts.
    cx = (bb.xmin + bb.xmax) / 2.0
    cy = (bb.ymin + bb.ymax) / 2.0
    cz = (z_max_mold + z_min_mold) / 2.0
    core_pin_radius = max(bb.xlen, bb.ylen) * 0.25
    core_pin_bound = cq.Workplane("XY").cylinder(height=z_max_mold - z_min_mold + 10, radius=core_pin_radius).translate((cx, cy, cz))
    
    left_slider_bound = left_slider_bound.cut(core_pin_bound)
    right_slider_bound = right_slider_bound.cut(core_pin_bound)
    
    left_slider = negative_volume.intersect(left_slider_bound)
    right_slider = negative_volume.intersect(right_slider_bound)
    
    # 4. Vertical Core/Cavity Logic
    # Remove the side slider regions from the negative volume completely
    vertical_remainder = negative_volume.cut(left_slider_bound).cut(right_slider_bound)
    
    top_cavity_bound = _make_box(x_min_mold, x_max_mold, y_min_mold, y_max_mold, parting_z, z_max_mold)
    bottom_core_bound = _make_box(x_min_mold, x_max_mold, y_min_mold, y_max_mold, z_min_mold, parting_z)
    
    top_cavity = vertical_remainder.intersect(top_cavity_bound)
    bottom_core = vertical_remainder.intersect(bottom_core_bound)
    
    # 5. Validation
    blocks = {
        "top_cavity": top_cavity,
        "bottom_core": bottom_core,
        "left_slider": left_slider,
        "right_slider": right_slider
    }
    
    for name, block in blocks.items():
        if block.val() is None or not block.val().isValid():
            raise MoldSplitError(f"Generated mold block '{name}' is invalid or empty.")
            
    return blocks


def split_core_cavity(
    part: cq.Workplane,
    pull_axis: Tuple[float, float, float] = (0.0, 0.0, 1.0),
    parting_center: Optional[Tuple[float, float, float] | float] = None
) -> Tuple[cq.Workplane, cq.Workplane]:
    """
    Backward-compatible 2-block split helper returning (core, cavity).
    """
    val = part.val()
    if val is None:
        raise MoldSplitError("Part has no valid solid geometry.")
    
    bb = val.BoundingBox()
    margin = max(bb.xlen, bb.ylen, bb.zlen) * 0.5
    xmin, xmax = bb.xmin - margin, bb.xmax + margin
    ymin, ymax = bb.ymin - margin, bb.ymax + margin
    zmin, zmax = bb.zmin - margin, bb.zmax + margin
    
    if pull_axis[0] != 0:
        px = parting_center[0] if isinstance(parting_center, (tuple, list)) else (parting_center if parting_center is not None else (bb.xmin + bb.xmax)/2.0)
        box1 = _make_box(xmin, px, ymin, ymax, zmin, zmax)
        box2 = _make_box(px, xmax, ymin, ymax, zmin, zmax)
    elif pull_axis[1] != 0:
        py = parting_center[1] if isinstance(parting_center, (tuple, list)) else (parting_center if parting_center is not None else (bb.ymin + bb.ymax)/2.0)
        box1 = _make_box(xmin, xmax, ymin, py, zmin, zmax)
        box2 = _make_box(xmin, xmax, py, ymax, zmin, zmax)
    else:
        pz = parting_center[2] if isinstance(parting_center, (tuple, list)) else (parting_center if parting_center is not None else (bb.zmin + bb.zmax)/2.0)
        box1 = _make_box(xmin, xmax, ymin, ymax, zmin, pz)
        box2 = _make_box(xmin, xmax, ymin, ymax, pz, zmax)
    
    core_shape = val.intersect(box1.val())
    cavity_shape = val.intersect(box2.val())
    return cq.Workplane().add(core_shape), cq.Workplane().add(cavity_shape)

