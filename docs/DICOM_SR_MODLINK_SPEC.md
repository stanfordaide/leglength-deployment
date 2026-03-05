# Pediatric Leg Length DICOM SR – Modlink Implementation Specification

**Purpose:** Technical specification of the DICOM Structured Report (SR) produced by the Stanford AIDE Pediatric Leg Length AI module, for successful Modlink integration.

**Audience:** PACS/IT administrators configuring Modlink to receive and parse these reports.

---

## 1. Overview

| Property | Value |
|----------|-------|
| **Modality** | SR (Structured Report) |
| **SOP Class UID** | `1.2.840.10008.5.1.4.1.1.88.11` (Enhanced SR) |
| **Series Description** | `AI Measurements` |
| **Character Set** | `ISO_IR 100` (Latin-1) |
| **Completion Flag** | `COMPLETE` |
| **Verification Flag** | `UNVERIFIED` |

---

## 2. Coding Scheme

All coded concepts use:

| Attribute | Value |
|-----------|-------|
| **Coding Scheme Designator** | `STANFORD_AIDE` |
| **Version** | 1.0 |
| **Algorithm** | `PLL_001` (Pediatric Leg Length) |

---

## 3. Content Structure (Hierarchy)

```
ContentSequence
└── [1] CONTAINER: "Pediatric Leg Length Results" (PLL_RESULTS)
    └── ContentSequence (flat list of TEXT items)
        ├── Measurement items (99_PLL_R_FEM, 99_PLL_R_TIB, etc.) — numeric values only
        ├── Difference placeholders (LONGER_SIDE + VALUE per segment) [when both sides available]
        └── (Issues container is currently disabled)
```

---

## 4. Content Items – Reference Table

### 4.1 Individual Measurements

Each measurement is a TEXT item with `RelationshipType = HAS PROPERTIES` and `ValueType = TEXT`.

**Units are not included** — values are numeric only. Units are cm (apply at display/reporting).

| Code Value | Code Meaning | TextValue Format | When Present |
|-------------|--------------|------------------|--------------|
| `99_PLL_R_FEM` | Right femur length | `{value}` (e.g. `25.4`) | When right femur measured |
| `99_PLL_R_TIB` | Right tibia length | `{value}` | When right tibia measured |
| `99_PLL_R_LGL` | Total right lower extremity length | `{value}` | When right total measured |
| `99_PLL_L_FEM` | Left femur length | `{value}` | When left femur measured |
| `99_PLL_L_TIB` | Left tibia length | `{value}` | When left tibia measured |
| `99_PLL_L_LGL` | Total left lower extremity length | `{value}` | When left total measured |

All numeric values use **1 decimal place** (e.g. `25.4`, `38.2`). Units = **cm** (to be applied by Modlink/reporting layer).

### 4.2 Difference Placeholders (Bilateral Comparison)

Difference data is stored as **separate placeholders** for sentence construction, not as pre-built text.

For each segment (femur, tibia, total), two items are present when both sides are available:

| Code Value | Code Meaning | TextValue | Description |
|-------------|--------------|-----------|-------------|
| `99_FEM_DIFF_LONGER_SIDE` | Femur length - longer side | `RIGHT` \| `LEFT` \| `EQUAL` | Which side is longer (or equal) |
| `99_FEM_DIFF_VALUE` | Femur length difference value | `{value}` (e.g. `0.2`) | Absolute difference, numeric only, no units |
| `99_TIB_DIFF_LONGER_SIDE` | Tibia length - longer side | `RIGHT` \| `LEFT` \| `EQUAL` | |
| `99_TIB_DIFF_VALUE` | Tibia length difference value | `{value}` | |
| `99_TOT_DIFF_LONGER_SIDE` | Total leg length - longer side | `RIGHT` \| `LEFT` \| `EQUAL` | |
| `99_TOT_DIFF_VALUE` | Total leg length difference value | `{value}` | |

**Segment name for sentence construction** (from CodeValue prefix): `FEM` → "femur", `TIB` → "tibia", `TOT` → "leg".

**Sentence construction rules:**

| LONGER_SIDE | Template |
|-------------|----------|
| `EQUAL` | "{segment} lengths are equal" |
| `RIGHT` | "Right {segment} is longer than left by {value} cm" |
| `LEFT` | "Left {segment} is longer than right by {value} cm" |

### 4.3 Display Text (Backup)

Ready-to-display sentences for cases where Modlink cannot use template logic (e.g. conditional on `EQUAL`):

| Code Value | Code Meaning | TextValue Examples |
|-------------|--------------|---------------------|
| `99_FEM_DIFF_DISPLAY` | Femur length difference (display text) | `"Femur lengths are equal"` / `"Right femur is longer than left by 0.2 cm"` / `"Left femur is longer than right by 0.3 cm"` |
| `99_TIB_DIFF_DISPLAY` | Tibia length difference (display text) | `"Tibia lengths are equal"` / `"Right tibia is longer than left by 0.1 cm"` / etc. |
| `99_TOT_DIFF_DISPLAY` | Total leg length difference (display text) | `"Total leg lengths are equal"` / `"Right leg is longer than left by 0.3 cm"` / etc. |

