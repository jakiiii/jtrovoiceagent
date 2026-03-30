class VoiceAgentError(Exception):
    """Base exception for the project."""


class ConfigurationError(VoiceAgentError):
    """Raised when configuration is invalid."""


class DependencyError(VoiceAgentError):
    """Raised when an external dependency is missing."""


class AudioError(VoiceAgentError):
    """Raised when audio capture fails."""


class InjectionError(VoiceAgentError):
    """Raised when text injection fails."""


class ControlError(VoiceAgentError):
    """Raised for daemon control socket failures."""
