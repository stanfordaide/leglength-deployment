"""Model classes copied from training code for inference compatibility.

These classes are minimal versions that support loading trained checkpoints
and running inference.
"""

import torch
import torchvision
import torch.nn as nn
import numpy as np
from torchvision.models.detection import FasterRCNN
from torchvision.models.detection.faster_rcnn import FastRCNNPredictor
from torchvision.models.detection.rpn import AnchorGenerator
from torchvision.ops import MultiScaleRoIAlign
from typing import Optional, Dict
import logging

logger = logging.getLogger(__name__)


class KeypointDetector:
    """Standard Faster R-CNN keypoint detector (from training code)."""
    
    def __init__(self, dataset, backbone: str = 'resnet50', weights=None):
        """Initialize the model.
        
        Args:
            dataset: Dataset object with num_classes and num_points attributes
            backbone: Backbone architecture name
            weights: Optional weights to load
        """
        self.num_classes = dataset.num_classes
        self.num_keypoints = dataset.num_points
        self.backbone = backbone
        self.model = self._create_model(self.num_classes, backbone, weights)
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.model.to(self.device)
    
    def _create_model(self, num_classes: int, backbone: str, weights) -> FasterRCNN:
        """Create Faster R-CNN model with specified backbone."""
        
        def _modify_classifier(model, num_classes):
            """Modify the model's box predictor to match our number of classes."""
            in_features = model.roi_heads.box_predictor.cls_score.in_features
            model.roi_heads.box_predictor = FastRCNNPredictor(in_features, num_classes)
            return model
        
        # Pre-built models from torchvision
        if backbone == "resnet50":
            # Use weights=None since we load our own trained checkpoint
            # This avoids downloading COCO weights at runtime
            model = torchvision.models.detection.fasterrcnn_resnet50_fpn(
                weights=None,
                weights_backbone=None,
                trainable_backbone_layers=5
            )
            model = _modify_classifier(model, num_classes)
            
        elif backbone in ["convnext_tiny", "convnext_small", "convnext_base", "convnext_large"]:
            # ConvNeXt backbones - use weights=None since we load our own checkpoint
            backbone_fn = getattr(torchvision.models, backbone)
            backbone_model = backbone_fn(weights=None)
            
            # Determine out_channels based on model variant
            if backbone == "convnext_tiny":
                out_channels = 768
            elif backbone == "convnext_small":
                out_channels = 768
            elif backbone == "convnext_base":
                out_channels = 1024
            elif backbone == "convnext_large":
                out_channels = 1536
            else:
                out_channels = 768  # default
            
            class ConvNeXtBackbone(nn.Module):
                def __init__(self, convnext_model, out_channels):
                    super().__init__()
                    self.features = convnext_model.features
                    self.avgpool = convnext_model.avgpool
                    self.out_channels = out_channels
                
                def forward(self, x):
                    x = self.features(x)
                    return {'0': x}
            
            bb = ConvNeXtBackbone(backbone_model, out_channels)
            
            anchor_generator = AnchorGenerator(
                sizes=((32, 64, 128, 256, 512),),
                aspect_ratios=((0.5, 1.0, 2.0),)
            )
            
            roi_pooler = MultiScaleRoIAlign(
                featmap_names=['0'],
                output_size=7,
                sampling_ratio=2
            )
            
            model = FasterRCNN(
                backbone=bb,
                num_classes=num_classes,
                rpn_anchor_generator=anchor_generator,
                box_roi_pool=roi_pooler
            )
        
        elif backbone in ["vit_b_16", "vit_b_32", "vit_l_16", "vit_l_32"]:
            # Vision Transformer backbones - use weights=None since we load our own checkpoint
            backbone_fn = getattr(torchvision.models, backbone)
            backbone_model = backbone_fn(weights=None)
            
            patch_size = int(backbone.split('_')[-1])
            out_channels = 768 if 'b_' in backbone else 1024
            
            class ViTBackbone(nn.Module):
                def __init__(self, vit_model, out_channels, patch_size):
                    super().__init__()
                    self.conv_proj = vit_model.conv_proj
                    self.encoder = vit_model.encoder
                    self.out_channels = out_channels
                    self.patch_size = patch_size
                    
                    # Store original position embeddings
                    self.original_pos_embed = vit_model.encoder.pos_embedding
                    self.original_grid_size = int((self.original_pos_embed.shape[1] - 1) ** 0.5)
                
                def interpolate_pos_encoding(self, pos_embed, H, W):
                    npatch = H * W
                    N = pos_embed.shape[1] - 1
                    
                    if npatch == N:
                        return pos_embed
                    
                    class_pos_embed = pos_embed[:, :1]
                    patch_pos_embed = pos_embed[:, 1:]
                    
                    patch_pos_embed = patch_pos_embed.reshape(1, self.original_grid_size, self.original_grid_size, -1)
                    patch_pos_embed = patch_pos_embed.permute(0, 3, 1, 2)
                    
                    patch_pos_embed = torch.nn.functional.interpolate(
                        patch_pos_embed, size=(H, W), mode='bicubic', align_corners=False
                    )
                    
                    patch_pos_embed = patch_pos_embed.permute(0, 2, 3, 1).reshape(1, H * W, -1)
                    
                    return torch.cat([class_pos_embed, patch_pos_embed], dim=1)
                
                def forward(self, x):
                    x = self.conv_proj(x)
                    B, C, H, W = x.shape
                    
                    x = x.flatten(2).transpose(1, 2)
                    
                    class_token = self.original_pos_embed[:, :1].expand(B, -1, -1)
                    x = torch.cat([class_token, x], dim=1)
                    
                    pos_embed = self.interpolate_pos_encoding(self.original_pos_embed, H, W)
                    
                    x = x + pos_embed
                    x = self.encoder.dropout(x)
                    
                    for layer in self.encoder.layers:
                        x = layer(x)
                    
                    x = x[:, 1:]
                    x = x.transpose(1, 2).view(B, C, H, W)
                    
                    return {'0': x}
            
            bb = ViTBackbone(backbone_model, out_channels, patch_size)
            
            anchor_generator = AnchorGenerator(
                sizes=((32, 64, 128, 256, 512),),
                aspect_ratios=((0.5, 1.0, 2.0),)
            )
            
            roi_pooler = MultiScaleRoIAlign(
                featmap_names=['0'],
                output_size=7,
                sampling_ratio=2
            )
            
            model = FasterRCNN(
                backbone=bb,
                num_classes=num_classes,
                rpn_anchor_generator=anchor_generator,
                box_roi_pool=roi_pooler
            )
        
        else:
            raise ValueError(f"Unsupported backbone: {backbone}")
        
        return model
    
    @torch.no_grad()
    def predict(self, image: torch.Tensor, confidence_threshold: float = 0.0, best_per_class: bool = True) -> Dict:
        """Run inference on a single image.
        
        Args:
            image: Preprocessed image tensor [3, H, W]
            confidence_threshold: Minimum confidence score for predictions
            best_per_class: If True, return only the best prediction per class
            
        Returns:
            Dictionary with 'boxes', 'scores', 'labels' arrays
        """
        self.model.eval()
        image = image.to(self.device)
        
        # Get predictions
        predictions = self.model([image])[0]
        
        # Filter predictions by confidence
        keep = predictions['scores'] > confidence_threshold
        filtered_preds = {
            'boxes': predictions['boxes'][keep].cpu().numpy(),
            'scores': predictions['scores'][keep].cpu().numpy(),
            'labels': predictions['labels'][keep].cpu().numpy()
        }
        
        if best_per_class:
            unique_labels = np.unique(filtered_preds['labels'])
            best_indices = []
            
            for label in unique_labels:
                class_mask = filtered_preds['labels'] == label
                if np.any(class_mask):
                    class_scores = filtered_preds['scores'][class_mask]
                    best_idx = np.argmax(class_scores)
                    original_indices = np.where(class_mask)[0]
                    best_indices.append(original_indices[best_idx])
            
            if best_indices:
                filtered_preds = {
                    'boxes': filtered_preds['boxes'][best_indices],
                    'scores': filtered_preds['scores'][best_indices],
                    'labels': filtered_preds['labels'][best_indices]
                }
            else:
                filtered_preds = {
                    'boxes': np.array([]).reshape(0, 4),
                    'scores': np.array([]),
                    'labels': np.array([])
                }
        
        return filtered_preds


