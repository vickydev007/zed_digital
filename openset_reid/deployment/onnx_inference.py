import cv2
import numpy as np
import onnxruntime as ort
from typing import List, Union, Tuple, Optional

class ONNXReIDEngine:

    def __init__(self, model_path: str, execution_provider: str='cpu'):
        providers = ['CPUExecutionProvider']
        if execution_provider == 'cuda' and 'CUDAExecutionProvider' in ort.get_available_providers():
            providers = ['CUDAExecutionProvider', 'CPUExecutionProvider']
        sess_opts = ort.SessionOptions()
        sess_opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        sess_opts.intra_op_num_threads = 4
        self.session = ort.InferenceSession(model_path, sess_options=sess_opts, providers=providers)
        self.input_name = self.session.get_inputs()[0].name
        self.output_name = self.session.get_outputs()[0].name
        self.mean = np.array([0.485, 0.456, 0.406], dtype=np.float32).reshape(1, 1, 3)
        self.std = np.array([0.229, 0.224, 0.225], dtype=np.float32).reshape(1, 1, 3)

    def preprocess(self, img_bgr: np.ndarray) -> np.ndarray:
        resized = cv2.resize(img_bgr, (128, 256), interpolation=cv2.INTER_LINEAR)
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
        normalized = (rgb - self.mean) / self.std
        transposed = np.transpose(normalized, (2, 0, 1))
        return np.expand_dims(transposed, axis=0)

    def extract_embedding(self, img_bgr: np.ndarray) -> np.ndarray:
        input_tensor = self.preprocess(img_bgr)
        outputs = self.session.run([self.output_name], {self.input_name: input_tensor})[0]
        emb = outputs[0]
        norm = np.linalg.norm(emb)
        return emb / max(norm, 1e-06)

    def extract_batch(self, img_list: List[np.ndarray]) -> np.ndarray:
        if len(img_list) == 0:
            return np.zeros((0, 512), dtype=np.float32)
        batch_tensors = [self.preprocess(img) for img in img_list]
        batch_input = np.vstack(batch_tensors)
        outputs = self.session.run([self.output_name], {self.input_name: batch_input})[0]
        norms = np.linalg.norm(outputs, axis=1, keepdims=True)
        return outputs / np.maximum(norms, 1e-06)
