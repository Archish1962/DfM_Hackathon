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
from dfm.rules.engine import evaluate_part
from dfm.llm.narrate import narrate_findings
from dfm.report.pdf_gen import generate_pdf_report

router = APIRouter()

# In-memory job store
jobs_db: Dict[str, Any] = {}

def run_analysis_job(job_id: str, filepath: str, material: str, pull_direction: str):
    try:
        part, metrics = load_step_file(filepath)

        if pull_direction and pull_direction != "Auto":
            axis_map = {
                "+X": (1.0, 0.0, 0.0),
                "-X": (-1.0, 0.0, 0.0),
                "+Y": (0.0, 1.0, 0.0),
                "-Y": (0.0, -1.0, 0.0),
                "+Z": (0.0, 0.0, 1.0),
                "-Z": (0.0, 0.0, -1.0)
            }
            # Fallback to (0,0,1) if something weird is passed
            pull_axis = axis_map.get(pull_direction.split(" ")[0], (0.0, 0.0, 1.0))
        else:
            axis_res = suggest_mold_axis(part)
            pull_axis = axis_res["recommended_axis"]

        draft_angles = compute_draft_angles(part, pull_axis)
        undercuts = detect_undercuts(part, pull_axis)
        pline = detect_parting_line(part, pull_axis)
        plane_res = suggest_parting_plane(part, pull_axis)
        side_actions = detect_side_actions(undercuts)

        # Export three coloured GLBs
        base_path = os.path.splitext(filepath)[0]
        mesh_paths = export_colored_meshes(
            part, draft_angles, undercuts, pull_axis, base_path
        )
        
        # Generate 4-block tooling split
        mold_blocks = execute_four_block_split(part, pull_axis=pull_axis)
        mold_mesh_paths = export_mold_blocks(mold_blocks, base_path)
        mesh_paths.update(mold_mesh_paths)

        geometry_findings = {
            "draft_angles": draft_angles,
            "undercuts": undercuts,
            "parting_line": pline,
            "side_actions": side_actions
        }

        graded_findings = evaluate_part(geometry_findings, material)
        graded_findings["metrics"] = metrics.model_dump()
        graded_findings["pull_axis"] = pull_axis

        final_findings = narrate_findings(graded_findings)

        jobs_db[job_id]["status"] = "completed"
        jobs_db[job_id]["findings"] = final_findings
        jobs_db[job_id]["mesh_paths"] = mesh_paths

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

    mesh_paths = job.get("mesh_paths", {})
    std_path = mesh_paths.get("standard", "")
    pdf_path = os.path.splitext(std_path)[0] + ".pdf"

    if not os.path.exists(pdf_path):
        generate_pdf_report(job["findings"], pdf_path)

    return FileResponse(pdf_path, media_type="application/pdf", filename=f"DfM_Report_{job_id}.pdf")
