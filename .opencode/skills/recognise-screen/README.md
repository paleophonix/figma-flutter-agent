# Recognise step — SCREEN board

## Purpose

Step 1/7 vision-first user-visible symptoms. Four-pass vision protocol: ref, capture, compare strip, heatmap.

## Usage example

Orchestrator runs `prepare_recognise_vision_bundle()` then assembles prompt with board=screen and `repair-master-screen.md` L1.

## LLM context

Requires verified capture. Heatmap is pass D only. Executive output is recognise.json symptoms[], not BATCH TRIAGE prose.
