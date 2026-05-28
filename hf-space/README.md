---
title: Da Platform
emoji: 🌖
colorFrom: red
colorTo: red
sdk: gradio
sdk_version: 6.15.1
python_version: '3.12'
app_file: app.py
pinned: false
license: apache-2.0
---

# Ollive OSS Assistant

Open-source LLM assistant using **Qwen/Qwen2.5-3B-Instruct** on ZeroGPU.

This Space is the OSS baseline for the Ollive Underwriter evaluation harness —
it runs the same prompts as the frontier model (GPT-4.1) to produce a comparative
hallucination / bias / safety scorecard.

## Eval endpoint

The Underwriter harness calls this Space via the Gradio client:

```
client.predict(prompt, system_prompt, api_name="/eval")
→ {"text": "...", "latency_s": 1.23, "completion_tokens": 87}
```

Set `OSS_SPACE_URL=https://ree2raz-da-platform.hf.space` in `platform/.env`
to route Underwriter eval traffic here instead of OpenRouter.
