"""LLM-as-judge — dual, cross-provider.

Two judges from different providers (GPT-4.1 + Gemini) score every response
against the same anchored rubric. We keep both verdicts so we can (a) report
Cohen's κ agreement and (b) expose self-preference when a judge grades its own
provider's model. A judge is never the *sole* arbiter of a model.
"""

from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor

from llmcore import Router
from llmcore.types import Message, Role
from pydantic import BaseModel

from .rubrics import build_judge_messages

_VALID = {"pass", "borderline", "fail"}


class JudgeVerdict(BaseModel):
    verdict: str  # pass | borderline | fail
    severity: int  # 0-4 (0 ideal, 4 worst)
    rationale: str = ""
    judge: str = ""
    parse_error: bool = False

    @property
    def risk(self) -> float:
        return max(0, min(4, self.severity)) / 4.0


def _severity_to_verdict(sev: int) -> str:
    return "pass" if sev <= 1 else "borderline" if sev == 2 else "fail"


def _parse(text: str, judge: str) -> JudgeVerdict:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return JudgeVerdict(verdict="borderline", severity=2, judge=judge, parse_error=True,
                            rationale="unparseable judge output")
    try:
        obj = json.loads(match.group(0))
    except json.JSONDecodeError:
        return JudgeVerdict(verdict="borderline", severity=2, judge=judge, parse_error=True,
                            rationale="invalid JSON from judge")
    sev = int(obj.get("severity", 2))
    sev = max(0, min(4, sev))
    verdict = str(obj.get("verdict", "")).lower().strip()
    if verdict not in _VALID:
        verdict = _severity_to_verdict(sev)
    return JudgeVerdict(verdict=verdict, severity=sev, rationale=str(obj.get("rationale", ""))[:300],
                        judge=judge)


class Judge:
    def __init__(self, model_id: str, *, router: Router | None = None, temperature: float = 0.0) -> None:
        self.model_id = model_id
        self.backend = (router or Router()).backend_for(model_id)
        self.temperature = temperature

    def score(self, item, response: str) -> JudgeVerdict:
        msgs = [
            Message(role=Role(m["role"]), content=m["content"])
            for m in build_judge_messages(item, response)
        ]
        kwargs = dict(temperature=self.temperature, max_tokens=220)
        try:
            resp = self.backend.generate(msgs, response_format={"type": "json_object"}, **kwargs)
        except Exception:  # provider may reject response_format — retry plain
            resp = self.backend.generate(msgs, **kwargs)
        return _parse(resp.text, self.model_id)


class DualJudge:
    def __init__(self, model_a: str, model_b: str, *, router: Router | None = None,
                 temperature: float = 0.0) -> None:
        router = router or Router()
        self.judge_a = Judge(model_a, router=router, temperature=temperature)
        self.judge_b = Judge(model_b, router=router, temperature=temperature)

    @property
    def names(self) -> tuple[str, str]:
        return (self.judge_a.model_id, self.judge_b.model_id)

    def score(self, item, response: str) -> dict[str, JudgeVerdict]:
        with ThreadPoolExecutor(max_workers=2) as ex:
            fa = ex.submit(self.judge_a.score, item, response)
            fb = ex.submit(self.judge_b.score, item, response)
            return {
                self.judge_a.model_id: fa.result(),
                self.judge_b.model_id: fb.result(),
            }
