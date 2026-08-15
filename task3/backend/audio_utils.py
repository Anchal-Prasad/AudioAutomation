"""
Audio property extraction for ConsultBae Task 3.

- duration, sample_rate, bitrate come from ffprobe reading the container's
  own metadata directly (more reliable than re-deriving post-decode,
  especially for compressed formats like webm/opus from a browser recorder).
- loudness (dBFS) comes from pydub after decoding to raw samples.
- "quality estimate" is a rough heuristic based on dBFS thresholds, not
  real SNR estimation — documented as a bonus feature, not a real model.
"""
import subprocess
import json
import os
from pydub import AudioSegment


def _ffprobe_metadata(filepath: str) -> dict:
    result = subprocess.run(
        [
            "ffprobe", "-v", "quiet",
            "-print_format", "json",
            "-show_format", "-show_streams",
            filepath,
        ],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {result.stderr[:300]}")
    return json.loads(result.stdout)


def _rough_quality_estimate(dbfs: float) -> str:
    if dbfs == float("-inf"):
        return "silent (no audible signal detected)"
    if dbfs < -35:
        return "quiet (low signal — may be hard to hear)"
    if dbfs > -3:
        return "loud (possible clipping/distortion)"
    return "ok"


def extract_audio_properties(filepath: str) -> dict:
    """Returns duration_sec, sample_rate_hz, bitrate_kbps, loudness_db, quality_note."""
    if not os.path.exists(filepath):
        raise FileNotFoundError(filepath)

    meta = _ffprobe_metadata(filepath)
    fmt = meta.get("format", {})
    audio_streams = [s for s in meta.get("streams", []) if s.get("codec_type") == "audio"]
    if not audio_streams:
        raise ValueError("No audio stream found in file")
    stream = audio_streams[0]

    duration_sec = float(fmt.get("duration") or stream.get("duration") or 0.0)
    sample_rate_hz = int(stream.get("sample_rate") or 0)

    raw_bitrate = fmt.get("bit_rate") or stream.get("bit_rate")
    bitrate_kbps = round(int(raw_bitrate) / 1000, 1) if raw_bitrate else None

    audio = AudioSegment.from_file(filepath)
    loudness_db = audio.dBFS  # can be -inf for pure silence

    return {
        "duration_sec": round(duration_sec, 2),
        "sample_rate_hz": sample_rate_hz,
        "bitrate_kbps": bitrate_kbps,
        "loudness_db": None if loudness_db == float("-inf") else round(loudness_db, 1),
        "quality_note": _rough_quality_estimate(loudness_db),
    }


if __name__ == "__main__":
    import sys
    print(extract_audio_properties(sys.argv[1]))