**Modlink can use `99_*_DIFF_DISPLAY` directly** when template branching is not available. Prefer placeholders (4.2) when template logic is supported.

---

## 5. Headers Copied from Source Study

The SR inherits these DICOM attributes from the original study (when present):

| Tag | Keyword | Notes |
|-----|---------|-------|
| (0010,0010) | PatientName | |
| (0010,0020) | PatientID | |
| (0010,0030) | PatientBirthDate | |
| (0010,0040) | PatientSex | |
| (0020,000D) | StudyInstanceUID | Links SR to source study |
| (0020,0010) | StudyID | |
| (0008,0020) | StudyDate | |
| (0008,0050) | AccessionNumber | |
| (0008,0090) | ReferringPhysicianName | |
| (0010,1010) | PatientAge | |
| (0010,1020) | PatientSize | |
| (0010,1030) | PatientWeight | |
| (0010,2000) | MedicalAlerts | |
| (0010,2110) | Allergies | |
| (0010,21C0) | PregnancyStatus | |
| (0008,1030) | StudyDescription | |

---

## 6. Stanford AIDE Private Tags (Group 0x7001)

| Tag | VR | Purpose |
|-----|-----|---------|
| (7001,0001) | LO | Algorithm ID (e.g. `PLL_001`) |
| (7001,0002) | CS | Processing Status (e.g. `COMPLETE`) |
| (7001,0003) | DT | Processing Timestamp |
| (7001,0004) | DS | Confidence Score (optional) |
| (7001,0005) | DS | Processing Duration seconds (optional) |
| (7001,0006) | UI | Source SOP Instance UID (optional) |

---

## 7. Routing to Modlink

- **Destination AET:** Configured as `MODLINK` in Orthanc (e.g. `PSRTBONEAPP01`).
- **Routing rule:** Instances with `Modality = SR` and `SeriesDescription` containing AI measurement patterns are sent to Modlink.
- **Expected workflow:** Orthanc receives SR from MERCURE → routes SR to Modlink via C-STORE.

---

## 8. File Naming and Storage

- SR files are saved as `{SeriesID}_sr_output.dcm` in the MERCURE output directory.
- They are then dispatched to the configured destinations, including Modlink.

---

## 9. Example Content (Conceptual)

For a successful bilateral study, the SR content might look like:

```
Pediatric Leg Length Results
├── 99_PLL_R_FEM  "Right femur length"            = "25.4"
├── 99_PLL_R_TIB  "Right tibia length"             = "22.1"
├── 99_PLL_R_LGL  "Total right lower extremity"    = "47.5"
├── 99_PLL_L_FEM  "Left femur length"              = "25.2"
├── 99_PLL_L_TIB  "Left tibia length"             = "22.0"
├── 99_PLL_L_LGL  "Total left lower extremity"    = "47.2"
├── 99_FEM_DIFF_LONGER_SIDE  "Femur - longer side" = "RIGHT"
├── 99_FEM_DIFF_VALUE        "Femur diff value"   = "0.2"
├── 99_FEM_DIFF_DISPLAY      "Femur (display)"     = "Right femur is longer than left by 0.2 cm"
├── 99_TIB_DIFF_LONGER_SIDE  "Tibia - longer side" = "RIGHT"
├── 99_TIB_DIFF_VALUE        "Tibia diff value"    = "0.1"
├── 99_TIB_DIFF_DISPLAY      "Tibia (display)"     = "Right tibia is longer than left by 0.1 cm"
├── 99_TOT_DIFF_LONGER_SIDE  "Total - longer side" = "RIGHT"
├── 99_TOT_DIFF_VALUE        "Total diff value"   = "0.3"
└── 99_TOT_DIFF_DISPLAY      "Total (display)"    = "Right leg is longer than left by 0.3 cm"
```

**Modlink options:**
- **Template:** `LONGER_SIDE` + `VALUE` → construct sentence (supports EQUAL/LEFT/RIGHT)
- **Backup:** Use `99_*_DIFF_DISPLAY` directly when template logic is not available

---

## 10. Modlink Configuration Checklist

- [ ] Modlink AET configured in Orthanc (e.g. MODLINK / PSRTBONEAPP01)
- [ ] Network connectivity and firewall rules for DICOM C-STORE to Modlink
- [ ] Modlink configured to accept SOP Class UID `1.2.840.10008.5.1.4.1.1.88.11` (Enhanced SR)
- [ ] Mapping/template in Modlink to extract `STANFORD_AIDE` coded concepts (CodeValue, CodeMeaning, TextValue)
- [ ] **Units:** Apply "cm" when displaying measurement values (values are numeric only)
- [ ] **Sentence construction:** Use LONGER_SIDE + VALUE placeholders, OR use 99_*_DIFF_DISPLAY as backup when template logic unavailable
- [ ] Validation that StudyInstanceUID and AccessionNumber are preserved for linking to source study

---

*Document generated from `mercure-pediatric-leglength` module. Last updated: 2025-03.*
