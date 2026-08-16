# DfM Intelligence - Automated Tooling & Mold Analysis

An automated Design for Manufacturing (DfM) software pipeline and 3D interactive viewer for inspecting CAD models, specifically geared toward injection molding analysis. 

The software utilizes a **CadQuery** backend to perform robust CAD kernel operations (like undercut detection, draft angle validation, and automated 4-block tooling splits) and a **React + Three.js** frontend to visualize the geometry and tooling blocks in a sleek, interactive 3D WebGL environment.

## Features
- **Upload & Analyze**: Upload standard `.stp` / `.step` CAD files.
- **Draft Angle Analysis**: Visualizes mold-release angles, mapping faces into a 4-color Siemens NX standard palette (Green, Yellow, Blue, Red).
- **Undercut Detection**: Ray-casting logic to highlight faces that create mechanical locks.
- **Automated Core/Cavity Split**: Generates a 4-block tooling layout (Top Cavity, Bottom Core, Left Slider, Right Slider) based on exact CNC measurements.
- **Interactive Exploded Viewer**: A smooth, slider-controlled exploded viewer to inspect the internal mold cavity and side-action pulls.

## Tech Stack
- **Backend**: Python, FastAPI, CadQuery (OCP)
- **Frontend**: React, Vite, `@react-three/fiber`, `@react-three/drei`
- **Package Management**: `uv` (Python), `npm` (Node.js)

---

## 🚀 How to Run Locally

### Prerequisites
- Python 3.10+ and [uv](https://github.com/astral-sh/uv) installed
- Node.js 18+ and `npm` installed

### 1. Start the Backend (FastAPI + CadQuery)
Open a terminal in the root directory of the project:

```bash
# Install dependencies using uv
uv sync

# Set the python path to include the src directory and start the server
# On Windows (PowerShell):
$env:PYTHONPATH="src"
uv run uvicorn dfm.api.main:app --port 8000 --reload

# On Mac/Linux:
export PYTHONPATH="src"
uv run uvicorn dfm.api.main:app --port 8000 --reload
```
The backend API will be available at `http://localhost:8000`.

### 2. Start the Frontend (React + Vite)
Open a new terminal and navigate to the `frontend` directory:

```bash
cd frontend

# Install dependencies
npm install

# Start the Vite development server
npm run dev
```
The interactive web app will be available at `http://localhost:5173`.

---

## Usage
1. Open the frontend in your browser.
2. Click to upload a valid `.stp` or `.step` CAD file (you can find samples in the `actual_part/` or `sample_parts/` folders).
3. Select your desired pull direction (`+Z`, `+X`, or `+Y`).
4. Wait for the background analysis job to complete.
5. Use the toggles to view **Draft Angles** and **Undercuts**.
6. Toggle **"Mold Exploded View"** and drag the slider to animate the 4-block tooling split!
