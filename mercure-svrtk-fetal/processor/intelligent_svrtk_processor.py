#!/usr/bin/env python3
"""
Intelligent SVRTK Processor for Fetal MRI
==========================================

This script processes complete fetal MRI studies by:
1. Analyzing series descriptions to identify sequence types and anatomy
2. Grouping DICOM series into appropriate reconstruction categories  
3. Running separate SVRTK reconstructions for each group
4. Organizing output results

Categories:
- SSFSEx Brain: Series with "SSFSEx brain"
- FIESTA Brain: Series with "Fiesta brain" or "FIESTA brain" 
- SSFSEx Body: Series with "SSFSEx body"
- FIESTA Body: Series with "Fiesta body" or "FIESTA body"

Usage: python3 intelligent_svrtk_processor.py <input_folder> <output_folder>
"""

import os
import sys
import shutil
import subprocess
import json
import re
import time
from pathlib import Path
import logging
from datetime import datetime
from concurrent.futures import ProcessPoolExecutor, as_completed

try:
    import pydicom
    import pydicom.uid
    PYDICOM_AVAILABLE = True
except ImportError:
    PYDICOM_AVAILABLE = False
    logging.warning("pydicom not available, DICOM processing will be limited")

# Module-level nii2dcm import — must be at top level so DicomMRI is in scope everywhere
try:
    from nii2dcm.run import run_nii2dcm
    from nii2dcm.dcm import DicomMRI
    NII2DCM_AVAILABLE = True
