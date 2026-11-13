"""A real audio round trip using synthetic user speech; never captures a microphone."""
from __future__ import annotations

import argparse
import json
import os
import threading
import time
import wave
from array import array
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs
from elevenlabs.conversational_ai.conversation import AudioInterface, Conversation

ROOT = Path(__file__).resolve().parents[1]
RATE = 16000


class SyntheticAudio(AudioInterface):
    def __init__(self):
        self.input_callback = None
        self.active = threading.Event()
        self.started = time.monotonic()
        self.playback_end = self.started
        self.chunks = []
        self.events = []
        self.lock = threading.Lock()

    def start(self, input_callback):
        self.input_callback = input_callback
        self.active.set()

    def stop(self):
        self.active.clear()

    def output(self, audio: bytes):
        with self.lock:
            begins = max(time.monotonic(), self.playback_end)
            self.chunks.append((begins - self.started, audio))
            self.playback_end = begins + len(audio) / (RATE * 2)

    def interrupt(self):
        # No physical speaker to stop; retain evidence of any interruption.
        self.events.append({"type": "interruption", "seconds": time.monotonic() - self.started})

    def speak(self, pcm: bytes):
        if not self.active.wait(30):
            raise RuntimeError("Audio session did not start")
        with self.lock:
            self.chunks.append((time.monotonic() - self.started, pcm))
        for index in range(0, len(pcm), 8000):
            if not self.active.is_set():
                raise RuntimeError("Conversation ended before the scripted input finished")
            chunk = pcm[index:index + 8000]
            self.input_callback(chunk)
            time.sleep(len(chunk) / (RATE * 2))
        # Explicit silence allows server-side VAD to end the user turn.
        for _ in range(4):
            if not self.active.is_set():
                break
            self.input_callback(bytes(8000))
            time.sleep(.25)

    def save(self, path: Path):
        with self.lock:
            length = max((int(start * RATE) + len(data) // 2 for start, data in self.chunks), default=0)
            samples = array("h", [0]) * length
            for start, data in self.chunks:
                offset = int(start * RATE)
                values = array("h")
                values.frombytes(data)
                for index, value in enumerate(values):
                    samples[offset + index] = max(-32768, min(32767, samples[offset + index] + value))
        with wave.open(str(path), "wb") as output:
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(RATE)
            output.writeframes(samples.tobytes())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true", help="Explicit opt-in: uses ElevenLabs credits")
    parser.add_argument("--hour", type=int, choices=range(9, 18), default=14)
    parser.add_argument("--minute", type=int, choices=[0, 30], default=30)
    args = parser.parse_args()
    if not args.run:
        print("Use --run to opt in to a real voice session with synthetic user speech. This consumes credits.")
        return
    load_dotenv(ROOT / ".env")
    if not os.getenv("ELEVENLABS_API_KEY") or not os.getenv("AGENT_ID"):
        raise SystemExit("Configure the agent first")
    client = ElevenLabs(api_key=os.environ["ELEVENLABS_API_KEY"])
    target = datetime.now(timezone(timedelta(hours=-3))) + timedelta(days=3)
    while target.weekday() > 4:
        target += timedelta(days=1)
    hour_words = {9:'nueve',10:'diez',11:'once',12:'doce',13:'trece',14:'catorce',15:'quince',16:'dieciséis',17:'diecisiete'}
    time_words = hour_words[args.hour] + (' y media' if args.minute else ' en punto')
    date_words = f"el {target.day} de {['enero','febrero','marzo','abril','mayo','junio','julio','agosto','septiembre','octubre','noviembre','diciembre'][target.month-1]} de {target.year}, a las {time_words}, hora de Argentina"
    phrases = ["Busco una SUV familiar por hasta veintidós mil dólares, con isofix.",
               "Me interesa la Renault Duster. ¿Qué garantía tiene?",
               "Quiero una visita simulada para la Renault Duster " + date_words + ".",
               "Sí, confirmo la visita simulada para la Renault Duster " + date_words + "."]
    # Inputs are synthesized from these disclosed phrases, never from a recording of a person.
    pcm = [b"".join(client.text_to_speech.convert(voice_id="EXAVITQu4vr4xnSDxMaL", model_id="eleven_multilingual_v2", output_format="pcm_16000", text=text)) for text in phrases]
    audio = SyntheticAudio()
    replies, events, latencies = [], [], []

    def response(text):
        replies.append(text)
        events.append({"role": "agent", "text": text, "seconds": time.monotonic() - audio.started})

    def transcript(text):
        events.append({"role": "user", "text": text, "seconds": time.monotonic() - audio.started})

    conversation = Conversation(client, os.environ["AGENT_ID"], requires_auth=True, audio_interface=audio,
                                callback_agent_response=response, callback_user_transcript=transcript,
                                callback_latency_measurement=latencies.append)

    def wait_reply(previous):
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            if len(replies) > previous and time.monotonic() > audio.playback_end + 1.2:
                return
            time.sleep(.2)
        raise RuntimeError("No complete audio reply within 45 seconds; evidence retained without a success claim")

    conversation.start_session()
    error = None
    try:
        wait_reply(0)
        for index, speech in enumerate(pcm):
            previous = len(replies)
            audio.speak(speech)
            wait_reply(previous)
            print(f"Audio turn {index + 1}/{len(pcm)} completed", flush=True)
    except Exception as exc:
        error = str(exc)
    finally:
        conversation.end_session()
    identifier = conversation.wait_for_session_end()
    directory = ROOT / ".local/voice-smoke"
    directory.mkdir(parents=True, exist_ok=True)
    audio.save(directory / "conversation.wav")
    evidence = {"conversation_id": identifier, "synthetic_user": True, "microphone_used": False,
                "events": events, "latency_callback_ms": latencies, "error": error, "audio_events": audio.events}
    (directory / "events.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Voice evidence saved in .local/voice-smoke; conversation_id={identifier}; error={error}")
    if error:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
