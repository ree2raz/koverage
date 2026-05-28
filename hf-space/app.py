"""Ollive OSS Assistant — Qwen2.5-3B-Instruct on ZeroGPU.

Serves as the open-source baseline for the Underwriter evaluation.
Set OSS_SPACE_URL=https://<username>-ollive-oss-assistant.hf.space in platform/.env
to route Underwriter eval traffic here.
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

# Load at module level — ZeroGPU emulates CUDA here for model loading,
# then provides real GPU inside @spaces.GPU-decorated functions.
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


def chat(message: str, history: list[tuple[str, str]]) -> str:
    """Multi-turn chat used by the Gradio ChatInterface."""
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for user_msg, assistant_msg in history:
        messages.append({"role": "user", "content": user_msg})
        messages.append({"role": "assistant", "content": assistant_msg})
    messages.append({"role": "user", "content": message})
    reply, latency, tokens = _generate(messages)
    print(f"[ollive-oss] latency={latency}s tokens={tokens}")
    return reply


def eval_generate(prompt: str, system: str) -> dict:
    """Single-turn endpoint for the Underwriter harness.

    Called via gradio_client: client.predict(prompt, system, api_name="/eval")
    Returns {"text": str, "latency_s": float, "completion_tokens": int}
    """
    messages = [
        {"role": "system", "content": system or SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]
    reply, latency, tokens = _generate(messages)
    return {"text": reply, "latency_s": latency, "completion_tokens": tokens}


with gr.Blocks(title="Ollive OSS Assistant", theme=gr.themes.Soft()) as demo:
    gr.Markdown(
        f"## Ollive OSS Assistant\n"
        f"Powered by **{MODEL_ID}** on ZeroGPU · "
        "Part of the Ollive AI risk evaluation platform."
    )

    # User-facing chat tab
    with gr.Tab("Chat"):
        gr.ChatInterface(
            fn=chat,
            examples=[
                "What is the capital of France?",
                "Explain transformer attention in one paragraph.",
                "What are the risks of AI-generated medical advice?",
            ],
            cache_examples=False,
        )

    # Programmatic eval tab (hidden from casual users, exposed as API)
    with gr.Tab("Eval API"):
        gr.Markdown(
            "**Underwriter harness endpoint.**\n\n"
            "Call via `client.predict(prompt, system, api_name='/eval')`."
        )
        with gr.Row():
            eval_prompt = gr.Textbox(label="Prompt", lines=4)
            eval_system = gr.Textbox(label="System prompt", lines=4, value=SYSTEM_PROMPT)
        eval_btn = gr.Button("Run")
        eval_out = gr.JSON(label="Result")
        eval_btn.click(fn=eval_generate, inputs=[eval_prompt, eval_system], outputs=eval_out,
                       api_name="eval")


if __name__ == "__main__":
    demo.launch()
