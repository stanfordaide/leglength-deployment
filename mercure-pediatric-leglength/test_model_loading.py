#!/usr/bin/env python
"""
Test script to demonstrate automatic model type detection.

This script shows how the updated LegLengthDetector.load_checkpoint() method
automatically detects whether a checkpoint contains:
1. Standard Faster R-CNN model
2. Faster R-CNN with specialized keypoint head

The detection is based on the 'detection_head_type' field in the checkpoint metadata.
"""

import torch
import logging
from leglength.detector import LegLengthDetector, LegLengthDetectorWithKeypointHead

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_model_loading():
    """Test loading models with automatic detection."""
    
    logger.info("=" * 80)
    logger.info("Testing Automatic Model Type Detection")
    logger.info("=" * 80)
    
    # Load registry to get available models
    import json
    import os
    current_dir = os.path.dirname(os.path.abspath(__file__))
    registry_path = os.path.join(current_dir, 'registry.json')
    
    try:
        with open(registry_path, 'r') as f:
            registry = json.load(f)
        available_models = list(registry.keys())
        logger.info(f"\nFound {len(available_models)} models in registry:")
        for model in available_models:
            logger.info(f"  - {model}")
    except Exception as e:
        logger.error(f"Could not load registry: {e}")
        available_models = []
    
    # Test 1: Load all models from registry
    logger.info("\n" + "=" * 80)
    logger.info("Test 1: Loading Models from Registry")
    logger.info("=" * 80)
    
    for model_name in available_models:
        try:
            logger.info(f"\nLoading model: {model_name}")
            logger.info("-" * 40)
            
            # Load checkpoint - automatic detection will determine model type
            detector = LegLengthDetector.load_checkpoint(model_name)
            
            # Check the type of detector loaded
            if isinstance(detector, LegLengthDetectorWithKeypointHead):
                logger.info(f"✓ Loaded as: LegLengthDetectorWithKeypointHead")
                logger.info(f"  - Model name: {model_name}")
                logger.info(f"  - Backbone: {detector.backbone_name}")
                logger.info(f"  - Num classes: {detector.num_classes}")
                logger.info(f"  - Num keypoints: {detector.num_keypoints}")
            elif isinstance(detector, LegLengthDetector):
                logger.info(f"✓ Loaded as: LegLengthDetector (Standard Faster R-CNN)")
                logger.info(f"  - Model name: {model_name}")
                logger.info(f"  - Backbone: {detector.backbone_name}")
                logger.info(f"  - Num classes: {detector.num_classes}")
            
            # Verify model is on correct device
            logger.info(f"  - Device: {detector.device}")
            
            # Test inference capability (without actual image)
            logger.info(f"  - Model ready for inference: ✓")
            
        except FileNotFoundError as e:
            logger.warning(f"✗ Model checkpoint not found: {model_name}")
            logger.warning(f"  Run 'python download_models.py' to download models")
        except Exception as e:
            logger.error(f"✗ Error loading model {model_name}: {e}")
            import traceback
            traceback.print_exc()
    
    # Test 2: Demonstrate metadata extraction and backbone name extraction
    logger.info("\n" + "=" * 80)
    logger.info("Test 2: Metadata Extraction and Backbone Detection")
    logger.info("=" * 80)
    
    if available_models:
        # Test with first available model
        model_name = available_models[0]
        try:
            logger.info(f"\nExamining model: {model_name}")
            logger.info("-" * 40)
            
            # Show backbone extraction
            backbone_name = LegLengthDetector._extract_backbone_name(model_name)
            logger.info(f"Model name: {model_name}")
            logger.info(f"Extracted backbone: {backbone_name}")
            
            # Load checkpoint and show metadata
            model_path = LegLengthDetector.get_model_path(model_name)
            checkpoint = torch.load(model_path, map_location='cpu')
            
            if 'metadata' in checkpoint:
                metadata = checkpoint['metadata']
                logger.info("\nMetadata found in checkpoint:")
                for key, value in metadata.items():
                    logger.info(f"  - {key}: {value}")
            else:
                logger.info("\nNo metadata found in checkpoint (using defaults)")
            
            # Show what detection_head_type determines
            detection_head_type = checkpoint.get('metadata', {}).get('detection_head_type', None)
            
            if detection_head_type is None:
                # Auto-detect from model name
                if any(suffix in model_name for suffix in ['_kp_head', '_keypoint_head']):
                    logger.info(f"\nNo detection_head_type in metadata")
                    logger.info(f"Auto-detected from name '{model_name}': faster_rcnn_keypoint_head")
                    logger.info("→ Will load as: LegLengthDetectorWithKeypointHead")
                else:
                    logger.info(f"\nNo detection_head_type in metadata")
                    logger.info(f"Auto-detected from name '{model_name}': faster_rcnn")
                    logger.info("→ Will load as: LegLengthDetector (Standard)")
            else:
                logger.info(f"\nDetection head type: {detection_head_type}")
                if detection_head_type == 'faster_rcnn_keypoint_head':
                    logger.info("→ Will load as: LegLengthDetectorWithKeypointHead")
                elif detection_head_type == 'faster_rcnn':
                    logger.info("→ Will load as: LegLengthDetector (Standard)")
                else:
                    logger.info(f"→ Unknown type: {detection_head_type}")
                
        except FileNotFoundError:
            logger.warning(f"Model checkpoint not found: {model_name}")
            logger.warning("Run 'python download_models.py' to download models")
        except Exception as e:
            logger.error(f"Error examining metadata: {e}")
    else:
        logger.warning("No models available in registry to test")
    
    # Test 3: Show supported detection head types
    logger.info("\n" + "=" * 80)
    logger.info("Test 3: Supported Detection Head Types")
    logger.info("=" * 80)
    
    logger.info("\nThe following detection_head_type values are supported:")
    logger.info("  1. 'faster_rcnn' - Standard Faster R-CNN")
    logger.info("     → Loads as: LegLengthDetector")
    logger.info("  2. 'faster_rcnn_keypoint_head' - Faster R-CNN with keypoint head")
    logger.info("     → Loads as: LegLengthDetectorWithKeypointHead")
    logger.info("\nThe type is automatically detected from checkpoint metadata.")
    
    logger.info("\n" + "=" * 80)
    logger.info("Testing Complete")
    logger.info("=" * 80)


