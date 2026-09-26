"""Grad-CAM for ResNet9 (target layer: the last residual block)."""
import io

import numpy as np
import torch.nn.functional as F
from PIL import Image


def gradcam(model, input_tensor, class_idx, target_layer=None):
    """Return a [H, W] numpy heatmap in [0, 1] at the input resolution."""
    target_layer = target_layer or model.res2
    activations, gradients = {}, {}

    def fwd_hook(_, __, out):
        activations["value"] = out

    def bwd_hook(_, __, grad_out):
        gradients["value"] = grad_out[0]

    h1 = target_layer.register_forward_hook(fwd_hook)
    h2 = target_layer.register_full_backward_hook(bwd_hook)
    try:
        model.zero_grad()
        x = input_tensor.clone().requires_grad_(True)
        logits = model(x)
        logits[0, class_idx].backward()
        acts = activations["value"].detach()[0]
        grads = gradients["value"].detach()[0]
    finally:
        h1.remove()
        h2.remove()

    weights = grads.mean(dim=(1, 2))
    cam = F.relu((weights[:, None, None] * acts).sum(0))
    cam = F.interpolate(cam[None, None], size=input_tensor.shape[-2:], mode="bilinear", align_corners=False)[0, 0]
    cam = cam - cam.min()
    if cam.max() > 0:
        cam = cam / cam.max()
    return cam.numpy()


def severity_from_cam(cam, threshold=0.5):
    """Share of the image whose activation is above `threshold` (proxy for affected leaf area)."""
    return float((cam >= threshold).mean())


def _colormap(cam):
    """Simple blue->green->yellow->red ramp without matplotlib."""
    r = np.clip(1.5 - np.abs(4 * cam - 3), 0, 1)
    g = np.clip(1.5 - np.abs(4 * cam - 2), 0, 1)
    b = np.clip(1.5 - np.abs(4 * cam - 1), 0, 1)
    return (np.stack([r, g, b], axis=-1) * 255).astype(np.uint8)


def overlay_png(image, cam, alpha=0.45):
    """Blend the heatmap over the original image; return PNG bytes."""
    base = image.convert("RGB").resize((cam.shape[1], cam.shape[0]))
    heat = Image.fromarray(_colormap(cam))
    blended = Image.blend(base, heat, alpha)
    buf = io.BytesIO()
    blended.save(buf, format="PNG")
    return buf.getvalue()
