import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.models.device import DeviceManager


def test_resolve_cpu_when_no_torch_cuda(monkeypatch):
    monkeypatch.setattr("app.models.device._has_nvidia_smi", lambda: False)
    d = DeviceManager("auto")
    assert d.resolve() == "cpu"


def test_resolve_cuda_when_supported(monkeypatch):
    monkeypatch.setattr("app.models.device._has_nvidia_smi", lambda: True)
    monkeypatch.setattr("app.models.device._query_gpu", lambda: {"name": "RTX 3060", "total_mb": 12288, "free_mb": 10503})
    monkeypatch.setattr("app.models.device._torch_cuda_available", lambda: True)
    monkeypatch.setattr("app.models.device._llama_gpu_offload", lambda: True)
    d = DeviceManager("auto")
    assert d.resolve() == "cuda"


def test_select_device_returns_cpu_when_no_cuda(monkeypatch):
    monkeypatch.setattr("app.models.device._has_nvidia_smi", lambda: False)
    dev, layers = DeviceManager("auto").select_device(estimate_bytes=2**30)
    assert dev == "cpu" and layers == 0


def test_select_device_cuda_layers(monkeypatch):
    monkeypatch.setattr("app.models.device._has_nvidia_smi", lambda: True)
    monkeypatch.setattr("app.models.device._query_gpu", lambda: {"name": "RTX 3060", "total_mb": 12288, "free_mb": 10503})
    monkeypatch.setattr("app.models.device._torch_cuda_available", lambda: True)
    monkeypatch.setattr("app.models.device._llama_gpu_offload", lambda: True)
    dev, layers = DeviceManager("auto").select_device(estimate_bytes=3 * 2**30, total_layers=40)
    assert dev == "cuda"
    assert layers >= 1


def test_select_device_zero_estimate_returns_cpu(monkeypatch):
    monkeypatch.setattr("app.models.device._has_nvidia_smi", lambda: True)
    monkeypatch.setattr("app.models.device._query_gpu", lambda: {"name": "RTX 3060", "total_mb": 12288, "free_mb": 10503})
    monkeypatch.setattr("app.models.device._torch_cuda_available", lambda: True)
    monkeypatch.setattr("app.models.device._llama_gpu_offload", lambda: True)
    dev, layers = DeviceManager("auto").select_device(estimate_bytes=0)
    assert dev == "cpu" and layers == 0


def test_select_device_nonpositive_layers_returns_cpu(monkeypatch):
    monkeypatch.setattr("app.models.device._has_nvidia_smi", lambda: True)
    monkeypatch.setattr("app.models.device._query_gpu", lambda: {"name": "RTX 3060", "total_mb": 12288, "free_mb": 10503})
    monkeypatch.setattr("app.models.device._torch_cuda_available", lambda: True)
    monkeypatch.setattr("app.models.device._llama_gpu_offload", lambda: True)
    dev, layers = DeviceManager("auto").select_device(estimate_bytes=2**30, total_layers=0)
    assert dev == "cpu" and layers == 0


def test_resolve_explicit_device():
    assert DeviceManager("cpu").resolve() == "cpu"
    assert DeviceManager("cuda").resolve() == "cuda"
