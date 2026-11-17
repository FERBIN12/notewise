from fastapi.testclient import TestClient
from notewise import server

class FakeLLM:
    def __init__(self, reply): self.reply = reply
    def json_chat(self, system, user): return dict(self.reply)

def client(reply=None):
    server.state.update(nb=server.Notebook(), files={})
    server.llm = FakeLLM(reply or {})
    return TestClient(server.app)

def test_index_and_static_served():
    c = client()
    assert "Notewise" in c.get("/").text
    assert c.get("/static/app.js").status_code == 200

def test_add_and_delete_notes_and_sanitize_name():
    c = client()
    r = c.post("/api/notes", json={"name": "../bio#3.md", "text": "# Cells\nMitochondria make ATP for the cell.\n"}).json()
    assert r["files"][0]["name"] == "bio_3.md" and r["chunks"] == 1
    assert c.delete("/api/notes/bio_3.md").json()["chunks"] == 0
    assert c.delete("/api/notes/bio_3.md").status_code == 404

def test_ask_needs_notes_and_valid_mode():
    c = client()
    assert c.post("/api/ask", json={"question": "what is ATP"}).status_code == 400
    c.post("/api/notes", json={"name": "bio.md", "text": "# Cells\nMitochondria make ATP for the cell.\n"})
    assert c.post("/api/ask", json={"question": "x", "mode": "cheat"}).status_code == 400

def test_ask_returns_grounded_answer_with_line_range():
    c = client({"in_notes": True, "answer": "Mitochondria make ATP for the cell.", "citations": ["bio.md#1"]})
    c.post("/api/notes", json={"name": "bio.md", "text": "# Cells\nMitochondria make ATP for the cell.\n"})
    r = c.post("/api/ask", json={"question": "what makes ATP in the cell"}).json()
    assert r["in_notes"] and r["citations"] == ["bio.md#1"] and r["sources"][0]["lines"] == [2, 2]

def test_samples_load():
    c = client()
    assert len(c.post("/api/samples").json()["files"]) >= 2
