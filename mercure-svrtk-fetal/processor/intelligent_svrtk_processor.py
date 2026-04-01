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
        self.categories = {
            'ssfsex_brain': {
                'patterns': [r'.*ssfsex.*brain.*', r'.*ssfse.*brain.*'],
                'script': '/home/auto-proc-svrtk/scripts/auto-brain-reconstruction.sh',
                'output_dir': 'ssfsex_brain_reconstruction',
                'description': 'SSFSEx Brain'
            },
            'fiesta_brain': {
                'patterns': [r'.*fiesta.*brain.*'],
                'script': '/home/auto-proc-svrtk/scripts/auto-brain-reconstruction.sh',
                'output_dir': 'fiesta_brain_reconstruction',
                'description': 'FIESTA Brain'
            },
            'ssfsex_body': {
                'patterns': [r'.*ssfsex.*body.*', r'.*ssfse.*body.*'],
                'script': '/home/auto-proc-svrtk/scripts/auto-body-reconstruction.sh',
                'output_dir': 'ssfsex_body_reconstruction',
                'description': 'SSFSEx Body'
            },
            'fiesta_body': {
                'patterns': [r'.*fiesta.*body.*'],
                'script': '/home/auto-proc-svrtk/scripts/auto-body-reconstruction.sh',
                'output_dir': 'fiesta_body_reconstruction',
                'description': 'FIESTA Body'
            }
        }
        
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
        
    def check_disk_space(self, required_gb=50):
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
            
    def analyze_dicom_series(self):
        """Analyze DICOM files and group by series description patterns"""
        logger.info("Analyzing input files...")
        
        # Find all DICOM files
        dicom_files = list(self.input_folder.glob('**/*.dcm')) + list(self.input_folder.glob('**/*.DCM'))
        
        if dicom_files:
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
            '-z', 'n',
            '-f', '%d_%s_%t_%r',
            '-o', str(output_dir),
            '-v', '1',
            '-b', 'n',
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
            '-z', 'y',
            '-b', 'n',
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
            
            reconstruction_jobs.append({
                'category': category,
                'description': self.categories[category]['description'],
                'input_dir': input_dir,
                'output_dir': output_dir,
                'script': self.categories[category]['script'],
                'file_count': len(files)
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
        
        # Create patched script command that overrides default_run_dir
        patched_script = f"sed 's|default_run_dir=/home/tmp_proc|default_run_dir={unique_work_dir}|g' {script}"
        
        cmd = [
            'bash', '-c', 
            f"{patched_script} | bash -s -- {input_dir} {output_dir} 1 3.0 0.8 1"
        ]
        
        logger.info(f"Command: {' '.join(cmd)}")
        logger.info("")
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
            
            # Always try to cleanup unique_work_dir regardless of success/failure
            for temp_dir in temp_dirs_to_cleanup:
                try:
                    if os.path.exists(temp_dir):
                        shutil.rmtree(temp_dir, ignore_errors=True)
                        logger.debug(f"Cleaned up job temp dir: {temp_dir}")
                except Exception as cleanup_e:
                    logger.warning(f"Could not clean job temp dir {temp_dir}: {cleanup_e}")
            
            if result.stdout:
                logger.info("STDOUT:")
                for line in result.stdout.split('\n'):
                    if line.strip():
                        logger.info(f"  {line}")
            
            if result.stderr:
                logger.info("STDERR:")
                for line in result.stderr.split('\n'):
                    if line.strip():
                        logger.warning(f"  {line}")
            
            if result.returncode == 0:
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
                logger.error(f"❌ {description} reconstruction FAILED (exit code {result.returncode})")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error(f"❌ {description} reconstruction TIMED OUT after 1 hour")
            # Cleanup on timeout
            for temp_dir in temp_dirs_to_cleanup:
                try:
                    if os.path.exists(temp_dir):
                        shutil.rmtree(temp_dir, ignore_errors=True)
                        logger.info(f"Cleaned up temp dir after timeout: {temp_dir}")
                except:
                    pass
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
    
    def convert_nifti_to_dicom(self, nifti_file, output_dir, ref_dicom_file=None, series_description=None):
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

            # Post-process to set series description
            dicom_files = list(output_dir.glob('*.dcm'))
            if dicom_files and series_description and PYDICOM_AVAILABLE:
                logger.info(f"Post-processing {len(dicom_files)} DICOM files to set series description")
                for dcm_file in dicom_files:
                    try:
                        ds = pydicom.dcmread(str(dcm_file))
                        ds.SeriesDescription = series_description
                        ds.save_as(str(dcm_file))
                    except Exception as fix_e:
                        logger.warning(f"Could not fix series description in {dcm_file.name}: {fix_e}")

            dicom_files = list(output_dir.glob('*.dcm'))
            if dicom_files:
                logger.info(f"✅ Successfully converted to {len(dicom_files)} DICOM files")
                if series_description and PYDICOM_AVAILABLE:
                    try:
                        test_ds = pydicom.dcmread(str(dicom_files[0]))
                        actual_desc = getattr(test_ds, 'SeriesDescription', '')
                        logger.info(f"Series description verified: '{actual_desc}'")
                    except:
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

            logger.info(f"Converting {category}: {expected_output}")
            dicom_output_dir = output_dir / 'dicom_series'

            success = self.convert_nifti_to_dicom(
                expected_output,
                dicom_output_dir,
                ref_dicom,
                series_description
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
        if not self.check_disk_space(required_gb=50):
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
            
            # Use ProcessPoolExecutor for CPU-intensive SVRTK reconstructions
            with ProcessPoolExecutor(max_workers=min(len(reconstruction_jobs), 4)) as executor:
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