except ImportError:
    run_nii2dcm = None
    DicomMRI = None
    NII2DCM_AVAILABLE = False
    logging.warning("nii2dcm not available, DICOM conversion will be skipped")

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class IntelligentSVRTKProcessor:
    def __init__(self, input_folder, output_folder):
        self.input_folder = Path(input_folder)
        self.output_folder = Path(output_folder)
        
        # Use output folder for temp processing to avoid permission issues
        self.temp_folder = self.output_folder / "temp_processing"
        
        # Create output structure
        self.output_folder.mkdir(parents=True, exist_ok=True)
        self.temp_folder.mkdir(parents=True, exist_ok=True)
        
        # Read Mercure task configuration if available
        self.task_info = self.read_task_json()
        
        # Log basic information
        logger.info(f"Input folder: {self.input_folder}")
        logger.info(f"Output folder: {self.output_folder}")
        logger.info(f"Task info available: {self.task_info is not None}")
        logger.info(f"nii2dcm available: {NII2DCM_AVAILABLE}")
        logger.info(f"DicomMRI class: {DicomMRI}")
        if self.task_info:
            logger.info(f"Processing settings: {self.task_info.get('process', {}).get('settings', {})}")
        
        # Reconstruction categories
        # NOTE: ssfsex is the primary pattern, ssfse is kept as fallback
        # default_thickness: fallback PSF thickness (mm) if DICOM tag is missing
        # output_resolution: reconstruction output voxel size (mm)
        #   Brain: 0.8mm — standard SVR brain resolution
        #   Body:  1.0mm — body DSVR from 4-5mm input slices; 0.8mm is too aggressive
        self.categories = {
            'ssfsex_brain': {
                'patterns': [r'.*ssfsex.*brain.*', r'.*ssfse.*brain.*'],
                'script': '/home/auto-proc-svrtk/scripts/auto-brain-reconstruction.sh',
                'output_dir': 'ssfsex_brain_reconstruction',
                'description': 'SSFSEx Brain',
                'default_thickness': 3.0,
                'output_resolution': 0.8,
            },
            'fiesta_brain': {
                'patterns': [r'.*fiesta.*brain.*'],
                'script': '/home/auto-proc-svrtk/scripts/auto-brain-reconstruction.sh',
                'output_dir': 'fiesta_brain_reconstruction',
                'description': 'FIESTA Brain',
                'default_thickness': 3.0,
                'output_resolution': 0.8,
            },
            'ssfsex_body': {
                'patterns': [r'.*ssfsex.*body.*', r'.*ssfse.*body.*'],
                'script': '/home/auto-proc-svrtk/scripts/auto-body-reconstruction.sh',
                'output_dir': 'ssfsex_body_reconstruction',
                'description': 'SSFSEx Body',
                'default_thickness': 4.0,
                'output_resolution': 1.0,
            },
            'fiesta_body': {
                'patterns': [r'.*fiesta.*body.*'],
                'script': '/home/auto-proc-svrtk/scripts/auto-body-reconstruction.sh',
                'output_dir': 'fiesta_body_reconstruction',
                'description': 'FIESTA Body',
                'default_thickness': 4.0,
                'output_resolution': 1.0,
            }
        }

        # Per-category slice thickness detected from DICOM tags (populated in analyze_dicom_series)
        self.detected_thickness = {}
        # Per-category representative DICOM file for nii2dcm reference (populated in read_dicom_metadata)
        self.category_ref_dicom = {}
        
    def read_task_json(self):
        """Read Mercure task.json configuration if available with race condition protection"""
        task_file = self.input_folder / "task.json"
        if task_file.exists():
            try:
                # Handle race condition during file writing with retry logic
                task_data = self._safe_read_json(task_file)
                logger.info("Successfully read task.json configuration")
                return task_data
            except Exception as e:
                logger.warning(f"Could not read task.json: {e}")
        else:
            logger.info("No task.json found (this is normal for non-Mercure usage)")
        return None
        
    def _safe_read_json(self, file_path, max_retries=5, base_delay=0.1):
        """Safely read JSON file with protection against race conditions during writing"""
        import time
        
        for attempt in range(max_retries):
            try:
                # First check: wait for file size to stabilize
                initial_size = file_path.stat().st_size
                time.sleep(base_delay)  # Allow any ongoing write to continue
                
                # Second check: verify size is stable
                current_size = file_path.stat().st_size
                if initial_size != current_size:
                    logger.debug(f"task.json size changed ({initial_size} -> {current_size}), retrying...")
                    time.sleep(base_delay * (attempt + 1))  # Exponential backoff
                    continue
                
                # File seems stable, try to read and parse JSON
                with open(file_path, 'r') as f:
                    content = f.read()
                    
                # Validate it's complete JSON before parsing
                if not content.strip():
                    raise ValueError("Empty file")
                    
                if not (content.strip().startswith('{') and content.strip().endswith('}')):
                    raise ValueError("JSON appears incomplete")
                    
                # Parse JSON
                task_data = json.loads(content)
                logger.debug(f"Successfully read task.json on attempt {attempt + 1}")
                return task_data
                
            except json.JSONDecodeError as e:
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)  # Exponential backoff
                    logger.warning(f"JSON decode error on attempt {attempt + 1}: {e}. Retrying in {delay:.2f}s...")
                    time.sleep(delay)
                    continue
                else:
                    logger.error(f"Failed to read task.json after {max_retries} attempts: {e}")
                    raise
                    
            except Exception as e:
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    logger.warning(f"Read error on attempt {attempt + 1}: {e}. Retrying in {delay:.2f}s...")
                    time.sleep(delay)
                    continue
                else:
                    logger.error(f"Failed to read task.json after {max_retries} attempts: {e}")
                    raise
        
        raise Exception("Max retries exceeded")
        
    def check_disk_space(self, required_gb=30):
        """Check available disk space before processing to prevent task.json corruption"""
        import shutil
        
        # Check space in output directory
        total, used, free = shutil.disk_usage(self.output_folder)
        free_gb = free / (1024**3)
        
        logger.info(f"Disk space check: {free_gb:.1f} GB available (need {required_gb} GB)")
        
        if free_gb < required_gb:
            logger.error(f"❌ Insufficient disk space: {free_gb:.1f} GB available, need {required_gb} GB")
            logger.error("This can cause task.json corruption and dispatcher loops!")
            return False
            
        if free_gb < required_gb * 2:  # Warning threshold
            logger.warning(f"⚠️ Low disk space: {free_gb:.1f} GB available. Consider cleanup.")
            
        return True
        
    def cleanup_temp_directories(self):
        """Clean up SVRTK temp directories that may not get cleaned up on crash"""
        import glob
        
        cleanup_patterns = [
            '/home/tmp_proc/tmp_proc_*',  # SVRTK temp dirs in home
            '/tmp/tmp_proc_*',      # Legacy temp dirs on root filesystem  
            '/home/tmp_proc/*',     # Old temp dirs in home
        ]
        
        cleaned_count = 0
        for pattern in cleanup_patterns:
            try:
                temp_dirs = glob.glob(pattern)
                for temp_dir in temp_dirs:
                    try:
                        if os.path.isdir(temp_dir):
                            shutil.rmtree(temp_dir, ignore_errors=True)
                            cleaned_count += 1
                            logger.info(f"Cleaned up temp directory: {temp_dir}")
                    except Exception as e:
                        logger.warning(f"Could not clean {temp_dir}: {e}")
            except Exception as e:
                logger.warning(f"Error cleaning pattern {pattern}: {e}")
                
        if cleaned_count > 0:
            logger.info(f"✅ Cleaned up {cleaned_count} temp directories")
        else:
            logger.info("No temp directories found to clean")
            
    def read_dicom_metadata(self, dicom_files):
        """
        Pre-pass: read SliceThickness (and SpacingBetweenSlices) per series from DICOM tags
        before dcm2niix conversion discards per-series metadata.
        Populates self.detected_thickness[category] with the median measured thickness.
        """
        if not PYDICOM_AVAILABLE or not dicom_files:
            return

        logger.info("Reading DICOM metadata to detect actual slice thickness per series...")

        # group by SeriesInstanceUID
        series_meta = {}  # uid -> {'desc': str, 'thicknesses': [float]}
        for dcm_path in dicom_files:
            try:
                ds = pydicom.dcmread(str(dcm_path), stop_before_pixels=True)
                uid = getattr(ds, 'SeriesInstanceUID', None)
                if uid is None:
                    continue
                desc = getattr(ds, 'SeriesDescription', '').strip()
                # Prefer SpacingBetweenSlices if present (more accurate for multi-stack), else SliceThickness
                thickness = None
                for tag in ('SpacingBetweenSlices', 'SliceThickness'):
                    raw = getattr(ds, tag, None)
                    if raw is not None:
                        try:
                            thickness = float(raw)
                            break
                        except (ValueError, TypeError):
                            pass
                if uid not in series_meta:
                    series_meta[uid] = {'desc': desc, 'thicknesses': []}
                if thickness is not None:
                    series_meta[uid]['thicknesses'].append(thickness)
            except Exception:
                pass

        # Match each series to a category and record its median thickness
        import statistics
        category_thicknesses = {cat: [] for cat in self.categories}
        for uid, meta in series_meta.items():
            desc = meta['desc'].lower()
            thicknesses = meta['thicknesses']
            if not thicknesses:
                continue
            median_t = statistics.median(thicknesses)
            for category, cfg in self.categories.items():
                for pattern in cfg['patterns']:
                    if re.match(pattern, desc, re.IGNORECASE):
                        category_thicknesses[category].append(median_t)
                        logger.info(f"  Series '{meta['desc']}' → {category}: SliceThickness={median_t:.2f}mm")
                        break

        # Also store a representative DICOM file per category for nii2dcm reference
        # Use the file from the middle of each series group (more representative than first/last)
        category_dicom_files = {cat: [] for cat in self.categories}
        for dcm_path in dicom_files:
            try:
                ds = pydicom.dcmread(str(dcm_path), stop_before_pixels=True)
                desc = getattr(ds, 'SeriesDescription', '').strip().lower()
                for category, cfg in self.categories.items():
                    for pattern in cfg['patterns']:
                        if re.match(pattern, desc, re.IGNORECASE):
                            category_dicom_files[category].append(dcm_path)
                            break
            except Exception:
                pass
        for category, files in category_dicom_files.items():
            if files:
                mid = files[len(files) // 2]
                self.category_ref_dicom[category] = mid
                logger.info(f"  {category}: ref DICOM = {mid.name}")

        for category, thicknesses in category_thicknesses.items():
            if thicknesses:
                detected = round(statistics.median(thicknesses), 2)
                default = self.categories[category]['default_thickness']
                self.detected_thickness[category] = detected
                if abs(detected - default) > 0.3:
                    logger.warning(
                        f"  \u26a0\ufe0f  {category}: detected thickness {detected}mm differs from "
                        f"default {default}mm \u2014 using detected value"
                    )
                else:
                    logger.info(f"  \u2705 {category}: confirmed thickness {detected}mm")
            else:
                logger.info(f"  {category}: no thickness found in DICOM tags, will use default {self.categories[category]['default_thickness']}mm")

    def analyze_dicom_series(self):
        """Analyze DICOM files and group by series description patterns"""
        logger.info("Analyzing input files...")
        
        # Find all DICOM files
        dicom_files = list(self.input_folder.glob('**/*.dcm')) + list(self.input_folder.glob('**/*.DCM'))
        
        if dicom_files:
            # Pre-pass: read slice thickness from DICOM tags before conversion
            self.read_dicom_metadata(dicom_files)

            logger.info(f"Found {len(dicom_files)} DICOM files - converting to NIfTI format...")
            nifti_conversion_dir = self.temp_folder / "auto_converted_nifti"
            nifti_conversion_dir.mkdir(parents=True, exist_ok=True)
            
            if self.auto_convert_dicom_to_nifti(self.input_folder, nifti_conversion_dir):
                logger.info("✅ DICOM to NIfTI conversion completed successfully")
                nifti_files = list(nifti_conversion_dir.glob('*.nii*'))
                if nifti_files:
                    return self.analyze_nifti_files(nifti_files)
                else:
                    logger.error("No NIfTI files found after conversion")
                    return {cat: [] for cat in self.categories.keys()}
            else:
                logger.error("DICOM to NIfTI conversion failed - trying fallback analysis")
                return self.analyze_dicom_files_directly(dicom_files)
        
        logger.warning("No DICOM files found, looking for NIfTI files...")
        nifti_files = list(self.input_folder.glob('**/*.nii*'))
        if nifti_files:
            logger.info(f"Found {len(nifti_files)} existing NIfTI files")
            return self.analyze_nifti_files(nifti_files)
        
        logger.error("No DICOM or NIfTI files found in input directory")
        return {cat: [] for cat in self.categories.keys()}
    
    def auto_convert_dicom_to_nifti(self, input_dir, output_dir):
        """Automatically convert DICOM files to NIfTI using OpenJPEG-enabled dcm2niix"""
        logger.info("Starting automatic DICOM to NIfTI conversion...")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        dcm2niix_cmd = [
            '/usr/local/bin/dcm2niix_openjpeg',
            '-z', 'n',           # uncompressed NIfTI (faster I/O during recon)
            '-f', '%d_%s_%t_%r', # SeriesDesc_SeriesNum_Date_InstanceNum — unique per stack
            '-o', str(output_dir),
            '-v', '1',
            '-b', 'n',           # no BIDS sidecar
            '-r', 'y',           # always reorder slices by ImagePositionPatient (correct geometry)
            # NOTE: -s y (split 4D) intentionally omitted — Mercure delivers flat per-slice DICOMs
            # which dcm2niix already treats as separate stacks. Adding -s y causes rename-only
            # behaviour on flat DICOM inputs instead of NIfTI output.
            str(input_dir)
        ]
        
        try:
            logger.info(f"Running dcm2niix conversion: {' '.join(dcm2niix_cmd)}")
            result = subprocess.run(dcm2niix_cmd, capture_output=True, text=True, timeout=600, encoding='utf-8', errors='replace')
            
            if result.returncode == 0:
                nifti_files = list(output_dir.glob('*.nii*'))
                if nifti_files:
                    logger.info(f"✅ Successfully converted to {len(nifti_files)} NIfTI files")
                    return True
                else:
                    logger.error("dcm2niix completed but no NIfTI files were created")
                    logger.error(f"dcm2niix stdout: {result.stdout}")
                    logger.error(f"dcm2niix stderr: {result.stderr}")
                    return False
            else:
                logger.error(f"dcm2niix failed with return code {result.returncode}")
                logger.error(f"dcm2niix stderr: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error("dcm2niix conversion timed out after 10 minutes")
            return False
        except FileNotFoundError:
            logger.error("dcm2niix_openjpeg not found at /usr/local/bin/dcm2niix_openjpeg")
            return False
        except Exception as e:
            logger.error(f"Error running dcm2niix conversion: {e}")
            return False
    
    def analyze_dicom_files_directly(self, dicom_files):
        """Fallback method to analyze DICOM files directly using pydicom"""
        logger.info("Analyzing DICOM files directly using pydicom...")
        
        if not PYDICOM_AVAILABLE:
            logger.error("pydicom not available for DICOM processing")
            return {cat: [] for cat in self.categories.keys()}
        
        series_groups = {cat: [] for cat in self.categories.keys()}
        series_info = {}
        
        for dcm_file in dicom_files:
            try:
                ds = pydicom.dcmread(dcm_file, force=True)
                series_uid = getattr(ds, 'SeriesInstanceUID', 'unknown')
                series_desc = getattr(ds, 'SeriesDescription', '').lower()
                
                if series_uid not in series_info:
                    series_info[series_uid] = {'description': series_desc, 'files': []}
                series_info[series_uid]['files'].append(dcm_file)
                
            except Exception as e:
                logger.warning(f"Could not read DICOM file {dcm_file}: {e}")
                continue
        
        logger.info(f"Found {len(series_info)} unique series")
        
        for series_uid, info in series_info.items():
            desc = info['description']
            logger.info(f"Series: '{desc}' ({len(info['files'])} files)")
            
            categorized = False
            for category, config in self.categories.items():
                for pattern in config['patterns']:
                    if re.match(pattern, desc, re.IGNORECASE):
                        series_groups[category].extend(info['files'])
                        logger.info(f"  → Categorized as: {category}")
                        categorized = True
                        break
                if categorized:
                    break
            
            if not categorized:
                logger.warning(f"  → Series not categorized: '{desc}'")
        
        return series_groups
    
    def analyze_nifti_files(self, nifti_files):
        """Analyze NIfTI files based on filename patterns"""
        series_groups = {cat: [] for cat in self.categories.keys()}
        
        for nifti_file in nifti_files:
            filename = nifti_file.name.lower()
            logger.info(f"NIfTI file: {filename}")
            
            categorized = False
            for category, config in self.categories.items():
                for pattern in config['patterns']:
                    clean_pattern = pattern.strip('.*')
                    if re.search(clean_pattern, filename, re.IGNORECASE):
                        series_groups[category].append(nifti_file)
                        logger.info(f"  → Categorized as: {category}")
                        categorized = True
                        break
                if categorized:
                    break
            
            if not categorized:
                logger.warning(f"  → File not categorized: {filename}")
        
        return series_groups
    
    def decompress_dicom_files(self, dicom_files, output_dir):
        """Decompress JPEG 2000 DICOM files using pydicom"""
        if not PYDICOM_AVAILABLE:
            logger.error("pydicom not available for DICOM decompression")
            return False
            
        logger.info(f"Decompressing {len(dicom_files)} JPEG 2000 DICOM files...")
        decompressed_dir = self.temp_folder / "decompressed_dicom"
        decompressed_dir.mkdir(exist_ok=True)
        decompressed_files = []
        
        try:
            for i, dicom_file in enumerate(dicom_files):
                try:
                    ds = pydicom.dcmread(str(dicom_file), force=True)
                    if hasattr(ds, 'TransferSyntaxUID'):
                        if ds.TransferSyntaxUID.name == 'JPEG 2000 Image Compression (Lossless Only)':
                            ds.file_meta.TransferSyntaxUID = pydicom.uid.ExplicitVRLittleEndian
                            ds.is_little_endian = True
                            ds.is_implicit_VR = False
                    output_file = decompressed_dir / f"decompressed_{i:04d}.dcm"
                    ds.save_as(str(output_file))
                    decompressed_files.append(output_file)
                except Exception as e:
                    logger.warning(f"Failed to decompress {dicom_file}: {e}")
                    output_file = decompressed_dir / f"original_{i:04d}.dcm"
                    shutil.copy2(dicom_file, output_file)
                    decompressed_files.append(output_file)
        except Exception as e:
            logger.error(f"Error during DICOM decompression: {e}")
            return False
            
        logger.info(f"✅ Decompressed {len(decompressed_files)} DICOM files")
        return decompressed_files

    def convert_dicom_to_nifti(self, dicom_files, output_dir):
        """Convert DICOM files to NIfTI format, handling compressed DICOMs"""
        logger.info(f"Converting {len(dicom_files)} DICOM files to NIfTI...")
        
        decompressed_files = self.decompress_dicom_files(dicom_files, output_dir)
        files_to_convert = decompressed_files if decompressed_files else dicom_files
        
        temp_dicom_dir = self.temp_folder / "dicom_input"
        temp_dicom_dir.mkdir(exist_ok=True)
        
        for i, dicom_file in enumerate(files_to_convert):
            shutil.copy2(dicom_file, temp_dicom_dir / f"file_{i:04d}.dcm")
        
        nifti_output_dir = self.temp_folder / "nifti_output"
        nifti_output_dir.mkdir(exist_ok=True)
        
        dcm2niix_cmd = [
            '/usr/local/bin/dcm2niix_openjpeg',
            '-o', str(nifti_output_dir),
            '-f', '%p_%t_%s',
            '-z', 'n',           # uncompressed NIfTI — faster I/O during recon
            '-b', 'n',           # no BIDS sidecar
            '-r', 'y',           # reorder slices by ImagePositionPatient
            str(temp_dicom_dir)
        ]
        
        try:
            result = subprocess.run(dcm2niix_cmd, capture_output=True, text=True)
            if result.returncode == 0:
                nifti_files = list(nifti_output_dir.glob("*.nii.gz"))
                if nifti_files:
                    output_dir.mkdir(parents=True, exist_ok=True)
                    for nifti_file in nifti_files:
                        shutil.copy2(nifti_file, output_dir / nifti_file.name)
                    logger.info(f"✅ Successfully converted to {len(nifti_files)} NIfTI files")
                    return True
                else:
                    logger.warning("dcm2niix_openjpeg completed but no NIfTI files found")
            else:
                logger.warning(f"dcm2niix_openjpeg failed: {result.stderr}")
        except FileNotFoundError:
            logger.warning("dcm2niix_openjpeg not found")
        
        logger.error("❌ Failed to convert DICOM to NIfTI")
        return False

    def prepare_reconstruction_inputs(self, series_groups):
        """Prepare input folders for each reconstruction category"""
        reconstruction_jobs = []
        
        for category, files in series_groups.items():
            if not files:
                logger.info(f"No files found for {category}, skipping...")
                continue
                
            logger.info(f"Preparing {category} reconstruction with {len(files)} files")
            
            input_dir = self.temp_folder / f"input_{category}"
            output_dir = self.output_folder / self.categories[category]['output_dir']
            
            input_dir.mkdir(parents=True, exist_ok=True)
            output_dir.mkdir(parents=True, exist_ok=True)
            
            for i, file_path in enumerate(files):
                dest_path = input_dir / f"{category}_{i:03d}{file_path.suffix}"
                shutil.copy2(file_path, dest_path)
                logger.info(f"📁 Copied {file_path.name} → {dest_path.name}")
                
            input_files = list(input_dir.glob("*.nii*"))
            logger.info(f"📋 Input directory {input_dir.name} contains {len(input_files)} NIfTI files:")
            for f in input_files:
                logger.info(f"   - {f.name}")
            
            # Determine slice thickness: use DICOM-detected value if available, else default
            cat_cfg = self.categories[category]
            detected_t = self.detected_thickness.get(category)
            slice_thickness = detected_t if detected_t is not None else cat_cfg['default_thickness']
            output_resolution = cat_cfg['output_resolution']

            # Stack count advisory (no hard minimum — reconstruction proceeds regardless)
            min_ideal = 4 if 'brain' in category else 5
            if len(files) < min_ideal:
                logger.warning(
                    f"  ⚠️  {category}: only {len(files)} NIfTI stack(s) — ideal is ≥{min_ideal}. "
                    f"Proceeding anyway; quality may be reduced."
                )
            elif len(files) < 7:
                logger.warning(
                    f"  ⚠️  {category}: {len(files)} stacks is marginal — ideal is ≥7. "
                    f"Proceeding; quality may be reduced."
                )

            logger.info(
                f"  {category}: thickness={slice_thickness}mm "
                f"({'detected' if detected_t is not None else 'default'}), "
                f"output_res={output_resolution}mm"
            )

            reconstruction_jobs.append({
                'category': category,
                'description': cat_cfg['description'],
                'input_dir': input_dir,
                'output_dir': output_dir,
                'script': cat_cfg['script'],
                'file_count': len(files),
                'slice_thickness': slice_thickness,
                'output_resolution': output_resolution,
            })
        
        return reconstruction_jobs
    
    def validate_reconstruction_outputs(self, category, output_dir):
        """
        Validate that expected SVRTK reconstruction output files exist.
        Returns list of found files, or empty list if validation fails.
        """
        expected_files = {
            'ssfsex_brain': ['reo-SVR-output-brain.nii.gz', 'SVR-output-brain.nii.gz'],
            'fiesta_brain': ['reo-SVR-output-brain.nii.gz', 'SVR-output-brain.nii.gz'],
            'ssfsex_body': ['reo-DSVR-output-body.nii.gz', 'DSVR-output-body.nii.gz'],
            'fiesta_body': ['reo-DSVR-output-body.nii.gz', 'DSVR-output-body.nii.gz'],
        }
        
        category_files = expected_files.get(category, ['reo-SVR-output.nii.gz', 'SVR-output.nii.gz'])
        found_files = []
        
        for expected_file in category_files:
            file_path = output_dir / expected_file
            if file_path.exists() and file_path.stat().st_size > 1024:  # At least 1KB
                found_files.append(str(file_path))
                logger.info(f"✓ Found valid output: {file_path}")
            else:
                logger.warning(f"✗ Missing or empty output: {file_path}")
        
        # Also check for any .nii.gz files containing reconstruction keywords
        additional_outputs = []
        for nifti_file in output_dir.glob('**/*.nii.gz'):
            if any(keyword in nifti_file.name.lower() for keyword in ['svr', 'dsvr', 'recon', 'output']):
                if nifti_file.stat().st_size > 1024:  # At least 1KB  
                    additional_outputs.append(str(nifti_file))
                    
        if additional_outputs and not found_files:
            logger.info(f"Found alternative reconstruction outputs: {additional_outputs}")
            found_files.extend(additional_outputs)
        
        return found_files

    def run_svrtk_reconstruction(self, job):
        """Run SVRTK reconstruction for a specific job with isolated working directory"""
        category = job['category']
        description = job['description']
        input_dir = job['input_dir']
        output_dir = job['output_dir']
        script = job['script']
        
        # Create unique working directory for this job to prevent parallel collisions  
        # Use /tmp which is always available and writable in container
        import time
        unique_work_dir = f"/tmp/tmp_proc_{category}_{int(time.time() * 1000000) % 1000000}_{os.getpid()}"
        
        # Ensure cleanup happens even if job fails
        temp_dirs_to_cleanup = [unique_work_dir]
        
        logger.info("")
        logger.info("=" * 80)
        logger.info(f"RUNNING {description.upper()} RECONSTRUCTION")
        logger.info("=" * 80)
        logger.info(f"Input: {input_dir}")
        logger.info(f"Output: {output_dir}")
        logger.info(f"Script: {script}")
        logger.info(f"Files: {job['file_count']}")
        logger.info(f"Working Dir: {unique_work_dir}")
        
        slice_thickness = job['slice_thickness']
        output_resolution = job['output_resolution']
        is_body = category in ('ssfsex_body', 'fiesta_body')

        # SVRTK threads: ~25% of physical CPUs per job, min 2, max 8.
        # On a 16C prod machine this gives 4 threads/job; on larger servers it scales up automatically.
        _cpu_count = os.cpu_count() or 4
        svrtk_threads = max(2, min(8, _cpu_count // 4))

        # Build sed pipeline:
        # 1. Always: redirect default_run_dir to unique temp dir (isolation for parallel jobs)
        # 2. Body only: patch hardcoded SVRTK parameters for better clinical quality:
        #    - iterations 2→4: two extra EM loops; SVRTK authors recommend 3-4 for body DSVR
        #    - exclusion_ncc 0.45→0.55: exclude slices with NCC<0.55 (more aggressive motion rejection)
        #    - exclusion_ssim 0.25→0.40: exclude slices with SSIM<0.40
        #    - stacks-selection 11→15: allow up to 15 stacks instead of 11 (more data = better recon)
        #    - lambda 0.018→0.014: default calibrated for 0.55T low-field; at 1.5T+ less smoothing needed
        #    - cp 12 9→14 10: finer FFD control point grid captures respiratory motion more precisely
        #    - lastIter 0.008→0.006: finer step size for final EM pass improves convergence
        #    NOTE: -delta kept at default 110 (controls per-voxel EM weighting, not slice exclusion;
        #          conservative default is fine for clinical body data)
        sed_pipeline = f"sed 's|default_run_dir=/home/tmp_proc|default_run_dir={unique_work_dir}|g' {script}"
        if is_body:
            sed_pipeline += (
                " | sed 's|-iterations 2 |-iterations 4 |g'"
                " | sed 's|-exclusion_ncc 0.45 |-exclusion_ncc 0.55 |g'"
                " | sed 's|-exclusion_ssim 0.25 |-exclusion_ssim 0.40 |g'"
                " | sed 's|} 11 1 0.5|} 15 1 0.5|g'"
                " | sed 's|-lambda 0.018 |-lambda 0.014 |g'"
                " | sed 's|-cp 12 9 |-cp 14 10 |g'"
                " | sed 's|-lastIter 0.008 |-lastIter 0.006 |g'"
            )

        cmd = [
            'bash', '-c',
            f"{sed_pipeline} | bash -s -- {input_dir} {output_dir} {svrtk_threads} {slice_thickness} {output_resolution} 1"
        ]
        
        logger.info(f"Command: {' '.join(cmd)}")
        logger.info(f"Slice thickness: {job['slice_thickness']}mm | Output resolution: {job['output_resolution']}mm")
        logger.info("")
        
        try:
            # Stream output in real-time so SVRTK progress is visible during long reconstructions
            import threading

            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,  # merge stderr into stdout for unified stream
                text=True,
                encoding='utf-8',
                errors='replace',
            )

            def _stream_output(pipe):
                for line in iter(pipe.readline, ''):
                    stripped = line.rstrip()
                    if stripped:
                        logger.info(f"  [SVRTK] {stripped}")
                pipe.close()

            reader_thread = threading.Thread(target=_stream_output, args=(proc.stdout,), daemon=True)
            reader_thread.start()

            try:
                proc.wait(timeout=3600)
            except subprocess.TimeoutExpired:
                proc.kill()
                reader_thread.join(timeout=5)
                logger.error(f"❌ {description} reconstruction TIMED OUT after 1 hour")
                for temp_dir in temp_dirs_to_cleanup:
                    try:
                        if os.path.exists(temp_dir):
                            shutil.rmtree(temp_dir, ignore_errors=True)
                    except Exception:
                        pass
                return False

            reader_thread.join(timeout=10)
            returncode = proc.returncode

            # Always cleanup unique_work_dir
            for temp_dir in temp_dirs_to_cleanup:
                try:
                    if os.path.exists(temp_dir):
                        shutil.rmtree(temp_dir, ignore_errors=True)
                        logger.debug(f"Cleaned up job temp dir: {temp_dir}")
                except Exception as cleanup_e:
                    logger.warning(f"Could not clean job temp dir {temp_dir}: {cleanup_e}")

            if returncode == 0:
                # Check for actual reconstruction outputs, not just exit code
                expected_outputs = self.validate_reconstruction_outputs(category, output_dir)
                if expected_outputs:
                    logger.info(f"✅ {description} reconstruction COMPLETED SUCCESSFULLY")
                    output_files = list(output_dir.glob('**/*'))
                    logger.info(f"Generated {len(output_files)} output files/folders")
                    logger.info(f"Validated expected outputs: {expected_outputs}")
                    return True
                else:
                    logger.error(f"❌ {description} reconstruction FAILED - expected output files not found")
                    logger.error("Process exited successfully but produced no valid reconstruction outputs")
                    return False
            else:
                logger.error(f"❌ {description} reconstruction FAILED (exit code {returncode})")
                return False
        except Exception as e:
            logger.error(f"❌ {description} reconstruction FAILED with exception: {e}")
            import traceback
            logger.error(traceback.format_exc())
            # Cleanup on exception
            for temp_dir in temp_dirs_to_cleanup:
                try:
                    if os.path.exists(temp_dir):
                        shutil.rmtree(temp_dir, ignore_errors=True)
                        logger.info(f"Cleaned up temp dir after exception: {temp_dir}")
                except:
                    pass
            return False
    
    def determine_reference_dicom(self, dicom_files):
        """Determine which DICOM file to use as reference for metadata transfer"""
        if not PYDICOM_AVAILABLE:
            logger.warning("pydicom not available, using first DICOM file as reference")
            return dicom_files[0] if dicom_files else None
            
        series_numbers = []
        valid_dicom_files = []
        
        for file_path in dicom_files:
            try:
                dcm = pydicom.dcmread(str(file_path))
                if hasattr(dcm, 'Modality') and 'MR' in dcm.Modality:
                    series_numbers.append(int(dcm.SeriesNumber))
                    valid_dicom_files.append(file_path)
            except Exception as e:
                logger.warning(f"File {file_path} does not appear to be valid DICOM: {e}")
                
        if not valid_dicom_files:
            logger.warning("No valid MR DICOM files found for reference")
            return dicom_files[0] if dicom_files else None
            
        series_numbers_sorted = sorted(enumerate(series_numbers), key=lambda x: x[1])
        ref_index = series_numbers_sorted[0][0]
        ref_dicom = valid_dicom_files[ref_index]
        
        logger.info(f"Selected DICOM reference file: {ref_dicom}")
        return ref_dicom
    
    def convert_nifti_to_dicom(self, nifti_file, output_dir, ref_dicom_file=None, series_description=None, output_resolution=None):
        """
        Convert NIfTI reconstruction to DICOM using nii2dcm.
        DicomMRI is imported at module level to ensure it is always in scope.
        """
        if not NII2DCM_AVAILABLE:
            logger.error("❌ nii2dcm not available - cannot convert NIfTI to DICOM")
            return False

        try:
            logger.info(f"Converting NIfTI to DICOM: {nifti_file}")
            logger.info(f"Output directory: {output_dir}")
            logger.info(f"Series description: {series_description}")
            logger.info(f"Using dicom_type: MR")

            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)

            # Pass "MR" as string for dicom_type parameter
            run_nii2dcm(
                Path(nifti_file),
                output_dir,
                dicom_type="MR",
                ref_dicom_file=Path(ref_dicom_file) if ref_dicom_file else None,
            )

            # Post-process output DICOM files to set correct clinical tags
            dicom_files = list(output_dir.glob('*.dcm'))
            if dicom_files and PYDICOM_AVAILABLE:
                logger.info(f"Post-processing {len(dicom_files)} DICOM files to set clinical tags")

                # Read reference DICOM to steal a valid SeriesNumber offset and WindowCenter
                ref_series_number = 900
                if ref_dicom_file:
                    try:
                        ref_ds = pydicom.dcmread(str(ref_dicom_file), stop_before_pixels=True)
                        ref_series_number = int(getattr(ref_ds, 'SeriesNumber', 900)) + 100
                    except Exception:
                        pass

                # SVRTK final output is rescaled to int16 [0, 5000] by the shell scripts.
                # Window/level: center=1250, width=3500 covers the full clinical useful range.
                window_center = 1250
                window_width = 3500

                voxel_size_str = f"{output_resolution:.2f}" if output_resolution else "1.00"

                for i, dcm_file in enumerate(sorted(dicom_files)):
                    try:
                        ds = pydicom.dcmread(str(dcm_file))

                        # Series identity
                        if series_description:
                            ds.SeriesDescription = series_description
                        ds.SeriesNumber = ref_series_number
                        ds.ImageComments = "SVRTK Fetal MRI Reconstruction"
                        ds.SoftwareVersions = "SVRTK v8"

                        # Geometry tags — reflect the actual output voxel size
                        if output_resolution is not None:
                            ds.SliceThickness = float(output_resolution)
                            ds.PixelSpacing = [float(output_resolution), float(output_resolution)]
                            ds.SpacingBetweenSlices = float(output_resolution)

                        # Window/level for PACS display — correct for SVRTK int16 [0,5000] output
                        ds.WindowCenter = window_center
                        ds.WindowWidth = window_width
                        if hasattr(ds, 'WindowCenterWidthExplanation'):
                            ds.WindowCenterWidthExplanation = 'SVRTK Default'

                        ds.save_as(str(dcm_file))
                    except Exception as fix_e:
                        logger.warning(f"Could not post-process tags in {dcm_file.name}: {fix_e}")

            dicom_files = list(output_dir.glob('*.dcm'))
            if dicom_files:
                logger.info(f"✅ Successfully converted to {len(dicom_files)} DICOM files")
                if series_description and PYDICOM_AVAILABLE:
                    try:
                        test_ds = pydicom.dcmread(str(dicom_files[0]))
                        actual_desc = getattr(test_ds, 'SeriesDescription', '')
                        logger.info(f"Series description verified: '{actual_desc}'")
                        logger.info(f"Window Center/Width: {getattr(test_ds, 'WindowCenter', '?')}/{getattr(test_ds, 'WindowWidth', '?')}")
                    except Exception:
                        pass
                return True
            else:
                logger.error("❌ DICOM conversion failed - no output files generated")
                return False

        except Exception as e:
            logger.error(f"❌ NIfTI to DICOM conversion failed: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    def run_segmentation(self, job):
        """
        Run SVRTK segmentation on a completed reconstruction output.
        Only FIESTA categories are segmented — SSFSEx is skipped because all
        segmentation models (BOUNTI, body organs, lung lobes) are trained on
        bSSFP/FIESTA data and produce unreliable results on SSFSEx contrast.

        Brain categories: auto-brain-bounti-segmentation-fetal.sh  (19-label parcellation + BET mask)
        Body  categories: auto-body-organ-segmentation.sh (10-label organs)
                        + auto-lung-segmentation.sh       (5-label lung lobes)

        Returns a list of dicts:
          {'nifti_file': Path, 'seg_type': str, 'category': str, 'description': str}
        """
        category = job['category']
        output_dir = job['output_dir']
        is_brain = 'brain' in category

        if 'ssfsex' in category:
            logger.info(
                f"Segmentation skipped for {category}: SSFSEx contrast not supported by "
                f"segmentation models (trained on FIESTA/bSSFP data only)"
            )
            return []

        recon_nifti_name = 'reo-SVR-output-brain.nii.gz' if is_brain else 'reo-DSVR-output-body.nii.gz'
        recon_nifti = output_dir / recon_nifti_name

        if not recon_nifti.exists():
            logger.warning(
                f"Segmentation skipped for {category}: reconstruction output not found: {recon_nifti}"
            )
            return []

        # Create a dedicated input folder with just the reconstruction NIfTI
        seg_input_dir = self.temp_folder / f"seg_input_{category}"
        seg_input_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(recon_nifti, seg_input_dir / recon_nifti.name)

        # Source label for PACS series description (SSFSEx vs FIESTA)
        src_label = 'SSFSEx' if 'ssfsex' in category else 'FIESTA'

        if is_brain:
            scripts_to_run = [
                (
                    '/home/auto-proc-svrtk/scripts/auto-brain-bounti-segmentation-fetal.sh',
                    'brain_bounti',
                    f'SVRTK BOUNTI Brain Parcellation ({src_label})',
                ),
            ]
        else:
            # Body organ segmentation removed — only lung lobes retained per clinical review
            scripts_to_run = [
                (
                    '/home/auto-proc-svrtk/scripts/auto-lung-segmentation.sh',
                    'lung',
                    f'SVRTK Lung Lobe Segmentation ({src_label})',
                ),
            ]

        seg_results = []
        import threading as _threading

        for script, seg_type, description in scripts_to_run:
            seg_output_dir = output_dir / f'seg_{seg_type}'
            seg_output_dir.mkdir(parents=True, exist_ok=True)

            unique_work_dir = (
                f"/tmp/tmp_seg_{category}_{seg_type}_{int(time.time() * 1000000) % 1000000}_{os.getpid()}"
            )

            sed_cmd = (
                f"sed 's|default_run_dir=/home/tmp_proc|default_run_dir={unique_work_dir}|g' {script}"
            )
            cmd = ['bash', '-c', f"{sed_cmd} | bash -s -- {seg_input_dir} {seg_output_dir}"]

            logger.info(f"")
            logger.info(f"Starting {seg_type} segmentation for {category}...")
            logger.info(f"  Input:  {seg_input_dir}")
            logger.info(f"  Output: {seg_output_dir}")
            logger.info(f"  Workdir: {unique_work_dir}")

            try:
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding='utf-8',
                    errors='replace',
                )

                def _stream(pipe):
                    for line in iter(pipe.readline, ''):
                        stripped = line.rstrip()
                        if stripped:
                            logger.info(f"[seg:{seg_type}] {stripped}")

                reader = _threading.Thread(target=_stream, args=(proc.stdout,), daemon=True)
                reader.start()
                proc.wait()
                reader.join(timeout=5)

                if proc.returncode != 0:
                    logger.error(
                        f"❌ {seg_type} segmentation failed (exit code {proc.returncode}) for {category}"
                    )
                    continue

                output_niftis = (
                    list(seg_output_dir.glob('*.nii.gz')) + list(seg_output_dir.glob('*.nii'))
                )

                if not output_niftis:
                    logger.error(f"❌ No segmentation output files found in {seg_output_dir}")
                    continue

                logger.info(
                    f"✅ {seg_type} segmentation complete — {len(output_niftis)} output file(s)"
                )
                for nifti in output_niftis:
                    # BET mask and BOUNTI-19 have distinct filenames; give each its own description
                    if seg_type == 'brain_bounti' and '-mask-bet-1' in nifti.name:
                        nifti_desc = f'SVRTK Brain BET Mask ({src_label})'
                    else:
                        nifti_desc = description
                    seg_results.append({
                        'nifti_file':  nifti,
                        'seg_type':    seg_type,
                        'category':    category,
                        'description': nifti_desc,
                    })

            except Exception as exc:
                logger.error(f"❌ {seg_type} segmentation error for {category}: {exc}")
                import traceback
                logger.error(traceback.format_exc())
            finally:
                # Clean up unique work dir
                try:
                    if os.path.isdir(unique_work_dir):
                        shutil.rmtree(unique_work_dir, ignore_errors=True)
                except Exception:
                    pass

        return seg_results

    def convert_segmentations_to_dicom(self, seg_results, reconstruction_jobs, original_dicom_files):
        """
        Convert segmentation label-map NIfTIs to DICOM series.

        Each segmentation output is written as a separate series.  Window/level is set
        to display all integer label values; SeriesNumber is offset by 200+ from the
        reconstruction ref so the series appear after reconstructions in PACS.
        """
        if not NII2DCM_AVAILABLE or not PYDICOM_AVAILABLE:
            logger.warning("nii2dcm/pydicom not available — skipping segmentation DICOM conversion")
            return []

        if not seg_results:
            return []

        logger.info("=" * 80)
        logger.info("CONVERTING SEGMENTATION OUTPUTS TO DICOM")
        logger.info("=" * 80)

        # Build category → ref_dicom mapping from reconstruction jobs
        job_ref_map = {}
        for job in reconstruction_jobs:
            job_ref_map[job['category']] = self.category_ref_dicom.get(
                job['category'],
                self.determine_reference_dicom(original_dicom_files),
            )

        # Window/level presets for each label-map type
        wl_presets = {
            'brain_bounti': (10, 20),   # 19 labels → W=20, C=10
            'body_organ':   (5,  10),   # 10 labels → W=10, C=5
            'lung':         (3,   6),   # 5  labels → W=6,  C=3
        }
        # SeriesNumber offset from ref (reconstruction already uses +100)
        seg_series_offset = {
            'brain_bounti': 200,
            'body_organ':   210,
            'lung':         220,
        }

        successful = []
        for idx, seg in enumerate(seg_results):
            nifti_file  = seg['nifti_file']
            seg_type    = seg['seg_type']
            category    = seg['category']
            description = seg['description']

            ref_dicom = job_ref_map.get(category)
            dicom_output_dir = nifti_file.parent / f'dicom_{nifti_file.stem.replace(".", "_")}'

            wc, ww = wl_presets.get(seg_type, (10, 20))
            offset  = seg_series_offset.get(seg_type, 200) + idx

            logger.info(f"Converting segmentation: {nifti_file.name} ({description})")

            dicom_output_dir.mkdir(parents=True, exist_ok=True)
            try:
                run_nii2dcm(
                    Path(nifti_file),
                    dicom_output_dir,
                    dicom_type="MR",
                    ref_dicom_file=Path(ref_dicom) if ref_dicom else None,
                )
            except Exception as exc:
                logger.error(f"❌ nii2dcm failed for {nifti_file.name}: {exc}")
                continue

            dcm_files = list(dicom_output_dir.glob('*.dcm'))
            if not dcm_files:
                logger.error(f"❌ No DICOM output for segmentation {nifti_file.name}")
                continue

            # Post-process: set series description, W/L, SeriesNumber, comments
            ref_series_number = offset + 900
            if ref_dicom:
                try:
                    ref_ds = pydicom.dcmread(str(ref_dicom), stop_before_pixels=True)
                    ref_series_number = int(getattr(ref_ds, 'SeriesNumber', 900)) + offset
                except Exception:
                    pass

            for dcm_file in dcm_files:
                try:
                    ds = pydicom.dcmread(str(dcm_file))
                    ds.SeriesDescription = description
                    ds.SeriesNumber      = ref_series_number
                    ds.ImageComments     = "SVRTK Fetal MRI Segmentation"
                    ds.SoftwareVersions  = "SVRTK v8"
                    ds.WindowCenter      = wc
                    ds.WindowWidth       = ww
                    if hasattr(ds, 'WindowCenterWidthExplanation'):
                        ds.WindowCenterWidthExplanation = 'Segmentation Labels'
                    ds.save_as(str(dcm_file))
                except Exception as fix_e:
                    logger.warning(f"Could not post-process seg DICOM {dcm_file.name}: {fix_e}")

            logger.info(f"✅ Segmentation DICOM written: {len(dcm_files)} files → {dicom_output_dir}")
            successful.append({
                'seg_type':    seg_type,
                'category':    category,
                'description': description,
                'dicom_dir':   dicom_output_dir,
            })

        logger.info(
            f"Segmentation DICOM conversion complete: {len(successful)}/{len(seg_results)} successful"
        )
        return successful

    def push_segmentations_to_orthanc(self, seg_dicom_results):
        """
        Push segmentation DICOM series directly to Orthanc via REST API.
        Segmentation results are stored in Orthanc only — not dispatched to PACS.
        """
        if not seg_dicom_results:
            return

        import requests

        orthanc_url  = os.environ.get('ORTHANC_URL', 'http://172.17.0.1:9010')
        orthanc_user = os.environ.get('ORTHANC_ADMIN_USER', 'orthanc_admin')
        orthanc_pass = os.environ.get('ORTHANC_ADMIN_PASS', '')
        instances_url = f"{orthanc_url.rstrip('/')}/instances"

        logger.info("=" * 80)
        logger.info("PUSHING SEGMENTATION DICOMs TO ORTHANC (not PACS)")
        logger.info("=" * 80)

        total_pushed = 0
        total_failed = 0

        for seg in seg_dicom_results:
            dicom_dir   = seg['dicom_dir']
            description = seg['description']
            dcm_files   = [f for f in dicom_dir.glob('*.dcm') if f.name != 'temp_ref.dcm']

            if not dcm_files:
                logger.warning(f"No DICOM files found in {dicom_dir} for '{description}'")
                continue

            logger.info(f"Pushing {len(dcm_files)} files for '{description}'...")
            for dcm_file in dcm_files:
                try:
                    with open(dcm_file, 'rb') as fh:
                        resp = requests.post(
                            instances_url,
                            data=fh.read(),
                            headers={'Content-Type': 'application/dicom'},
                            auth=(orthanc_user, orthanc_pass),
                            timeout=30,
                        )
                    if resp.status_code in (200, 409):  # 409 = already exists, still fine
                        total_pushed += 1
                    else:
                        logger.warning(
                            f"Orthanc rejected {dcm_file.name}: HTTP {resp.status_code}"
                        )
                        total_failed += 1
                except Exception as push_exc:
                    logger.error(f"Failed to push {dcm_file.name} to Orthanc: {push_exc}")
                    total_failed += 1

            logger.info(f"  '{description}': {total_pushed} pushed, {total_failed} failed")

        logger.info(
            f"✅ Orthanc segmentation push complete: {total_pushed} files pushed, {total_failed} failed"
        )

    def convert_reconstruction_outputs_to_dicom(self, reconstruction_jobs, original_dicom_files):
        """
        Convert ALL reconstruction outputs to DICOM only after all jobs have completed.
        This ensures we wait for all 4 reconstruction types before starting conversion.
        """
        logger.info("=" * 80)
        logger.info("ALL RECONSTRUCTIONS COMPLETE — STARTING DICOM CONVERSION")
        logger.info("=" * 80)

        if not NII2DCM_AVAILABLE:
            logger.error("❌ nii2dcm not available at module level - cannot convert to DICOM")
            return []

        # Find reference DICOM file for metadata
        ref_dicom = self.determine_reference_dicom(original_dicom_files)
        if not ref_dicom:
            logger.warning("No reference DICOM file available for metadata transfer")
            
        dicom_conversions = []

        # Map category to expected output file and series description
        category_config = {
            'ssfsex_brain': {
                'output_file': 'reo-SVR-output-brain.nii.gz',
                'series_description': 'SVRTK SSFSEx Brain Reconstruction'
            },
            'fiesta_brain': {
                'output_file': 'reo-SVR-output-brain.nii.gz',
                'series_description': 'SVRTK FIESTA Brain Reconstruction'
            },
            'ssfsex_body': {
                'output_file': 'reo-DSVR-output-body.nii.gz',
                'series_description': 'SVRTK SSFSEx Body Reconstruction'
            },
            'fiesta_body': {
                'output_file': 'reo-DSVR-output-body.nii.gz',
                'series_description': 'SVRTK FIESTA Body Reconstruction'
            },
        }

        logger.info(f"Converting {len(reconstruction_jobs)} completed reconstructions to DICOM...")

        for job in reconstruction_jobs:
            category = job['category']
            output_dir = job['output_dir']
            output_resolution = job.get('output_resolution')

            cfg = category_config.get(category, {
                'output_file': 'reo-SVR-output.nii.gz',
                'series_description': 'SVRTK Research Reconstruction'
            })

            expected_output = output_dir / cfg['output_file']
            series_description = cfg['series_description']

            if not expected_output.exists():
                logger.error(f"❌ Expected output not found for {category}: {expected_output}")
                # Mark this as a failed reconstruction
                dicom_conversions.append({
                    'category': category,
                    'nifti_file': None,
                    'dicom_dir': None,
                    'series_description': series_description,
                    'success': False,
                    'error': 'Expected reconstruction output file not found'
                })
                continue

            # Use category-matched reference DICOM (brain ref for brain recon, body ref for body)
            # Falls back to global ref_dicom if category-specific one not available
            cat_ref_dicom = self.category_ref_dicom.get(category, ref_dicom)
            if cat_ref_dicom and cat_ref_dicom != ref_dicom:
                logger.info(f"  Using category-matched ref DICOM for {category}: {Path(cat_ref_dicom).name}")

            logger.info(f"Converting {category}: {expected_output}")
            dicom_output_dir = output_dir / 'dicom_series'

            success = self.convert_nifti_to_dicom(
                expected_output,
                dicom_output_dir,
                cat_ref_dicom,
                series_description,
                output_resolution=output_resolution,
            )

            if success:
                dicom_conversions.append({
                    'category': category,
                    'nifti_file': expected_output,
                    'dicom_dir': dicom_output_dir,
                    'series_description': series_description
                })
                logger.info(f"✅ {category} DICOM conversion successful")
            else:
                logger.error(f"❌ {category} DICOM conversion failed")
                    
        logger.info(f"DICOM conversion complete: {len(dicom_conversions)}/{len(reconstruction_jobs)} successful")
        return dicom_conversions
    
    def copy_reconstructed_dicom_files(self):
        """Copy reconstructed DICOM files from subdirectories to main output for Mercure dispatch"""
        logger.info("Copying reconstructed DICOM files to main output directory...")
        
        # Only copy reconstruction dirs — segmentation DICOMs go directly to Orthanc, not PACS
        dicom_series_dirs = list(self.output_folder.glob('**/dicom_series'))
        
        if not dicom_series_dirs:
            logger.warning("No dicom_series directories found in output")
            all_dicom_files = list(self.output_folder.glob('**/*.dcm')) + list(self.output_folder.glob('**/*.DCM'))
            recon_dicom_files = [f for f in all_dicom_files if 'reconstruction' in str(f.parent)]
            if recon_dicom_files:
                logger.info(f"Found {len(recon_dicom_files)} DICOM files in reconstruction subdirectories as fallback")
                for dicom_file in recon_dicom_files:
                    output_filename = f"svr_reconstructed_{dicom_file.parent.name}_{dicom_file.name}"
                    output_path = self.output_folder / output_filename
                    try:
                        shutil.copy2(dicom_file, output_path)
                        logger.info(f"Copied {dicom_file.name} → {output_filename}")
                    except Exception as e:
                        logger.error(f"Failed to copy {dicom_file}: {e}")
            return
        
        copied_count = 0
        for series_dir in dicom_series_dirs:
            logger.info(f"Processing DICOM series directory: {series_dir}")
            dicom_files = list(series_dir.glob('*.dcm')) + list(series_dir.glob('*.DCM'))
            # Exclude temp_ref.dcm — it's the reference file, not a real output slice
            dicom_files = [f for f in dicom_files if f.name != 'temp_ref.dcm']
            logger.info(f"Found {len(dicom_files)} DICOM files in {series_dir}")
            
            for dicom_file in dicom_files:
                output_filename = f"svr_reconstructed_{series_dir.parent.name}_{dicom_file.name}"
                output_path = self.output_folder / output_filename
                try:
                    shutil.copy2(dicom_file, output_path)
                    copied_count += 1
                except Exception as e:
                    logger.error(f"Failed to copy {dicom_file}: {e}")
        
        # CRITICAL FIX: Create a dummy NIfTI file so Mercure's process_svrtk_outputs() 
        # finds something and doesn't skip the outgoing copy step
        dummy_nifti = self.output_folder / "svrtk_reconstruction_complete.nii.gz"
        try:
            # Create a minimal valid NIfTI file (just header)
            import numpy as np
            import nibabel as nib
            dummy_data = np.zeros((2, 2, 2), dtype=np.float32)
            dummy_img = nib.Nifti1Image(dummy_data, np.eye(4))
            nib.save(dummy_img, str(dummy_nifti))
            logger.info(f"Created dummy NIfTI file to trigger Mercure outgoing copy: {dummy_nifti}")
        except Exception as e:
            logger.warning(f"Could not create dummy NIfTI file (this may cause outgoing copy issues): {e}")
        
        logger.info(f"✅ Copied {copied_count} reconstructed DICOM files to main output directory")
    
    def process_study(self):
        """Main processing pipeline"""
        logger.info("Starting intelligent SVRTK processing...")
        logger.info(f"Input folder: {self.input_folder}")
        logger.info(f"Output folder: {self.output_folder}")

        # Step 0: Check disk space and clean up old temp files
        logger.info("Performing pre-processing checks...")
        
        # Clean up any stale temp directories from previous failed runs
        self.cleanup_temp_directories()
        
        # Check available disk space to prevent task.json corruption
        if not self.check_disk_space(required_gb=30):
            logger.error("❌ Aborting due to insufficient disk space")
            logger.error("Low disk space can cause task.json corruption and dispatcher loops!")
            return False

        # Confirm nii2dcm is available before we do any work
        if not NII2DCM_AVAILABLE:
            logger.error("❌ nii2dcm not available at startup — DICOM conversion will fail!")
        else:
            logger.info(f"✅ nii2dcm ready, DicomMRI={DicomMRI}")
        
        # Step 1: Analyze and group series
        series_groups = self.analyze_dicom_series()
        
        # Step 2: Prepare reconstruction inputs
        reconstruction_jobs = self.prepare_reconstruction_inputs(series_groups)
        
        if not reconstruction_jobs:
            logger.error("No reconstruction jobs prepared. Check series descriptions or file patterns.")
            return False
        
        logger.info(f"Prepared {len(reconstruction_jobs)} reconstruction jobs:")
        for job in reconstruction_jobs:
            logger.info(f"  - {job['description']} ({job['file_count']} files)")
        
        # Step 3: Run ALL reconstructions in parallel for 4x speedup
        # DICOM conversion only starts after all jobs are done
        results = []
        successful_jobs = []

        if len(reconstruction_jobs) > 1:
            logger.info(f"🚀 Running {len(reconstruction_jobs)} reconstructions in PARALLEL for maximum speed...")
            
            # Concurrent jobs: 1 per 8 physical CPUs, capped at 4.
            # On 16C prod: 2 concurrent × 4 threads = 8 threads peak, 8 cores free for MONAI.
            # On larger servers this auto-scales without any code changes.
            _cpu_count = os.cpu_count() or 4
            _max_concurrent = max(1, min(len(reconstruction_jobs), _cpu_count // 8, 4))
            logger.info(f"Running {_max_concurrent} concurrent reconstruction jobs ({_cpu_count} CPUs available)")
            with ProcessPoolExecutor(max_workers=_max_concurrent) as executor:
                # Submit all jobs
                future_to_job = {executor.submit(self.run_svrtk_reconstruction, job): job 
                                for job in reconstruction_jobs}
                
                # Collect results as they complete
                for future in as_completed(future_to_job):
                    job = future_to_job[future]
                    try:
                        success = future.result()
                        results.append((job['category'], success))
                        if success:
                            successful_jobs.append(job)
                            logger.info(f"✅ {job['description']} completed successfully in parallel")
                        else:
                            logger.error(f"❌ {job['description']} failed in parallel execution")
                    except Exception as exc:
                        logger.error(f"❌ {job['description']} generated exception: {exc}")
                        results.append((job['category'], False))
        else:
            # Single job - run sequentially
            logger.info("Running single reconstruction job...")
            for job in reconstruction_jobs:
                success = self.run_svrtk_reconstruction(job)
                results.append((job['category'], success))
                if success:
                    successful_jobs.append(job)

        # Log reconstruction summary before starting conversion
        logger.info("")
        logger.info("=" * 80)
        logger.info("RECONSTRUCTION SUMMARY")
        logger.info("=" * 80)
        for category, success in results:
            status = "✅ SUCCESS" if success else "❌ FAILED"
            logger.info(f"  {category}: {status}")
        logger.info(f"  Total: {len(successful_jobs)}/{len(reconstruction_jobs)} succeeded")
        logger.info("=" * 80)

        # Step 4: Convert ALL successful reconstructions to DICOM (only now, after all are done)
        dicom_success = True
        if successful_jobs:
            original_dicom_files = list(self.input_folder.glob('**/*.dcm')) + list(self.input_folder.glob('**/*.DCM'))
            
            if original_dicom_files:
                dicom_conversions = self.convert_reconstruction_outputs_to_dicom(
                    successful_jobs,
                    original_dicom_files
                )
                
                # Check if any DICOM conversions failed
                failed_conversions = [conv for conv in dicom_conversions if not conv.get('success', True)]
                successful_conversions = [conv for conv in dicom_conversions if conv.get('success', True)]
                
                if successful_conversions:
                    logger.info(f"✅ DICOM conversion completed ({len(successful_conversions)}/{len(dicom_conversions)} successful) - copying files for Mercure dispatch...")
                    self.copy_reconstructed_dicom_files()
                else:
                    logger.error("❌ All DICOM conversions failed - no reconstruction outputs found")
                    dicom_success = False
                    
                if failed_conversions:
                    logger.warning(f"⚠️ {len(failed_conversions)} DICOM conversions failed - some reconstructions missing expected outputs")
                    dicom_success = False
            else:
                logger.warning("No original DICOM files found for metadata reference - skipping DICOM conversion")
                dicom_success = False
        else:
            logger.error("❌ No successful reconstructions - skipping DICOM conversion")
            dicom_success = False

        # Step 4.5: Segmentation — runs after ALL reconstructions and DICOM conversions are done.
        # Runs on every successful reconstruction (all 4 categories independently).
        # Failures are non-fatal: reconstruction results are already in the output regardless.
        if successful_jobs:
            logger.info(
                f"Running segmentation on all {len(successful_jobs)} successful reconstruction(s): "
                + ", ".join(j['category'] for j in successful_jobs)
            )
            all_seg_results = []
            for job in successful_jobs:
                try:
                    seg_results_for_job = self.run_segmentation(job)
                    all_seg_results.extend(seg_results_for_job)
                except Exception as seg_exc:
                    logger.error(
                        f"⚠️  Segmentation error for {job['category']} (non-fatal): {seg_exc}"
                    )

            if all_seg_results and original_dicom_files:
                try:
                    seg_dicom_results = self.convert_segmentations_to_dicom(
                        all_seg_results, successful_jobs, original_dicom_files
                    )
                    # Push segmentation DICOMs to Orthanc directly — not dispatched to PACS
                    self.push_segmentations_to_orthanc(seg_dicom_results)
                except Exception as conv_exc:
                    logger.error(f"⚠️  Segmentation DICOM conversion error (non-fatal): {conv_exc}")
            elif not all_seg_results:
                logger.info("No segmentation outputs produced — skipping segmentation DICOM conversion")

        # Step 5: Generate summary report
        self.generate_summary_report(results)
        
        # Step 6: Aggressive cleanup of temp files and SVRTK directories
        logger.info("Cleaning up temporary files...")
        try:
            # Clean our temp folder
            if self.temp_folder.exists():
                shutil.rmtree(self.temp_folder, ignore_errors=True)
                logger.info(f"Removed temp folder: {self.temp_folder}")
                
            # Clean up SVRTK temp directories again (in case any were created during processing)
            self.cleanup_temp_directories()
            
            # Final disk space check
            total, used, free = shutil.disk_usage(self.output_folder)
            free_gb = free / (1024**3)
            logger.info(f"Final disk space: {free_gb:.1f} GB available")
            
        except Exception as e:
            logger.warning(f"Error during cleanup: {e}")
        
        all_reconstructions_success = all(success for _, success in results)
        final_success = all_reconstructions_success and dicom_success
        
        if final_success:
            logger.info("🎉 All reconstructions and DICOM conversions completed successfully!")
        elif all_reconstructions_success:
            logger.warning("⚠️ Reconstructions succeeded but DICOM conversion failed. Results available as NIfTI only.")
        else:
            logger.error("❌ Some reconstructions failed. Check individual logs for details.")
        
        return final_success
    
    def generate_summary_report(self, results):
        """Generate a summary report of all reconstructions"""
        report_path = self.output_folder / "reconstruction_summary.json"
        
        summary = {
            'timestamp': datetime.now().isoformat(),
            'input_folder': str(self.input_folder),
            'output_folder': str(self.output_folder),
            'reconstructions': []
        }
        
        for category, success in results:
            summary['reconstructions'].append({
                'category': category,
                'success': success,
                'output_directory': self.categories[category]['output_dir']
            })
        
        with open(report_path, 'w') as f:
            json.dump(summary, f, indent=2)
        
        logger.info(f"Summary report saved to: {report_path}")

def main():
    # Support both CLI arguments and Mercure environment variables
    if len(sys.argv) == 3:
        input_folder = sys.argv[1]
        output_folder = sys.argv[2]
    elif os.environ.get('MERCURE_IN_DIR') and os.environ.get('MERCURE_OUT_DIR'):
        input_folder = os.environ['MERCURE_IN_DIR']
        output_folder = os.environ['MERCURE_OUT_DIR']
        print(f"Using Mercure environment variables: in={input_folder}, out={output_folder}")
    else:
        print("Usage: python3 intelligent_svrtk_processor.py <input_folder> <output_folder>")
        print("  Or set MERCURE_IN_DIR and MERCURE_OUT_DIR environment variables")
        sys.exit(1)
    
    if not os.path.exists(input_folder):
        print(f"Error: Input folder {input_folder} does not exist")
        sys.exit(1)
    
    processor = IntelligentSVRTKProcessor(input_folder, output_folder)
    success = processor.process_study()
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()