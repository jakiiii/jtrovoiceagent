# JTRO Voice Agent

Offline Bangla-to-English desktop voice typing agent for Ubuntu Linux.

## Version-01 scope

- Local microphone capture
- Offline Bangla speech recognition
- Offline Bangla-to-English translation
- Automatic typing into the currently focused application
- Runtime selection between X11 and Wayland injection backends
- CLI control surface and systemd user service support

## Recommended stack

- STT: `faster-whisper`
- Translation: Hugging Face `transformers` with `facebook/nllb-200-distilled-600M`
- Audio capture: `sounddevice` over PortAudio
- X11 injection: `xdotool`
- Wayland injection: `ydotool`
- Daemon model: single-process Python service with a Unix domain control socket
- Config: YAML
- Logging: rotating text logs
- Service management: `systemd --user`

## Why this stack

- `faster-whisper` is the most practical offline Bangla-capable STT choice for Ubuntu when you need reasonable accuracy, CPU support, and optional GPU acceleration.
- NLLB gives better Bangla-to-English translation quality than lightweight phrase-based alternatives, while still being usable locally.
- `sounddevice` is a thin Python layer over PortAudio and is straightforward for microphone device enumeration and low-latency capture.
- `xdotool` is reliable for X11. On Wayland, synthetic input is intentionally restricted, so `ydotool` is the most compositor-agnostic fallback even though it depends on `uinput`.
- A single-process daemon keeps Version-01 operationally simple while still allowing clean abstractions for STT, translation, injection, and future GUI work.

## Architecture

1. `MicrophoneRecorder` captures mono PCM audio from the selected input device.
2. Energy-based segmentation builds utterance-sized chunks.
3. `FasterWhisperSTTEngine` transcribes Bangla speech to Bangla text.
4. `TransformersNllbTranslator` translates Bangla text to English.
5. `TextInjector` writes the English text into the focused application or logs it in dry-run mode.
6. `VoiceAgentService` exposes `status`, `pause`, `resume`, `toggle`, and `shutdown` through a Unix socket.

## Repository layout

```text
app/jtrovoiceagent/
  audio/
  cli/
  core/
  daemon/
  injection/
  services/
  stt/
  translation/
  utils/
configs/
scripts/
systemd/
tests/
logs/
models/cache/
```

## Setup

The default example config is tuned for limited VRAM machines:

- STT stays on `auto`, which uses CUDA when available
- Translation defaults to CPU to avoid GPU OOM with NLLB on 8 GB cards
- If you explicitly set translation to CUDA, the app falls back to CPU on CUDA OOM

### 1. System packages

```bash
./scripts/setup_ubuntu.sh
```

### 2. Warm model caches

```bash
./scripts/download_models.sh ./configs/config.example.yaml
```

### 3. Inspect devices

```bash
source .venv/bin/activate
voice-agent --config ./configs/config.example.yaml devices
```

### 4. Doctor check

```bash
voice-agent --config ./configs/config.example.yaml doctor
```

## Running

### Start daemon

```bash
./scripts/run_agent.sh ./configs/config.example.yaml
```

The default configuration starts in a safe paused state.
It also keeps translation on CPU by default, which is the safest option for machines where
`faster-whisper` and NLLB do not fit in VRAM together.

### Enable listening

```bash
./scripts/control_agent.sh resume ./configs/config.example.yaml
```

### Pause listening

```bash
./scripts/control_agent.sh pause ./configs/config.example.yaml
```

### Toggle listening

```bash
./scripts/control_agent.sh toggle ./configs/config.example.yaml
```

### Stop daemon

```bash
./scripts/control_agent.sh shutdown ./configs/config.example.yaml
```

## Push-to-talk recommendation

Version-01 implements a control socket and CLI toggles instead of a built-in global hotkey daemon. The practical desktop approach is:

- Bind a desktop shortcut to `voice-agent --config ... control resume`
- Bind another shortcut to `voice-agent --config ... control pause`

This is safer than always-on dictation and avoids compositor-specific hotkey code in the first version.

## X11 and Wayland notes

### X11

- Preferred injector: `xdotool`
- Usually works without root
- Suitable for editors, browsers, chat inputs, and IDEs running under X11

### Wayland

- Preferred injector: `ydotool`
- Requires `ydotoold`
- Usually requires access to `/dev/uinput`
- Some desktop environments may still need additional policy or device configuration

If no compatible injector is available and `fallback_to_dry_run` is enabled, the agent logs translated output instead of typing it.

## Systemd user service

Install and enable:

```bash
mkdir -p ~/.config/systemd/user
cp ./systemd/jtrovoiceagent.service ~/.config/systemd/user/jtrovoiceagent.service
systemctl --user daemon-reload
systemctl --user enable --now jtrovoiceagent.service
```

## Testing

```bash
source .venv/bin/activate
pytest
```

## Logs and state

- Logs: `./logs/agent.log`
- Runtime state: `~/.local/state/jtrovoiceagent/state.json`
- Control socket: `~/.local/state/jtrovoiceagent/control.sock`

## Known limitations

- Bangla STT quality depends heavily on microphone quality, background noise, and chosen Whisper model size.
- Translation adds noticeable latency on weaker CPUs.
- Running both Whisper medium and NLLB 600M on CUDA may exceed 8 GB VRAM, so the default config keeps translation on CPU.
- Wayland injection is fundamentally more restricted than X11.
- The current VAD is energy based, not phoneme aware.
- Global hotkeys are intentionally delegated to the desktop environment in Version-01.

## Future Version-02 directions

- Replace the energy gate with a real VAD backend
- Add partial/streaming transcription
- Add model auto-benchmarking and adaptive backend selection
- Add GUI tray status and microphone selector
- Add clipboard fallback and richer injection strategies
- Add optional direct speech-to-English mode for lower latency
