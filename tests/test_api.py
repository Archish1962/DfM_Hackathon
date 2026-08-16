import pytest
import time
from fastapi.testclient import TestClient
from dfm.api.main import app

client = TestClient(app)

SAMPLE_BOX_PATH = "sample_parts/test_box.step"

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_analyze_flow():
    with open(SAMPLE_BOX_PATH, "rb") as f:
        response = client.post("/analyze", files={"file": ("test_box.step", f, "application/step")}, data={"material": "Generic"})
        
    assert response.status_code == 200
    job_id = response.json()["job_id"]
    
    # Poll for completion
    max_retries = 30
    for _ in range(max_retries):
        resp = client.get(f"/analyze/{job_id}")
        data = resp.json()
        if data["status"] == "completed":
            break
        elif data["status"] == "failed":
            pytest.fail(f"Job failed: {data.get('error')}")
        time.sleep(0.5)
    else:
        pytest.fail("Job did not complete in time")
        
    # Check findings
    assert "findings" in data
    assert "executive_summary" in data["findings"]
    
    # Check mesh download
    mesh_resp = client.get(f"/analyze/{job_id}/mesh")
    assert mesh_resp.status_code == 200
    assert len(mesh_resp.content) > 0
    assert mesh_resp.headers["content-type"] == "model/gltf-binary"
