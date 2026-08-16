import React, { useState, useEffect, useRef } from 'react';
import { Upload, File, Loader } from 'lucide-react';
import Viewer from './Viewer';
import ExplodedViewer from './ExplodedViewer';

const API_BASE = "http://localhost:8000";

function App() {
  const [file, setFile] = useState(null);
  const [jobId, setJobId] = useState(null);
  const [status, setStatus] = useState("idle");
  const [findings, setFindings] = useState(null);
  const [pullDirection, setPullDirection] = useState("Auto");

  const [viewMode, setViewMode] = useState("standard"); // standard, draft, undercut, mold

  const fileInputRef = useRef(null);

  // Build the mesh URL dynamically from viewMode
  const meshUrl = (jobId && status === "completed" && viewMode !== "mold")
    ? `${API_BASE}/analyze/${jobId}/mesh?mode=${viewMode}`
    : null;

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
    }
  };

  const startAnalysis = async () => {
    if (!file) return;
    setStatus("uploading");

    const formData = new FormData();
    formData.append("file", file);
    formData.append("material", "Generic");
    formData.append("pull_direction", pullDirection);

    try {
      const res = await fetch(`${API_BASE}/analyze`, {
        method: "POST",
        body: formData,
      });
      if (!res.ok) throw new Error("Upload failed");
      const data = await res.json();
      setJobId(data.job_id);
      setStatus("processing");
    } catch (err) {
      console.error(err);
      setStatus("error");
    }
  };

  useEffect(() => {
    if (status !== "processing" || !jobId) return;

    const interval = setInterval(async () => {
      try {
        const res = await fetch(`${API_BASE}/analyze/${jobId}`);
        const data = await res.json();

        if (data.status === "completed") {
          setFindings(data.findings);
          setStatus("completed");
          clearInterval(interval);
        } else if (data.status === "failed") {
          setStatus("error");
          clearInterval(interval);
        }
      } catch (err) {
        console.error(err);
      }
    }, 1000);

    return () => clearInterval(interval);
  }, [status, jobId]);

  return (
    <div className="app-container">
      <div className="sidebar">
        <div className="header">
          <h1>DfM Intelligence</h1>
          <p className="subtitle">Automated Design for Manufacturing analysis for injection-molded plastics.</p>
        </div>

        {!findings && (
          <>
            <div
              className="upload-zone"
              onClick={() => fileInputRef.current?.click()}
            >
              <Upload size={32} color="var(--accent)" style={{ marginBottom: 16 }} />
              {file ? (
                <p>Selected: <strong>{file.name}</strong></p>
              ) : (
                <p>Click to browse or drop a STEP file here.</p>
              )}
              <input
                type="file"
                ref={fileInputRef}
                onChange={handleFileChange}
                accept=".step,.stp"
                style={{ display: 'none' }}
              />
            </div>
            
            <label>Pull Direction</label>
            <select value={pullDirection} onChange={(e) => setPullDirection(e.target.value)}>
              <option value="Auto">Auto (Calculated)</option>
              <option value="+Z">+Z (0, 0, 1)</option>
              <option value="-Z">-Z (0, 0, -1)</option>
              <option value="+X">+X (1, 0, 0)</option>
              <option value="-X">-X (-1, 0, 0)</option>
              <option value="+Y">+Y (0, 1, 0)</option>
              <option value="-Y">-Y (0, -1, 0)</option>
            </select>

            <button
              className="primary"
              onClick={startAnalysis}
              disabled={!file || status === "uploading" || status === "processing"}
            >
              {(status === "uploading" || status === "processing") ? (
                <><div className="loading-spinner" /> Analyzing Geometry...</>
              ) : (
                "Run DfM Analysis"
              )}
            </button>
          </>
        )}

        {findings && (
          <div className="results-section">
            <button className="primary" onClick={() => window.open(`${API_BASE}/analyze/${jobId}/report.pdf`)}>
              <File size={16} /> Download Full PDF Report
            </button>

            <div className="card">
              <h3>Executive Summary</h3>
              <div className="executive-summary">{findings.executive_summary}</div>
            </div>

            <div className="card">
              <h3>
                Identified Issues
                <span className={`status-badge status-${findings.pass_fail_summary.fail > 0 ? 'fail' : 'pass'}`}>
                  {findings.pass_fail_summary.fail} Fails
                </span>
              </h3>

              {findings.issues.map((issue, idx) => (
                <div className="issue-item" key={idx}>
                  <div className="issue-header">
                    <span className="issue-title">{issue.issue_type}</span>
                    <span className={`status-badge status-${issue.severity}`}>{issue.severity}</span>
                  </div>
                  <p className="issue-desc">
                    {issue.category === "draft"
                      ? `Measured draft: ${issue.measured_value.toFixed(1)}° (Required: ${issue.threshold.toFixed(1)}°)`
                      : `Undercut trapped by pull direction.`}
                  </p>
                  <p className="issue-narrative">{issue.narrative}</p>
                </div>
              ))}

              {findings.issues.length === 0 && (
                <p className="issue-desc">No critical manufacturability issues found!</p>
              )}
            </div>
          </div>
        )}
      </div>

      <div className="viewer-container">
        {status === "completed" ? (
          viewMode === "mold" ? (
            <ExplodedViewer jobId={jobId} key="mold" />
          ) : (
            <Viewer url={meshUrl} key={viewMode} />
          )
        ) : (
          <div style={{display:'flex', height:'100%', alignItems:'center', justifyContent:'center', color:'var(--text-secondary)'}}>
            <p>Upload a part to visualize the analysis.</p>
          </div>
        )}

        {status === "completed" && (
          <div className="controls-overlay" style={{ zIndex: 10 }}>
            <button
              className={`control-btn ${viewMode === 'standard' ? 'active' : ''}`}
              onClick={() => setViewMode('standard')}
            >
              Standard View
            </button>
            <button
              className={`control-btn ${viewMode === 'draft' ? 'active' : ''}`}
              onClick={() => setViewMode('draft')}
            >
              Draft Heatmap
            </button>
            <button
              className={`control-btn ${viewMode === 'undercut' ? 'active' : ''}`}
              onClick={() => setViewMode('undercut')}
            >
              Undercuts
            </button>
            <button
              className={`control-btn ${viewMode === 'mold' ? 'active' : ''}`}
              onClick={() => setViewMode('mold')}
            >
              Mold Exploded View
            </button>
          </div>
        )}

        {status === "completed" && viewMode === "draft" && (
          <div className="legend-overlay">
            <div className="legend-title">Draft Angle</div>
            <div className="legend-item"><span className="legend-swatch" style={{background:'#00c800'}} /> &gt; +5°</div>
            <div className="legend-item"><span className="legend-swatch" style={{background:'#ffdc00'}} /> 0° to +5°</div>
            <div className="legend-item"><span className="legend-swatch" style={{background:'#1e3cdc'}} /> −5° to 0°</div>
            <div className="legend-item"><span className="legend-swatch" style={{background:'#d21414'}} /> &lt; −5°</div>
          </div>
        )}

        {status === "completed" && viewMode === "undercut" && (
          <div className="legend-overlay">
            <div className="legend-title">Undercuts</div>
            <div className="legend-item"><span className="legend-swatch" style={{background:'#d21414'}} /> Undercut face</div>
            <div className="legend-item"><span className="legend-swatch" style={{background:'#b4b4be'}} /> Clear</div>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;
