from jtrovoiceagent.core.config import TranslationConfig
from jtrovoiceagent.core.errors import ConfigurationError
from jtrovoiceagent.translation.base import IdentityTranslator, TranslatorBackend
from jtrovoiceagent.translation.transformers_nllb import TransformersNllbTranslator


def create_translator(config: TranslationConfig) -> TranslatorBackend:
    if not config.enabled or config.backend == "identity":
        return IdentityTranslator()
    if config.backend == "nllb":
        return TransformersNllbTranslator(config)
    raise ConfigurationError(f"Unsupported translation backend: {config.backend}")
