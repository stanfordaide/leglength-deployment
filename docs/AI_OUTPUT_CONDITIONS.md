# AI Output Detection Conditions (for Docker / DICOM Implementation)

This document describes **how the RADWATCH routing system detects that a study contains AI-generated output**. Use this when implementing Docker-based AI modules or DICOM pipelines so your outputs are correctly identified and routed.

When Orthanc receives a study back from Mercure/AI processing, it checks each instance (DICOM file) for these markers. **If ANY instance in the study matches ANY condition**, the entire study is considered to have AI output and will be routed to final destinations (LPCH, LPCHT, MODLINK).

---

## Condition 1: Manufacturer (Primary)

| Tag | Value |
|-----|-------|
| **Manufacturer** | Contains `STANFORDAIDE` (case-insensitive) |

This is the primary AI marker. Set this on all DICOM outputs from your AI module.

---

## Condition 2: Series Description

| Tag | Value |
|-----|-------|
| **SeriesDescription** | Contains `AI MEASUREMENTS` **OR** `QA VISUALIZATION` (case-insensitive) |

Use these exact strings (or substrings) in your output series:
- **AI Measurements (SR)**: `SeriesDescription = "AI Measurements"` or similar
- **QA Visualization (SC)**: `SeriesDescription = "QA Visualization"` or similar

---

## Condition 3: Software Version Pattern

| Tag | Value |
|-----|-------|
| **SoftwareVersions** | Contains `PEDIATRIC_LEG_LENGTH_V` (case-insensitive) |

Example: `SoftwareVersions = "pediatric_leg_length_v1.0"`

---

## Condition 4: Institution Combo (All Required)

All of the following must match:

| Tag | Value |
|-----|-------|
| **InstitutionName** | `SOM` (case-insensitive) |
| **InstitutionalDepartmentName** | `RADIOLOGY` (case-insensitive) |
| **StationName** | `LPCH` (case-insensitive) |
| **Manufacturer** | Contains `STANFORDAIDE` (case-insensitive) |

---

## Recommendation for Pediatric Leg Length Module

The `mercure-pediatric-leglength` module sets the following in its outputs (see `leglength/outputs.py`):

- **Manufacturer**: `StanfordAIDE`
- **SoftwareVersions**: `pediatric_leg_length_v1.0`
- **InstitutionName**: `SOM`
- **InstitutionalDepartmentName**: `Radiology`
- **StationName**: `LPCH`
- **SeriesDescription** (QA DICOM): `QA Visualization`
- **SeriesDescription** (SR DICOM): `AI Measurements` (via SeriesDescription in headers)

**For your Docker implementation**: Set **at minimum**:
1. `Manufacturer = "StanfordAIDE"` on all output instances
2. `SeriesDescription` = `"QA Visualization"` for QA images, `"AI Measurements"` for SR

That will ensure routing detects your AI output.

---

## Reference

Source: `orthanc/lua-scripts-v2/matcher.lua` → `hasAIResultMarker()`
