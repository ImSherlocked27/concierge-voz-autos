# Draft for “Have you used ElevenLabs?”

Yes. I built Concierge, a Spanish voice agent for a fictional used-car marketplace with ElevenLabs Agents. It uses authenticated webhook tools backed by FastAPI, a policy knowledge base, a private voice session, native agent tests, and success evaluation. The final native suite passed 10/10 cases in one run; a separate harness checks exact tool filters. Across three real audio sessions with a synthetic buyer, 2/3 passed evaluation, with 2.06 s p50 and 3.35 s p95 silence-to-first-audio latency over 12 turns. I kept the initial grounding failure in the report and used it to improve the prompt. The latest session completes the search-to-appointment flow.

Repository: https://github.com/ImSherlocked27/concierge-voz-autos

Captioned demo (88 seconds; synthetic buyer, real agent audio; playback edits disclosed): https://github.com/ImSherlocked27/concierge-voz-autos/blob/main/docs/media/demo.mp4

This is a demo project, not production usage at an employer. No application has been submitted. A permanent hosted demo and the optional Argentine library voice are separate from this repository delivery.
