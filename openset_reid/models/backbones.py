import math
import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import List, Tuple, Dict, Optional

class ConvBlock(nn.Module):

    def __init__(self, in_channels: int, out_channels: int, kernel_size: int=3, stride: int=1, padding: int=1, groups: int=1):
        super().__init__()
        self.conv = nn.Conv2d(in_channels, out_channels, kernel_size=kernel_size, stride=stride, padding=padding, groups=groups, bias=False)
        self.bn = nn.BatchNorm2d(out_channels)
        self.act = nn.SiLU(inplace=True)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.act(self.bn(self.conv(x)))

class LightConvBlock(nn.Module):

    def __init__(self, in_channels: int, out_channels: int, kernel_size: int=3, stride: int=1):
        super().__init__()
        padding = (kernel_size - 1) // 2
        self.dw = nn.Conv2d(in_channels, in_channels, kernel_size=kernel_size, stride=stride, padding=padding, groups=in_channels, bias=False)
        self.bn1 = nn.BatchNorm2d(in_channels)
        self.pw = nn.Conv2d(in_channels, out_channels, kernel_size=1, bias=False)
        self.bn2 = nn.BatchNorm2d(out_channels)
        self.act = nn.SiLU(inplace=True)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.act(self.bn1(self.dw(x)))
        x = self.act(self.bn2(self.pw(x)))
        return x

class OmniScaleStreamBlock(nn.Module):

    def __init__(self, channels: int, reduction: int=4):
        super().__init__()
        mid_channels = channels // reduction
        self.stream1 = nn.Sequential(nn.Conv2d(channels, mid_channels, kernel_size=1, bias=False), nn.BatchNorm2d(mid_channels), nn.SiLU(inplace=True))
        self.stream2 = nn.Sequential(nn.Conv2d(channels, mid_channels, kernel_size=1, bias=False), nn.BatchNorm2d(mid_channels), nn.SiLU(inplace=True), LightConvBlock(mid_channels, mid_channels, kernel_size=3))
        self.stream3 = nn.Sequential(nn.Conv2d(channels, mid_channels, kernel_size=1, bias=False), nn.BatchNorm2d(mid_channels), nn.SiLU(inplace=True), LightConvBlock(mid_channels, mid_channels, kernel_size=3), LightConvBlock(mid_channels, mid_channels, kernel_size=3))
        self.stream4 = nn.Sequential(nn.Conv2d(channels, mid_channels, kernel_size=1, bias=False), nn.BatchNorm2d(mid_channels), nn.SiLU(inplace=True), LightConvBlock(mid_channels, mid_channels, kernel_size=3), LightConvBlock(mid_channels, mid_channels, kernel_size=3), LightConvBlock(mid_channels, mid_channels, kernel_size=3))
        self.gate = nn.Sequential(nn.AdaptiveAvgPool2d(1), nn.Conv2d(mid_channels * 4, mid_channels * 4, kernel_size=1, bias=False), nn.BatchNorm2d(mid_channels * 4), nn.Sigmoid())
        self.out_conv = nn.Sequential(nn.Conv2d(mid_channels * 4, channels, kernel_size=1, bias=False), nn.BatchNorm2d(channels))
        self.act = nn.SiLU(inplace=True)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        identity = x
        s1 = self.stream1(x)
        s2 = self.stream2(x)
        s3 = self.stream3(x)
        s4 = self.stream4(x)
        fused = torch.cat([s1, s2, s3, s4], dim=1)
        gate_weights = self.gate(fused)
        fused = fused * gate_weights
        out = self.out_conv(fused)
        return self.act(out + identity)

class OmniScaleReIDBackbone(nn.Module):

    def __init__(self, in_channels: int=3, base_channels: int=64):
        super().__init__()
        self.stem = nn.Sequential(ConvBlock(in_channels, base_channels, kernel_size=7, stride=2, padding=3), nn.MaxPool2d(kernel_size=3, stride=2, padding=1), ConvBlock(base_channels, base_channels, kernel_size=3, stride=1, padding=1))
        self.stage1_down = ConvBlock(base_channels, base_channels * 2, kernel_size=3, stride=2, padding=1)
        self.stage1_block1 = OmniScaleStreamBlock(base_channels * 2, reduction=4)
        self.stage1_block2 = OmniScaleStreamBlock(base_channels * 2, reduction=4)
        self.stage2_down = ConvBlock(base_channels * 2, base_channels * 4, kernel_size=3, stride=2, padding=1)
        self.stage2_block1 = OmniScaleStreamBlock(base_channels * 4, reduction=4)
        self.stage2_block2 = OmniScaleStreamBlock(base_channels * 4, reduction=4)
        self.stage2_block3 = OmniScaleStreamBlock(base_channels * 4, reduction=4)
        self.stage3_conv = ConvBlock(base_channels * 4, base_channels * 6, kernel_size=3, stride=1, padding=1)
        self.stage3_block1 = OmniScaleStreamBlock(base_channels * 6, reduction=4)
        self.stage3_block2 = OmniScaleStreamBlock(base_channels * 6, reduction=4)
        self.out_channels = base_channels * 6

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.stem(x)
        x = self.stage1_down(x)
        x = self.stage1_block1(x)
        x = self.stage1_block2(x)
        x = self.stage2_down(x)
        x = self.stage2_block1(x)
        x = self.stage2_block2(x)
        x = self.stage2_block3(x)
        x = self.stage3_conv(x)
        x = self.stage3_block1(x)
        x = self.stage3_block2(x)
        return x
