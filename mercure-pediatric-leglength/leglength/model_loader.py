"""Unified model loader supporting all detection architectures.

Matches the training code architecture exactly.
"""

import torch
import logging
from pathlib import Path
from typing import Optional, Any

logger = logging.getLogger(__name__)


class DummyDataset:
    """Dummy dataset for model initialization (matches training code interface)."""
    def __init__(self, num_points=8):
        self.num_points = num_points
        self.num_classes = num_points + 1  # +1 for background


def load_model_from_checkpoint(
    model_name: str,
    device: Optional[torch.device] = None
) -> Any:
    """Load model from checkpoint with automatic architecture detection.
    
    Supports all detection head types from training code:
    - 'faster_rcnn': Standard Faster R-CNN
    - 'faster_rcnn_keypoint_head': Faster R-CNN with specialized keypoint head
    - 'faster_rcnn_heatmap': Faster R-CNN with heatmap head (fallback to faster_rcnn)
    - 'heatmap_offset': HeatmapOffset detector (fallback to faster_rcnn)
    - 'hierarchical_heatmap': Hierarchical heatmap detector (fallback to faster_rcnn)
    
    Args:
        model_name: Name of model in registry (e.g., 'resnet50_kp_head', 'vit_l_16')
        device: Device to load model on
        
    Returns:
        Model instance with loaded weights
    """
    from .detector import LegLengthDetector
    
    if device is None:
        device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    
    # Get model path
    model_path = LegLengthDetector.get_model_path(model_name)
    
    if not Path(model_path).exists():
        raise FileNotFoundError(f"Model checkpoint not found: {model_path}")
    
    # Load checkpoint
    checkpoint = torch.load(model_path, map_location=device, weights_only=False)
    
    # Extract metadata
    metadata = checkpoint.get('metadata', {})
    detection_head_type = metadata.get('detection_head_type', None)
    
    # Extract backbone name
    if 'backbone' in metadata:
        backbone_name = metadata['backbone']
    else:
        backbone_name = LegLengthDetector._extract_backbone_name(model_name)
    
    # Auto-detect model type if not specified in metadata
    if detection_head_type is None:
        if any(suffix in model_name for suffix in ['_kp_head', '_keypoint_head', '_kphead']):
            detection_head_type = 'faster_rcnn_keypoint_head'
            logger.info(f"Auto-detected keypoint head model from name: {model_name}")
        else:
            detection_head_type = 'faster_rcnn'
            logger.info(f"Auto-detected standard Faster R-CNN from name: {model_name}")
    
    logger.info(f"Loading model '{model_name}' - Type: {detection_head_type}, Backbone: {backbone_name}")
    
    # Create dummy dataset (8 landmarks for leg length)
    dataset = DummyDataset(num_points=8)
    
    # Load model using training code's approach
    if detection_head_type == 'faster_rcnn':
        from .training_models import KeypointDetector
        model = KeypointDetector(dataset, backbone=backbone_name)
        model.model.load_state_dict(checkpoint['model_state_dict'])
        model.model.to(device)
    
    elif detection_head_type == 'faster_rcnn_keypoint_head':
        from .training_models import KeypointDetectorWithSpecializedHead
        model = KeypointDetectorWithSpecializedHead(dataset, backbone=backbone_name)
        model.model.load_state_dict(checkpoint['model_state_dict'])
        model.model.to(device)
    
    elif detection_head_type in ['faster_rcnn_heatmap', 'heatmap_offset', 'hierarchical_heatmap']:
        # These types are not fully implemented for inference yet
        # Fallback to standard FasterRCNN
        logger.warning(f"{detection_head_type} not fully supported in inference module, using standard faster_rcnn")
        from .training_models import KeypointDetector
        model = KeypointDetector(dataset, backbone=backbone_name)
        model.model.load_state_dict(checkpoint['model_state_dict'])
        model.model.to(device)
    
    else:
        raise ValueError(
            f"Unknown detection_head_type: {detection_head_type}. "
            f"Supported: 'faster_rcnn', 'faster_rcnn_keypoint_head', 'faster_rcnn_heatmap', "
            f"'heatmap_offset', 'hierarchical_heatmap'"
        )
    
    logger.info(f"Successfully loaded model from {model_path}")
    return model
