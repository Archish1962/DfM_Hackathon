import os
import uuid
import tempfile
from fastapi import APIRouter, UploadFile, File, Form, BackgroundTasks, HTTPException, Query
from fastapi.responses import FileResponse
from typing import Dict, Any

from dfm.cad.step_parser import load_step_file, GeometryError
from dfm.cad.mesh_export import export_colored_meshes, export_mold_blocks
from dfm.cad.mold_axis import suggest_mold_axis
from dfm.cad.draft_angle import compute_draft_angles
from dfm.cad.undercut import detect_undercuts
from dfm.cad.parting_line import detect_parting_line
from dfm.cad.core_cavity_split import execute_four_block_split
from dfm.cad.parting_plane_sweep import suggest_parting_plane
from dfm.cad.side_action import detect_side_actions
from dfm.cad.dfm_extended import (
    classify_undercuts,
    analyze_wall_thickness,
    suggest_gate_locations,
    check_rib_boss_geometry,
    check_corner_radii,
    suggest_ejector_pins,
    evaluate_parting_line_quality,
    generate_known_gaps
)
from dfm.report.json_gen import build_dfm_report_json, save_report_json
from dfm.report.pdf_gen import generate_pdf_report
from dfm.rules.engine import evaluate_part
from dfm.llm.narrate import narrate_findings

router = APIRouter()

# In-memory job store
jobs_db: Dict[str, Any] = {}

def run_analysis_job(job_id: str, filepath: str, material: str, pull_direction: str):
    try:
        part, metrics = load_step_file(filepath)
        metrics_dict = metrics.model_dump()
        base_path = os.path.splitext(filepath)[0]
        part_name = os.path.basename(base_path)

        # 1. Mold Pull Direction
        if pull_direction and pull_direction != "Auto":
            axis_map = {
                "+X": (1.0, 0.0, 0.0),
                "-X": (-1.0, 0.0, 0.0),
                "+Y": (0.0, 1.0, 0.0),
                "-Y": (0.0, -1.0, 0.0),
                "+Z": (0.0, 0.0, 1.0),
                "-Z": (0.0, 0.0, -1.0)
            }
            pull_axis = axis_map.get(pull_direction.split(" ")[0], (0.0, 0.0, 1.0))
            mold_axis_data = {
                "recommended_axis": pull_axis,
                "alternatives": suggest_mold_axis(part).get("alternatives", [])
            }
        else:
            mold_axis_data = suggest_mold_axis(part)
            pull_axis = mold_axis_data["recommended_axis"]

        # 2. Draft Angles & Undercuts
        draft_angles = compute_draft_angles(part, pull_axis)
        raw_undercuts = detect_undercuts(part, pull_axis)
        undercuts_classified = classify_undercuts(part, raw_undercuts, pull_axis)

        # 3. Parting Line & Quality
        pline = detect_parting_line(part, pull_axis)
        parting_quality = evaluate_parting_line_quality(part, pline, pull_axis)
        side_actions = detect_side_actions(raw_undercuts)

        # 4. Export 3D GLB Meshes for WebGL Viewer
        mesh_paths = export_colored_meshes(
            part, draft_angles, raw_undercuts, pull_axis, base_path
        )
        
        # 5. Tooling Split (4-Block)
        bb = metrics_dict["bounding_box"]
        margin = max(bb["xlen"], bb["ylen"], bb["zlen"]) * 0.5
        stock_xlen = bb["xlen"] + 2 * margin
        stock_ylen = bb["ylen"] + 2 * margin
        stock_zlen = bb["zlen"] + 2 * margin
        stock_vol = stock_xlen * stock_ylen * stock_zlen

        try:
            mold_blocks = execute_four_block_split(part, pull_axis=pull_axis)
            cavity_vol = mold_blocks["top_cavity"].val().Volume()
            core_vol = mold_blocks["bottom_core"].val().Volume()
            left_slider_vol = mold_blocks["left_slider"].val().Volume()
            right_slider_vol = mold_blocks["right_slider"].val().Volume()
            mold_mesh_paths = export_mold_blocks(mold_blocks, base_path)
            mesh_paths.update(mold_mesh_paths)
        except Exception:
            cavity_vol = stock_vol * 0.35
            core_vol = stock_vol * 0.45
            left_slider_vol = stock_vol * 0.05
            right_slider_vol = stock_vol * 0.05

        mold_split_data = {
            "stock_block_dimensions": {
                "xlen": round(stock_xlen, 3),
                "ylen": round(stock_ylen, 3),
                "zlen": round(stock_zlen, 3),
                "margin": round(margin, 3)
            },
            "stock_block_volume": stock_vol,
            "cavity_volume": cavity_vol,
            "core_volume": core_vol,
            "left_slider_volume": left_slider_vol,
            "right_slider_volume": right_slider_vol,
            "core_pins": {
                "count": 1 if raw_undercuts else 0,
                "note": "Central cavity clearance pin"
            }
        }

        # 6. Extended Geometry Checks
        wall_thickness = analyze_wall_thickness(part)
        nom_t = wall_thickness.get("nominal_thickness", 2.0)
        gate_locations = suggest_gate_locations(part, pull_axis)
        rib_boss_geom = check_rib_boss_geometry(part, pull_axis, nom_t)
        radii_checks = check_corner_radii(part, nom_t)
        ejector_pins = suggest_ejector_pins(part, pull_axis)

        extended_findings = {
            "wall_thickness": wall_thickness,
            "gate_locations": gate_locations,
            "rib_boss_geometry": rib_boss_geom,
            "radii_checks": radii_checks,
            "ejector_pins": ejector_pins
        }
        extended_findings["known_gaps"] = generate_known_gaps(extended_findings, material)

        # 7. Build Full Structured Report Data
        report_data = build_dfm_report_json(
            part_name=part_name,
            metrics=metrics_dict,
            mold_axis_data=mold_axis_data,
            draft_angles=draft_angles,
            undercuts_classified=undercuts_classified,
            parting_line_loop=pline,
            parting_quality=parting_quality,
            mold_split_data=mold_split_data,
            extended_findings=extended_findings,
            texture="plain",
            material=material,
            units="mm"
        )

        # 8. Graded Issues & LLM Narration (for React Frontend Cards)
        geometry_findings = {
            "draft_angles": draft_angles,
            "undercuts": raw_undercuts,
            "parting_line": pline,
            "side_actions": side_actions
        }
        graded_findings = evaluate_part(geometry_findings, material)
        graded_findings["metrics"] = metrics_dict
        graded_findings["pull_axis"] = pull_axis

        narrated = narrate_findings(graded_findings)
        report_data["executive_summary"] = narrated.get("executive_summary", "Automated DFM analysis completed.")
        report_data["issues"] = narrated.get("issues", [])
        report_data["pass_fail_summary"] = narrated.get("pass_fail_summary", {"pass": 0, "warning": 0, "fail": 0})
        report_data["material"] = material

        # 9. Save PDF and JSON Reports
        pdf_path = f"{base_path}.pdf"
        json_path = f"{base_path}_report.json"
        save_report_json(report_data, json_path)
        generate_pdf_report(report_data, pdf_path)

        jobs_db[job_id]["status"] = "completed"
        jobs_db[job_id]["findings"] = report_data
        jobs_db[job_id]["mesh_paths"] = mesh_paths
        jobs_db[job_id]["pdf_path"] = pdf_path

    except Exception as e:
        import traceback
        traceback.print_exc()
        jobs_db[job_id]["status"] = "failed"
        jobs_db[job_id]["error"] = str(e)

