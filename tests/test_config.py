from pathlib import Path

from jtrovoiceagent.core.config import load_config


def test_load_config_resolves_relative_paths(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
audio:
  sample_rate: 16000
stt:
  cache_dir: ./cache/stt
  temp_dir: ./cache/tmp
translation:
  cache_dir: ./cache/translation
  fallback_device: cpu
  force_cpu: true
logging:
  directory: ./logs
""",
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert str(config.stt.cache_dir).startswith(str(tmp_path))
    assert str(config.translation.cache_dir).startswith(str(tmp_path))
    assert str(config.logging.directory).startswith(str(tmp_path))
    assert config.translation.fallback_device == "cpu"
    assert config.translation.force_cpu is True