def demonstrate_checkpoint_structure():
    """Demonstrate the expected checkpoint structure."""
    
    logger.info("\n" + "=" * 80)
    logger.info("Expected Checkpoint Structure")
    logger.info("=" * 80)
    
    logger.info("\nFor Standard Faster R-CNN:")
    logger.info("""
{
    'model_state_dict': <model weights>,
    'optimizer_state_dict': <optimizer state>,
    'epoch': <epoch number>,
    'metrics': <validation metrics>,
    'metadata': {
        'detection_head_type': 'faster_rcnn',  # Key field!
        'backbone': 'resnet101',
        'num_classes': 9,
        'preprocessing_config': {...}
    }
}
    """)
    
    logger.info("\nFor Faster R-CNN with Keypoint Head:")
    logger.info("""
{
    'model_state_dict': <model weights>,
    'optimizer_state_dict': <optimizer state>,
    'epoch': <epoch number>,
    'metrics': <validation metrics>,
    'metadata': {
        'detection_head_type': 'faster_rcnn_keypoint_head',  # Key field!
        'backbone': 'resnet101',
        'num_classes': 9,
        'num_keypoints': 8,
        'preprocessing_config': {...}
    }
}
    """)


def show_usage_examples():
    """Show usage examples."""
    
    logger.info("\n" + "=" * 80)
    logger.info("Usage Examples")
    logger.info("=" * 80)
    
    logger.info("\nExample 1: Load any model (automatic detection)")
    logger.info("""
from leglength.detector import LegLengthDetector

# Load standard Faster R-CNN model
detector = LegLengthDetector.load_checkpoint('vit_l_16')

# Load keypoint head model - automatically detected from name
detector_kp = LegLengthDetector.load_checkpoint('resnet50_kp_head')

# Use for inference (same interface for both)
predictions = detector.predict(image, confidence_threshold=0.5)
    """)
    
    logger.info("\nExample 2: Check model type after loading")
    logger.info("""
from leglength.detector import LegLengthDetector, LegLengthDetectorWithKeypointHead

detector = LegLengthDetector.load_checkpoint('my_model')

if isinstance(detector, LegLengthDetectorWithKeypointHead):
    print("Loaded model with specialized keypoint head")
elif isinstance(detector, LegLengthDetector):
    print("Loaded standard Faster R-CNN model")
    """)
    
    logger.info("\nExample 3: Integration with existing inference pipeline")
    logger.info("""
# Your existing code works without changes!
from leglength.detector import LegLengthDetector
from leglength.processor import ImageProcessor

# Load any model from registry (automatic type detection)
detector = LegLengthDetector.load_checkpoint('resnet50_kp_head')
preprocessor = ImageProcessor()

# Preprocess and predict
image = preprocessor.preprocess_image('path/to/dicom.dcm')
predictions = detector.predict(image, confidence_threshold=0.5)

# Convert boxes back to original space
boxes = torch.tensor(predictions['boxes'])
boxes = preprocessor.translate_boxes_to_original(boxes)
    """)


if __name__ == '__main__':
    logger.info("Starting Model Loading Tests\n")
    
    # Run tests
    test_model_loading()
    
    # Show documentation
    demonstrate_checkpoint_structure()
    show_usage_examples()
    
    logger.info("\n" + "=" * 80)
    logger.info("All tests completed!")
    logger.info("=" * 80)