class FasterRCNNWithKeypointHead(nn.Module):
    """FasterRCNN with specialized keypoint refinement head (from training code)."""
    
    def __init__(self, fasterrcnn_model, num_keypoints: int):
        super().__init__()
        self.fasterrcnn = fasterrcnn_model
        self.num_keypoints = num_keypoints
        
        # Specialized keypoint refinement head
        self.keypoint_head = nn.Sequential(
            nn.Linear(256 * 7 * 7, 1024),
            nn.ReLU(inplace=True),
            nn.Dropout(0.5),
            nn.Linear(1024, 512),
            nn.ReLU(inplace=True),
            nn.Dropout(0.5),
            nn.Linear(512, 2),  # Predict x, y offset
        )
        
        self.roi_pool = MultiScaleRoIAlign(
            featmap_names=['0', '1', '2', '3'],
            output_size=7,
            sampling_ratio=2
        )
    
    def forward(self, images, targets=None):
        """Forward pass - at inference, returns standard FasterRCNN predictions."""
        if self.training and targets is not None:
            # Training mode (not used for inference)
            raise NotImplementedError("Training mode not supported in inference module")
        else:
            # Inference: Just use FasterRCNN predictions
            predictions = self.fasterrcnn(images)
            
            # Add dummy keypoint offsets (not used at inference)
            for pred in predictions:
                pred['keypoint_offsets'] = torch.zeros(
                    len(pred['boxes']), 2, device=pred['boxes'].device
                )
            
            return predictions


