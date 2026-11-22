from __future__ import annotations

import asyncio
import uuid
from pathlib import Path

from livekit.agents import APIConnectOptions, APIConnectionError, APITimeoutError, tts


class PiperTTS(tts.TTS):
    def __init__(
        self,
        *,
        binary_path: str,
        model_path: str,
        config_path: str | None = None,
        speaker_id: int = 0,
        length_scale: float = 1.0,
        noise_scale: float = 0.667,
        noise_w: float = 0.8,
        sample_rate: int = 22050,
    ) -> None:
        super().__init__(
            capabilities=tts.TTSCapabilities(streaming=False, aligned_transcript=False),
            sample_rate=sample_rate,
            num_channels=1,
        )
        self._binary_path = binary_path
        self._model_path = model_path
        self._config_path = config_path or ""
        self._speaker_id = speaker_id
        self._length_scale = length_scale
        self._noise_scale = noise_scale
        self._noise_w = noise_w

    @property
    def model(self) -> str:
        return Path(self._model_path).name or "piper"

    @property
    def provider(self) -> str:
        return "Piper"

    def synthesize(
        self,
        text: str,
        *,
        conn_options: APIConnectOptions | None = None,
    ) -> tts.ChunkedStream:
        options = conn_options or APIConnectOptions()
        return _PiperChunkedStream(
            tts=self,
            input_text=text,
            conn_options=options,
        )

    async def aclose(self) -> None:
        return


class _PiperChunkedStream(tts.ChunkedStream):
    def __init__(self, *, tts: PiperTTS, input_text: str, conn_options) -> None:
        super().__init__(tts=tts, input_text=input_text, conn_options=conn_options)
        self._tts = tts

    async def _run(self, output_emitter: tts.AudioEmitter) -> None:
        text = (self._input_text or "").strip()
        if not text:
            return

        command = [
            self._tts._binary_path,
            "--model",
            self._tts._model_path,
            "--output_raw",
            "--length_scale",
            str(self._tts._length_scale),
            "--noise_scale",
            str(self._tts._noise_scale),
            "--noise_w",
            str(self._tts._noise_w),
        ]
        if self._tts._config_path:
            command.extend(["--config", self._tts._config_path])
        if self._tts._speaker_id >= 0:
            command.extend(["--speaker", str(self._tts._speaker_id)])

        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _stdout, stderr = await asyncio.wait_for(
                process.communicate(input=text.encode("utf-8")),
                timeout=max(float(self._conn_options.timeout), 1.0) + 20.0,
            )
            if process.returncode != 0:
                detail = (stderr or b"").decode("utf-8", errors="ignore").strip()
                raise APIConnectionError(f"piper failed ({process.returncode}): {detail[:200]}")

            audio_bytes = _stdout or b""
            if not audio_bytes:
                raise APIConnectionError("piper returned empty audio")

            output_emitter.initialize(
                request_id=str(uuid.uuid4()),
                sample_rate=self._tts.sample_rate,
                num_channels=self._tts.num_channels,
                mime_type="audio/pcm",
            )
            output_emitter.push(audio_bytes)
            output_emitter.flush()
        except asyncio.TimeoutError as exc:
            raise APITimeoutError() from exc
        except APITimeoutError:
            raise
        except APIConnectionError:
            raise
        except Exception as exc:
            raise APIConnectionError(str(exc)) from exc
