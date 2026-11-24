def _post(client, subject, body):
    r = client.post("/v1/tickets", json={"subject": subject, "body": body})
    assert r.status_code == 201, r.text
    return r.json()


def test_confident_grounded_ticket_gets_draft_with_citations(client):
    r = _post(client, "Forgot my password", "I forgot my password and need to reset it, how do I do that?")
    assert r["decision"] == "draft_ready"
    assert r["category"] == "password_reset"
    assert r["draft"] and r["citations"][0]["source"] == "password-reset.md"


def test_legal_threat_escalates_without_draft(client):
    r = _post(client, "Unacceptable", "Reset my password or my lawyer will be in touch.")
    assert r["decision"] == "escalate" and r["draft"] is None and r["category"] == "legal_threat"


def test_unrecognised_ticket_goes_to_human_triage(client):
    r = _post(client, "Hello", "Do you sponsor local football clubs?")
    assert r["decision"] == "human_triage" and r["draft"] is None


def test_feedback_loop_and_stats(client):
    t1 = _post(client, "Password", "I forgot my password, how do I reset it?")["ticket_id"]
    t2 = _post(client, "Password", "I forgot my password, how do I reset it?")["ticket_id"]
    t3 = _post(client, "Password", "I forgot my password, how do I reset it?")["ticket_id"]

    assert client.post(f"/v1/tickets/{t1}/feedback", json={"action": "accept"}).status_code == 201
    edit = client.post(f"/v1/tickets/{t2}/feedback", json={"action": "edit", "edited_text": "Totally different reply."})
    assert edit.status_code == 201 and edit.json()["edit_ratio"] > 0.5
    assert client.post(f"/v1/tickets/{t3}/feedback", json={"action": "reject", "reason": "wrong tone"}).status_code == 201

    stats = client.get("/v1/feedback/stats?days=1").json()
    assert stats["overall"]["total"] == 3
    assert stats["overall"]["acceptance_rate"] == round(1 / 3, 4)
    assert stats["by_category"]["password_reset"]["edit"] == 1


def test_edit_requires_text(client):
    t = _post(client, "Password", "I forgot my password, how do I reset it?")["ticket_id"]
    assert client.post(f"/v1/tickets/{t}/feedback", json={"action": "edit"}).status_code == 422


def test_feedback_on_escalated_ticket_is_conflict(client):
    t = _post(client, "Legal", "I will sue you")["ticket_id"]
    assert client.post(f"/v1/tickets/{t}/feedback", json={"action": "accept"}).status_code == 409


def test_feedback_unknown_ticket_404(client):
    assert client.post("/v1/tickets/nope/feedback", json={"action": "accept"}).status_code == 404


def test_policy_endpoint_lists_five_categories(client):
    p = client.get("/v1/policy").json()
    assert len(p["never_auto_respond"]) == 5 and p["acceptance_threshold"] == 0.75


# ---- queue / listing endpoints (used by the React UI) ----

def _ids(rows):
    return [r["ticket"]["ticket_id"] for r in rows]


def test_list_endpoints_split_tickets_by_decision(client):
    drafted = _post(client, "Password", "I forgot my password, how do I reset it?")["ticket_id"]
    escalated = _post(client, "Legal", "My lawyer will contact you")["ticket_id"]
    triage = _post(client, "Hello", "Do you sponsor local football clubs?")["ticket_id"]

    all_rows = client.get("/v1/tickets").json()
    assert set(_ids(all_rows)) == {drafted, escalated, triage}
    assert client.get("/v1/tickets/").status_code == 200  # trailing slash also works

    assert _ids(client.get("/v1/tickets/AI_drafted_tickets").json()) == [drafted]
    assert set(_ids(client.get("/v1/tickets/Escalated_tickets").json())) == {escalated, triage}


def test_get_ticket_by_id_and_404(client):
    tid = _post(client, "Password", "I forgot my password, how do I reset it?")["ticket_id"]
    rec = client.get(f"/v1/tickets/{tid}").json()
    assert rec["ticket"]["feedback_status"] == "Pending" and rec["result"]["decision"] == "draft_ready"
    assert client.get("/v1/tickets/nope").status_code == 404


def test_feedback_marks_ticket_submitted_and_removes_it_from_the_pending_queue(client):
    tid = _post(client, "Password", "I forgot my password, how do I reset it?")["ticket_id"]
    assert client.post(f"/v1/tickets/{tid}/feedback", json={"action": "accept", "agent_id": "sam"}).status_code == 201
    assert client.get(f"/v1/tickets/{tid}").json()["ticket"]["feedback_status"] == "Submitted"
    assert client.get("/v1/tickets/AI_drafted_tickets").json() == []
    assert _ids(client.get("/v1/tickets").json()) == [tid]  # still in the full list
