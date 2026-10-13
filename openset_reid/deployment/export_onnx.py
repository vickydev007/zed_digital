"""
Production ONNX Export and Numerical Validation Engine.
Converts OpenSetReID PyTorch models into high-performance ONNX computational graphs
with dynamic batch dimension and verified numerical parity.
"""

import os
import torch
import numpy as np
import onnx
import onnxruntime as ort
from typing import Tuple, Dict

from openset_reid.models.openset_model import OpenSetReIDModel


class ONNXExporter:
    """
    Exports and validates PyTorch Re-ID models into ONNX.
    """
    @staticmethod
    def export(model: OpenSetReIDModel,
               output_path: str,
               input_shape: Tuple[int, int, int, int] = (1, 3, 256, 128),
               opset_version: int = 17) -> str:
        """
        Exports the model feature extractor to ONNX.
        """
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        model.eval()

        # Wrapper class to ensure clean single-output feature extraction in ONNX graph
        class ONNXWrapper(torch.nn.Module):
            def __init__(self, m):
                super().__init__()
                self.m = m

            def forward(self, x):
                return self.m.extract_features(x)

        wrapped = ONNXWrapper(model)
        dummy_input = torch.randn(*input_shape, dtype=torch.float32)

        # PyTorch forward for reference check
        with torch.no_grad():
            torch_output = wrapped(dummy_input).numpy()

        input_names = ["images"]
        output_names = ["embeddings"]
        dynamic_axes = {
            "images": {0: "batch_size"},
            "embeddings": {0: "batch_size"}
        }

        # Export to ONNX
        torch.onnx.export(
            wrapped,
            dummy_input,
            output_path,
            export_params=True,
            opset_version=opset_version,
            do_constant_folding=True,
            input_names=input_names,
            output_names=output_names,
            dynamic_axes=dynamic_axes
        )
        print(f"ONNX graph exported to {output_path}")

        # Check ONNX model validity
        onnx_model = onnx.load(output_path)
        onnx.checker.check_model(onnx_model)
        print("ONNX model passed integrity check.")

        # Numerical Parity Validation via ONNX Runtime
        session = ort.InferenceSession(output_path, providers=["CPUExecutionProvider"])
        ort_inputs = {session.get_inputs()[0].name: dummy_input.numpy()}
        ort_outputs = session.run(None, ort_inputs)[0]

        max_abs_diff = np.max(np.abs(torch_output - ort_outputs))
        print(f"PyTorch vs ONNX Max Absolute Difference: {max_abs_diff:.6e}")
        assert max_abs_diff < 1e-4, f"Numerical parity error too large: {max_abs_diff}"
        print("Verification SUCCESS: PyTorch and ONNX Runtime outputs match within tolerance.")

        return output_path
