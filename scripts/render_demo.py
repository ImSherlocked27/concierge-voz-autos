"""Render actual synthetic-user voice evidence as a captioned MP4; no fabricated responses."""
from __future__ import annotations

import argparse
import json
import subprocess
import textwrap
import wave
from array import array
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
import imageio_ffmpeg

ROOT = Path(__file__).resolve().parents[1]
WIDTH, HEIGHT, FPS = 1280, 720, 8


def font(size, bold=False):
    candidates = ([Path("C:/Windows/Fonts/segoeuib.ttf")] if bold else [Path("C:/Windows/Fonts/segoeui.ttf")])
    candidates += [Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")]
    for path in candidates:
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default(size=size)


def trim_pauses(samples: array, rate: int):
    """Keep audio verbatim; shorten only sustained near-silence between utterances."""
    window = rate // 20
    blocks = [(i, min(i + window, len(samples))) for i in range(0, len(samples), window)]
    silent = [max((abs(v) for v in samples[a:b]), default=0) < 100 for a, b in blocks]
    keep = []
    index = 0
    while index < len(blocks):
        if not silent[index]:
            keep.append(blocks[index]); index += 1; continue
        end = index
        while end < len(blocks) and silent[end]:
            end += 1
        # Preserve 400ms of each pause; no time-stretching or generated narration.
        count = min(end - index, 8)
        keep.extend(blocks[index:index + count])
        index = end
    output, mapping = array("h"), []
    for a, b in keep:
        mapping.append((a / rate, b / rate, len(output) / rate))
        output.extend(samples[a:b])

    def translate(seconds):
        previous = 0.0
        for start, end, new_start in mapping:
            if seconds < start:
                return previous
            if seconds <= end:
                return new_start + seconds - start
            previous = new_start + end - start
        return previous
    return output, translate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / ".local/voice-smoke")
    args = parser.parse_args()
    evidence = json.loads((args.source / "events.json").read_text(encoding="utf-8"))
    if evidence.get("error") or evidence.get("synthetic_user") is not True:
        raise SystemExit("Only completed, disclosed synthetic-user evidence can be rendered")
    with wave.open(str(args.source / "conversation.wav"), "rb") as audio:
        if audio.getnchannels() != 1 or audio.getsampwidth() != 2:
            raise SystemExit("Expected 16-bit mono PCM")
        rate = audio.getframerate()
        samples = array("h"); samples.frombytes(audio.readframes(audio.getnframes()))
    samples, translate = trim_pauses(samples, rate)
    events = [{**event, "seconds": translate(event["seconds"])} for event in evidence["events"]]
    duration = len(samples) / rate
    speed = duration / 88 if duration > 90 else 1.0
    playback_duration = duration / speed
    directory = ROOT / "docs/media"
    directory.mkdir(parents=True, exist_ok=True)
    wav_path = args.source / "trimmed.wav"
    with wave.open(str(wav_path), "wb") as output:
        output.setnchannels(1); output.setsampwidth(2); output.setframerate(rate)
        output.writeframes(samples.tobytes())
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    command = [ffmpeg, "-y", "-f", "rawvideo", "-vcodec", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{WIDTH}x{HEIGHT}", "-r", str(FPS), "-i", "-", "-i", str(wav_path), "-vf", f"setpts=PTS/{speed}", "-af", f"atempo={speed}", "-c:v", "libx264", "-preset", "fast", "-crf", "25", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "96k", "-shortest", "-movflags", "+faststart", str(directory / "demo.mp4")]
    log_path = args.source / "render.log"
    with log_path.open("w", encoding="utf-8") as log:
        process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=log)
        for frame in range(int(duration * FPS) + 1):
            current = frame / FPS
            active = next((event for event in reversed(events) if event["seconds"] <= current), None)
            image = Image.new("RGB", (WIDTH, HEIGHT), "#f6f5f1")
            draw = ImageDraw.Draw(image)
            draw.rounded_rectangle((48, 35, 101, 88), radius=14, fill="#224c40")
            draw.text((60, 36), "c.", font=font(37, True), fill="#d9f18a")
            draw.text((118, 43), "concierge", font=font(30, True), fill="#1f302d")
            draw.text((842, 52), "ELEVENLABS AGENTS + FASTAPI", font=font(15), fill="#64706b")
            draw.line((48, 113, WIDTH - 48, 113), fill="#dce0d8", width=2)
            draw.text((55, 143), "UNA CONVERSACIÓN REAL · UN MARKETPLACE FICTICIO", font=font(15, True), fill="#6d8057")
            draw.rounded_rectangle((48, 202, WIDTH - 48, 555), radius=24, fill="#e9eee1")
            if active:
                speaker = "COMPRADOR · VOZ SINTÉTICA" if active["role"] == "user" else "CONCIERGE · AUDIO DE LA SESIÓN"
                draw.text((80, 227), speaker, font=font(17, True), fill="#52664d")
                wrapped = textwrap.wrap(active["text"], width=67)
                for index, line in enumerate(wrapped[:7]):
                    draw.text((80, 278 + index * 34), line, font=font(26), fill="#1f302d")
            else:
                draw.text((80, 270), "Buscá un auto. Consultá sus políticas.", font=font(36), fill="#1f302d")
                draw.text((80, 330), "Confirmá una visita simulada.", font=font(36), fill="#1f302d")
            draw.text((55, 585), "Tools reales: search_vehicles · schedule_visit   /   Políticas desde knowledge base", font=font(17), fill="#52664d")
            draw.rectangle((48, 639, WIDTH - 48, 643), fill="#dce0d8")
            draw.rectangle((48, 639, 48 + int((WIDTH - 96) * min(current / duration, 1)), 643), fill="#6d8057")
            draw.text((55, 665), f"Audio de sesión real · Comprador sintético · Pausas recortadas · Reproducción {speed:.2f}×", font=font(14), fill="#64706b")
            draw.text((1060, 665), f"{int(current / speed):02}s / {int(playback_duration):02}s", font=font(14), fill="#64706b")
            if frame == min(int(20 * FPS), int(duration * FPS)):
                image.save(directory / "demo.jpg", quality=90)
            process.stdin.write(image.tobytes())
        process.stdin.close()
        if process.wait() != 0:
            raise SystemExit("Video render failed; inspect .local/voice-smoke/render.log")
    manifest = {"conversation_id": evidence["conversation_id"], "synthetic_user": True, "microphone_used": False,
                "edits": "Sustained near-silence shortened to 400 ms. Playback speed disclosed on every frame; no generated agent replies.",
                "playback_speed": round(speed, 4), "duration_seconds": round(playback_duration, 2), "audio_source": "Real ElevenLabs Agents WebSocket session", "caption_source": "SDK ASR + agent response callbacks"}
    (directory / "demo.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Real voice demo rendered: {directory / 'demo.mp4'} · {playback_duration:.1f} seconds")


if __name__ == "__main__":
    main()
