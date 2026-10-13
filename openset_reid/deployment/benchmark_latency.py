"""
Edge Deployment Latency, Throughput, and Gallery Search Profiler.
Measures real-time performance to verify edge deployment constraints.
"""

import time
import numpy as np
from typing import Dict, List

from openset_reid.deployment.onnx_inference import ONNXReIDEngine


class EdgePerformanceProfiler:
    """
    Profiles end-to-end latency and gallery search speed.
    """
    def __init__(self, onnx_model_path: str):
        self.engine = ONNXReIDEngine(onnx_model_path)

    def benchmark_inference_latency(self, num_warmup: int = 20, num_runs: int = 100) -> Dict[str, float]:
        """
        Profiles single-crop embedding extraction latency.
        """
        dummy_crop = np.random.randint(0, 255, (256, 128, 3), dtype=np.uint8)

        # Warmup
        for _ in range(num_warmup):
            _ = self.engine.extract_embedding(dummy_crop)

        latencies = []
        for _ in range(num_runs):
            t0 = time.perf_counter()
            _ = self.engine.extract_embedding(dummy_crop)
            t1 = time.perf_counter()
            latencies.append((t1 - t0) * 1000.0)  # ms

        latencies = np.array(latencies)
        return {
            "mean_ms": float(np.mean(latencies)),
            "std_ms": float(np.std(latencies)),
            "median_ms": float(np.median(latencies)),
            "p95_ms": float(np.percentile(latencies, 95)),
            "p99_ms": float(np.percentile(latencies, 99)),
            "fps": float(1000.0 / np.mean(latencies))
        }

    def benchmark_batch_throughput(self, batch_sizes: List[int] = [1, 4, 8, 16, 32],
                                   num_runs: int = 30) -> Dict[int, float]:
        """
        Profiles throughput across various batch sizes (crops/second).
        """
        throughput_results = {}
        for bs in batch_sizes:
            dummy_batch = [np.random.randint(0, 255, (256, 128, 3), dtype=np.uint8) for _ in range(bs)]
            # Warmup
            _ = self.engine.extract_batch(dummy_batch)

            t0 = time.perf_counter()
            for _ in range(num_runs):
                _ = self.engine.extract_batch(dummy_batch)
            elapsed = time.perf_counter() - t0

            total_crops = bs * num_runs
            fps = total_crops / elapsed
            throughput_results[bs] = float(fps)
        return throughput_results

    def benchmark_gallery_search_scaling(self, gallery_sizes: List[int] = [100, 1000, 5000, 10000],
                                         embedding_dim: int = 512,
                                         num_queries: int = 100) -> Dict[int, float]:
        """
        Profiles gallery matching time against large open-set galleries.
        """
        search_times = {}
        for n_gal in gallery_sizes:
            # Synthetic normalized gallery matrix
            gallery = np.random.randn(n_gal, embedding_dim).astype(np.float32)
            gallery /= np.linalg.norm(gallery, axis=1, keepdims=True)

            queries = np.random.randn(num_queries, embedding_dim).astype(np.float32)
            queries /= np.linalg.norm(queries, axis=1, keepdims=True)

            t0 = time.perf_counter()
            # Vectorized matrix product + top-2 search
            scores = np.dot(queries, gallery.T)
            top2_indices = np.argpartition(-scores, 2, axis=1)[:, :2]
            elapsed = (time.perf_counter() - t0) * 1000.0 / num_queries  # ms per query

            search_times[n_gal] = float(elapsed)
        return search_times
