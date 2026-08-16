import React, { useState, useEffect, useRef } from 'react';
import { Upload, File, Loader, FileText, Download } from 'lucide-react';
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

  const meshUrl = (jobId && status === "completed" && viewMode !== "mold")
    ? `${API_BASE}/analyze/${jobId}/mesh?mode=${viewMode === 'parting' ? 'standard' : viewMode}`
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
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', marginBottom: '12px' }}>
              <button className="primary" style={{ padding: '10px', fontSize: '0.85rem' }} onClick={() => window.open(`${API_BASE}/analyze/${jobId}/report.pdf`)}>
                <File size={16} /> Download PDF
              </button>
              <button className="secondary" style={{ padding: '10px', fontSize: '0.85rem', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px' }} onClick={() => {
                const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(findings, null, 2));
                const downloadAnchor = document.createElement('a');
                downloadAnchor.setAttribute("href", dataStr);
                const pName = findings?.part_summary?.part_name || (file ? file.name.replace(/\.[^/.]+$/, "") : "dfm");
                downloadAnchor.setAttribute("download", `${pName}_report.json`);
                document.body.appendChild(downloadAnchor);
                downloadAnchor.click();
                downloadAnchor.remove();
              }}>
                <FileText size={16} /> Download JSON
              </button>
            </div>

            <div className="card">
              <h3>Executive Summary</h3>
              <div className="executive-summary">{findings.executive_summary}</div>
            </div>

            <div className="card">
              <h3>
                Identified Issues
                <span className={`status-badge status-${findings.pass_fail_summary && findings.pass_fail_summary.fail > 0 ? 'fail' : 'pass'}`}>
                  {findings.pass_fail_summary ? findings.pass_fail_summary.fail : 0} Violations
                </span>
              </h3>

              {(() => {
                const issues = findings.issues || [];
                if (issues.length === 0) {
                  return <p className="issue-desc">No critical manufacturability issues found!</p>;
                }

                // Group issues by type
                const groups = {};
                issues.forEach(issue => {
                  const key = issue.issue_type || "Issue";
                  if (!groups[key]) {
                    groups[key] = {
                      title: key,
                      severity: issue.severity || "fail",
                      category: issue.category,
                      count: 0,
                      threshold: issue.threshold
                    };
                  }
                  groups[key].count += 1;
                });

                return Object.values(groups).map((group, idx) => (
                  <div className="issue-item" key={idx}>
                    <div className="issue-header">
                      <span className="issue-title">
                        {group.count} faces with {group.title}
                      </span>
                      <span className={`status-badge status-${group.severity}`}>{group.severity}</span>
                    </div>
                    <p className="issue-desc">
                      {group.category === "draft"
                        ? `Walls lacking minimum ${group.threshold ? group.threshold.toFixed(1) : '1.0'}° draft angle required for ejection.`
                        : `Undercuts trapped along pull direction requiring side-action sliders or lifters.`}
                    </p>
                    <p style={{ fontSize: "0.78rem", color: "#64748b", marginTop: "4px" }}>
                      Visualized on 3D viewer. Detailed per-face table available in the PDF report.
                    </p>
                  </div>
                ));
              })()}
            </div>
          </div>
        )}
      </div>

      <div className="viewer-container">
        {status === "completed" ? (
          viewMode === "mold" ? (
            <ExplodedViewer jobId={jobId} key="mold" />
          ) : (
            <Viewer url={meshUrl} partingLine={findings?.parting_line} viewMode={viewMode} key={viewMode} />
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
            <button
              className={`control-btn ${viewMode === 'parting' ? 'active' : ''}`}
              onClick={() => setViewMode('parting')}
            >
              Parting Lines
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
