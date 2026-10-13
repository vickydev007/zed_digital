"""
Architecture Sanity Check: verifies forward pass, output shapes, parameter count.
"""
import sys
sys.path.insert(0, "d:/zed digital")

import torch
from openset_reid.models.backbones import OmniScaleReIDBackbone
from openset_reid.models.heads import DualGranularityReIDHead
from openset_reid.models.openset_model import create_openset_model
from openset_reid.models.loss import CombinedOpenSetLoss

print("=" * 60)
print("ARCHITECTURE SANITY CHECK")
print("=" * 60)

# ── 1. Backbone ─────────────────────────────────────────────
print("\n[1] OmniScaleReIDBackbone")
backbone = OmniScaleReIDBackbone(base_channels=64)
x = torch.randn(4, 3, 256, 128)
feat = backbone(x)
print(f"  Input:  {tuple(x.shape)}")
print(f"  Output: {tuple(feat.shape)}")
params = sum(p.numel() for p in backbone.parameters())
print(f"  Params: {params/1e6:.2f}M")
assert feat.shape == (4, 384, 16, 8), f"Shape mismatch: {feat.shape}"
print("  PASSED ✓")

# ── 2. Dual Granularity Head ─────────────────────────────────
print("\n[2] DualGranularityReIDHead")
head = DualGranularityReIDHead(in_channels=384, global_dim=256, part_dim=256, num_parts=5)
emb, aux = head(feat)
print(f"  Embedding shape: {tuple(emb.shape)}")
print(f"  Part weights:    {tuple(aux['part_weights'].shape)}")
assert emb.shape == (4, 512), f"Embedding shape mismatch: {emb.shape}"
print("  PASSED ✓")

# ── 3. Full Model (dual granularity) ──────────────────────────
print("\n[3] OpenSetReIDModel (dual_granularity=True)")
model = create_openset_model(dual_granularity=True, embedding_dim=512)
x2 = torch.randn(8, 3, 256, 128)
emb2, aux2 = model(x2)
print(f"  Embedding shape: {tuple(emb2.shape)}")
total = sum(p.numel() for p in model.parameters())
print(f"  Total Params:    {total/1e6:.2f}M")
assert emb2.shape == (8, 512)
# L2 norms should be 1.0
norms = emb2.norm(dim=1)
print(f"  L2 norms (min/max): {norms.min().item():.5f} / {norms.max().item():.5f}")
assert (norms - 1.0).abs().max().item() < 1e-4, "Embeddings not unit-normalized!"
print("  PASSED ✓")

# ── 4. Feature extraction (inference mode) ────────────────────
print("\n[4] extract_features() inference path")
feats = model.extract_features(x2)
print(f"  Shape: {tuple(feats.shape)}")
assert feats.shape == (8, 512)
print("  PASSED ✓")

# ── 5. Combined Loss ─────────────────────────────────────────
print("\n[5] CombinedOpenSetLoss (ArcFace + AdaptiveTriplet + PartOrtho)")
criterion = CombinedOpenSetLoss(in_features=512, num_classes=20)
labels = torch.arange(8) % 20
loss, loss_dict = criterion(emb2, labels, aux2)
print(f"  Total Loss:    {loss_dict['loss_total']:.4f}")
print(f"  ArcFace Loss:  {loss_dict['loss_arcface']:.4f}")
print(f"  Triplet Loss:  {loss_dict['loss_triplet']:.4f}")
print(f"  Ortho Loss:    {loss_dict['loss_ortho']:.4f}")
assert loss.item() > 0, "Loss should be positive"
print("  PASSED ✓")

# ── 6. Backward pass ─────────────────────────────────────────
print("\n[6] Backward pass gradient flow")
loss.backward()
grad_norms = [p.grad.norm().item() for p in model.parameters() if p.grad is not None]
print(f"  Layers with gradients: {len(grad_norms)}/{sum(1 for _ in model.parameters())}")
print(f"  Gradient norm (mean):  {sum(grad_norms)/len(grad_norms):.6f}")
assert len(grad_norms) > 0, "No gradients found!"
print("  PASSED ✓")

print("\n" + "=" * 60)
print("ALL SANITY CHECKS PASSED — System ready for training.")
print("=" * 60)
