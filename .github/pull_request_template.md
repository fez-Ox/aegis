## Aegis Pull Request

### 1. Summary of Changes
<!-- Provide a clear, concise overview of what was implemented or modified. -->

### 2. Functional & Non-Functional Requirements Mapping
<!-- Check the applicable requirement(s) implemented or touched by this PR -->
- [ ] **FR1:** Video Ingestion & Keyframe Normalization (Shahmeer)
- [ ] **FR2:** Dementia-Accessible Patient & Caregiver Mobile UI (Shahmeer)
- [ ] **FR3:** 3D Spatial Anchor & Persistent Instance Graph (Faizan)
- [ ] **FR4:** Anchor-Relative Query & Fast Coordinate Reasoning API (Faizan)
- [ ] **FR5:** Natural Language / Voice Query Disambiguation (Ali Sher)
- [ ] **FR6:** Spatial-Temporal Grounding & Relation Validation (Ali Sher)
- [ ] **NFR1:** Low-Latency Query Execution ($\le 500\,\text{ms}$)
- [ ] **NFR2:** WCAG 2.1 AAA Accessibility Compliance

### 3. Panel Action Register (PAR) Item Addressed
<!-- If this PR addresses feedback from the proposal defense, reference it here: -->
- [ ] **PAR-01:** Scope, CCP identification & Defined Acceptance Criteria Claims
- [ ] **PAR-02:** Resource Feasibility (Storage, Memory, Compute, Bandwidth, Cost)
- [ ] **PAR-03:** Plausibility of Technical Claims & Project Constraints
- [ ] **PAR-04:** Graphics, Visual Design & UI/UX Product Overhaul

### 4. Testing & Verification Evidence
<!-- Describe how this was tested and attach logs, screenshots, or benchmark metrics -->
- [ ] `uvx ruff check src tests run_pipeline.py` passed cleanly
- [ ] `uv run pytest` passed with all tests green
- [ ] Unit / Integration / Widget tests added or updated: `...`
- [ ] Edge / Failure case tested and handled: `...`

### 5. Responsible AI & Tool Disclosure (FYP Handbook Compliance)
<!-- Disclose any external models, APIs, libraries, or GenAI assistance used in this PR -->
- **External Components / Models Used:** (e.g., VGGT-Ω, YOLO-World, SAM 2, Flutter BLoC, etc.)
- **Human Authorship & Reasoning:** (Brief explanation of how the group designed, verified, and adapted the code)
