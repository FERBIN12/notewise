from notewise.core import Notebook, chunk_notes, ask, check_understanding

NOTES = """# PID control
A PID controller sums three terms: proportional, integral and derivative of the error.
The integral term removes steady-state error but can cause windup when the actuator saturates.

# Kalman filter
The Kalman filter alternates a predict step and an update step.
The Kalman gain weighs the measurement against the prediction using their covariances.
"""

class FakeLLM:
    def __init__(self, reply): self.reply = reply; self.calls = 0
    def json_chat(self, system, user): self.calls += 1; return dict(self.reply)

def nb():
    n = Notebook(); n.add(NOTES, "controls.md"); return n

def test_chunks_keep_headings_and_lines():
    cs = chunk_notes(NOTES, "controls.md")
    assert [c.heading for c in cs] == ["PID control", "Kalman filter"]
    assert cs[0].lines == (2, 3) and cs[0].id == "controls.md#1"

def test_search_finds_right_chunk():
    assert nb().search("what causes integral windup")[0][0].heading == "PID control"

def test_off_topic_question_never_calls_llm():
    llm = FakeLLM({"in_notes": True, "answer": "Paris", "citations": ["controls.md#1"]})
    out = ask(nb(), llm, "capital of France")
    assert out["in_notes"] is False and llm.calls == 0

def test_invented_citations_are_dropped_and_answer_withheld():
    llm = FakeLLM({"in_notes": True, "answer": "made up", "citations": ["other.md#9"]})
    out = ask(nb(), llm, "what does the Kalman gain weigh")
    assert out["in_notes"] is False and out["guard"] == "citation"

def test_valid_answer_returns_sources():
    llm = FakeLLM({"in_notes": True, "answer": "measurement vs prediction", "citations": ["controls.md#2"]})
    out = ask(nb(), llm, "what does the Kalman gain weigh")
    assert out["citations"] == ["controls.md#2"] and out["sources"][0]["heading"] == "Kalman filter"

class ScriptLLM:
    """Returns replies in order (claim verdicts, then pair checks)."""
    def __init__(self, *replies): self.replies = list(replies)
    def json_chat(self, system, user): return dict(self.replies.pop(0)) if self.replies else {}

def test_split_claims():
    from notewise.core import split_claims
    assert split_claims("It predicts first; then it updates the state. The gain uses covariances, and it weighs data.") == [
        "It predicts first", "then it updates the state", "The gain uses covariances", "it weighs data"]

def test_check_supported_claim_needs_real_evidence():
    ev = "The Kalman filter alternates a predict step and an update step."
    good = ScriptLLM({"verdict": "supported", "citation": "controls.md#2", "evidence": ev})
    out = check_understanding(nb(), good, "Kalman filter", "The Kalman filter does a predict step then an update step.")
    assert out["covered"] and out["score"] == 100 and not out["wrong"]
    fake = ScriptLLM({"verdict": "supported", "citation": "controls.md#2", "evidence": "Kalman invented it in 1960 at NASA."})
    out = check_understanding(nb(), fake, "Kalman filter", "The Kalman filter does a predict step then an update step.")
    assert not out["covered"] and out["unverified"] and out["score"] == 0

def test_contradiction_needs_pair_confirmation():
    ev = "The Kalman gain weighs the measurement against the prediction using their covariances."
    claim = "The Kalman gain ignores the covariances completely."
    v = {"verdict": "contradicted", "citation": "controls.md#2", "evidence": ev, "correction": ev}
    out = check_understanding(nb(), ScriptLLM(v, {"disagree": True}), "Kalman gain", claim)
    assert len(out["wrong"]) == 1 and out["wrong"][0]["citation"] == "controls.md#2"
    out = check_understanding(nb(), ScriptLLM(v, {"disagree": False}), "Kalman gain", claim)
    assert not out["wrong"] and out["unverified"] == [claim.rstrip(".")]

def test_restated_note_is_never_flagged_wrong():
    ev = "The Kalman filter alternates a predict step and an update step."
    v = {"verdict": "contradicted", "citation": "controls.md#2", "evidence": ev}
    out = check_understanding(nb(), ScriptLLM(v, {"disagree": True}), "Kalman filter", "The Kalman filter alternates a predict step and an update step.")
    assert not out["wrong"]

def test_unsupported_citation_is_dropped():
    llm = FakeLLM({"in_notes": True, "answer": "The Kalman gain weighs the measurement against the prediction using covariances",
                   "citations": ["controls.md#1", "controls.md#2"]})
    out = ask(nb(), llm, "what does the Kalman gain weigh against the prediction")
    assert out["citations"] == ["controls.md#2"]
