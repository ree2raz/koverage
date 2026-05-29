"""Ollive OSS Inference Backend — Qwen2.5-3B-Instruct on ZeroGPU.

This Space is the inference backend for the Ollive AI risk evaluation platform.
It is NOT a user-facing demo — the UI below exists only because HF Spaces requires
a Gradio app as the entry point.

The Underwriter evaluation harness calls the /eval API endpoint programmatically:
    client = gradio_client.Client("ree2raz/da-platform")
    result = client.predict(prompt, system, api_name="/eval")
    # → {"text": str, "latency_s": float, "completion_tokens": int}

Source: https://github.com/ree2raz/olive-platform
"""

import time

import gradio as gr
import spaces
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

MODEL_ID = "Qwen/Qwen2.5-3B-Instruct"
MAX_NEW_TOKENS = 512
TEMPERATURE = 0.7

SYSTEM_PROMPT = (
    "You are a helpful, honest, and careful assistant. Hold a natural multi-turn "
    "conversation and remember what the user told you earlier. If unsure of a fact, "
    "say so rather than guessing."
)

# Load at module level — ZeroGPU requires this; model is kept warm between requests.
tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
model = AutoModelForCausalLM.from_pretrained(
    MODEL_ID,
    torch_dtype=torch.float16,
    device_map="cuda",  # explicit; device_map="auto" is unreliable on ZeroGPU
)


@spaces.GPU(duration=120)
def _generate(messages: list[dict]) -> tuple[str, float, int]:
    t0 = time.perf_counter()
    text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer(text, return_tensors="pt").to(model.device)
    with torch.no_grad():
        out = model.generate(
            **inputs,
            max_new_tokens=MAX_NEW_TOKENS,
            temperature=TEMPERATURE,
            do_sample=TEMPERATURE > 0,
            pad_token_id=tokenizer.eos_token_id,
        )
    new_tokens = out[0][inputs["input_ids"].shape[1]:]
    reply = tokenizer.decode(new_tokens, skip_special_tokens=True)
    latency = time.perf_counter() - t0
    return reply, round(latency, 3), int(len(new_tokens))


def eval_generate(prompt: str, system: str) -> dict:
    """Underwriter harness endpoint. Called via gradio_client, api_name='/eval'."""
    messages = [
        {"role": "system", "content": system or SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]
    reply, latency, tokens = _generate(messages)
    return {"text": reply, "latency_s": latency, "completion_tokens": tokens}


with gr.Blocks(title="Ollive OSS Inference Backend") as demo:
    gr.Markdown(
        """# Ollive OSS Inference Backend

This Space is a **programmatic inference endpoint**, not a user-facing assistant.

It serves `Qwen/Qwen2.5-3B-Instruct` on ZeroGPU and is called by the
[Ollive evaluation harness](https://github.com/ree2raz/olive-platform) to benchmark
the OSS model against frontier models (GPT-4.1) across four risk axes:
hallucination, bias, content safety, and sensitive-data disclosure.

**API usage (from the harness):**
```python
from gradio_client import Client
client = Client("ree2raz/da-platform")
result = client.predict(prompt, system_prompt, api_name="/eval")
# → {"text": "...", "latency_s": 1.23, "completion_tokens": 42}
```

See the full platform at **github.com/ree2raz/olive-platform**.
"""
    )

    # Minimal UI wrapper required by HF Spaces — the real interface is the /eval API above.
    with gr.Accordion("API endpoint (for harness use)", open=False):
        with gr.Row():
            eval_prompt = gr.Textbox(label="Prompt", lines=3)
            eval_system = gr.Textbox(label="System prompt", lines=3, value=SYSTEM_PROMPT)
        eval_btn = gr.Button("Run")
        eval_out = gr.JSON(label="Result")
        eval_btn.click(fn=eval_generate, inputs=[eval_prompt, eval_system], outputs=eval_out,
                       api_name="eval")


if __name__ == "__main__":
    demo.launch()