class KeypointDetectorWithSpecializedHead:
    """FasterRCNN with specialized keypoint head (from training code)."""
    
    def __init__(self, dataset, backbone: str = 'resnet50', weights=None):
        """Initialize FasterRCNN with specialized keypoint head.
        
        Args:
            dataset: Dataset object with num_classes and num_points attributes
            backbone: Backbone architecture name
            weights: Optional weights to load
        """
        self.num_keypoints = dataset.num_points
        self.num_classes = dataset.num_points + 1  # +1 for background
        self.backbone_name = backbone
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        
        # Build model with specialized keypoint head
        self.model = self._create_model(backbone, self.num_classes, self.num_keypoints)
        self.model.to(self.device)
    
    def _create_model(self, backbone: str, num_classes: int, num_keypoints: int):
        """Create FasterRCNN model with specialized keypoint head."""
        
        # First create base FasterRCNN using KeypointDetector
        # Create a dummy dataset object
        class DummyDataset:
            def __init__(self, num_classes, num_points):
                self.num_classes = num_classes
                self.num_points = num_points
        
        dummy_dataset = DummyDataset(num_classes, num_keypoints)
        base_detector = KeypointDetector(dummy_dataset, backbone=backbone)
        base_model = base_detector.model
        
        # Wrap with specialized keypoint head
        model = FasterRCNNWithKeypointHead(base_model, num_keypoints)
        
        return model
    
    @torch.no_grad()
    def predict(self, image: torch.Tensor, confidence_threshold: float = 0.0, best_per_class: bool = True) -> Dict:
        """Run inference on a single image.
        
        Args:
            image: Preprocessed image tensor [3, H, W]
            confidence_threshold: Minimum confidence score for predictions
            best_per_class: If True, return only the best prediction per class
            
        Returns:
            Dictionary with 'boxes', 'scores', 'labels' arrays
        """
        self.model.eval()
        image = image.to(self.device)
        
        # Get predictions
        predictions = self.model([image])[0]
        
        # Filter predictions by confidence
        keep = predictions['scores'] > confidence_threshold
        filtered_preds = {
            'boxes': predictions['boxes'][keep].cpu().numpy(),
            'scores': predictions['scores'][keep].cpu().numpy(),
            'labels': predictions['labels'][keep].cpu().numpy()
        }
        
        if best_per_class:
            unique_labels = np.unique(filtered_preds['labels'])
            best_indices = []
            
            for label in unique_labels:
                class_mask = filtered_preds['labels'] == label
                if np.any(class_mask):
                    class_scores = filtered_preds['scores'][class_mask]
                    best_idx = np.argmax(class_scores)
                    original_indices = np.where(class_mask)[0]
                    best_indices.append(original_indices[best_idx])
            
            if best_indices:
                filtered_preds = {
                    'boxes': filtered_preds['boxes'][best_indices],
                    'scores': filtered_preds['scores'][best_indices],
                    'labels': filtered_preds['labels'][best_indices]
                }
            else:
                filtered_preds = {
                    'boxes': np.array([]).reshape(0, 4),
                    'scores': np.array([]),
                    'labels': np.array([])
                }
        
        return filtered_preds