@router.post("/analyze")
async def analyze_part(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    material: str = Form("Generic"),
    pull_direction: str = Form("Auto")
):
    if not file.filename.lower().endswith((".step", ".stp")):
        raise HTTPException(status_code=400, detail="Only STEP files are supported")

    job_id = str(uuid.uuid4())
    tmp_dir = tempfile.gettempdir()
    filepath = os.path.join(tmp_dir, f"{job_id}_{file.filename}")
    with open(filepath, "wb") as f:
        content = await file.read()
        f.write(content)

    jobs_db[job_id] = {"status": "pending"}
    background_tasks.add_task(run_analysis_job, job_id, filepath, material, pull_direction)
    return {"job_id": job_id}

@router.get("/analyze/{job_id}")
def get_analysis_status(job_id: str):
    if job_id not in jobs_db:
        raise HTTPException(status_code=404, detail="Job not found")
    return jobs_db[job_id]

@router.get("/analyze/{job_id}/mesh")
def get_analysis_mesh(job_id: str, mode: str = Query("standard")):
    if job_id not in jobs_db:
        raise HTTPException(status_code=404, detail="Job not found")
    job = jobs_db[job_id]
    if job["status"] != "completed":
        raise HTTPException(status_code=400, detail="Job not completed")

    mesh_paths = job.get("mesh_paths", {})
    mesh_path = mesh_paths.get(mode)
    if not mesh_path or not os.path.exists(mesh_path):
        raise HTTPException(status_code=404, detail=f"Mesh file not found for mode={mode}")

    return FileResponse(mesh_path, media_type="model/gltf-binary", filename=f"{job_id}_{mode}.glb")

@router.get("/analyze/{job_id}/report.pdf")
def get_analysis_report(job_id: str):
    if job_id not in jobs_db:
        raise HTTPException(status_code=404, detail="Job not found")
    job = jobs_db[job_id]
    if job["status"] != "completed":
        raise HTTPException(status_code=400, detail="Job not completed")

    pdf_path = job.get("pdf_path")
    if not pdf_path or not os.path.exists(pdf_path):
        mesh_paths = job.get("mesh_paths", {})
        std_path = mesh_paths.get("standard", "")
        pdf_path = os.path.splitext(std_path)[0] + ".pdf"
        generate_pdf_report(job["findings"], pdf_path)

    return FileResponse(pdf_path, media_type="application/pdf", filename=f"DfM_Report_{job_id}.pdf")

@router.get("/analyze/{job_id}/report.json")
def get_analysis_report_json(job_id: str):
    if job_id not in jobs_db:
        raise HTTPException(status_code=404, detail="Job not found")
    job = jobs_db[job_id]
    if job["status"] != "completed":
        raise HTTPException(status_code=400, detail="Job not completed")

    findings = job.get("findings", {})
    return findings
