"""
OpenSet-ReID: Open-Set Person Re-Identification under Low Inter-Class Variance
Package setup.
"""
from setuptools import setup, find_packages

setup(
    name="openset-reid",
    version="1.0.0",
    description="Open-Set Person Re-Identification under Low Inter-Class Variance",
    author="Zed Digital AI Engineering",
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=[
        "torch>=2.0",
        "torchvision>=0.15",
        "numpy>=1.24",
        "opencv-python>=4.7",
        "Pillow>=9.0",
        "scipy>=1.10",
        "scikit-learn>=1.2",
        "matplotlib>=3.7",
        "seaborn>=0.12",
        "onnx>=1.14",
        "onnxruntime>=1.15",
        "tqdm>=4.65",
    ],
)
