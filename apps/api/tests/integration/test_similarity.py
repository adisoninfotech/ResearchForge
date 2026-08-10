"""Similarity / citation-risk checker tests."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

COPIED = "Neural widgets reduce latency under batch size thirty two in synthetic trials."
SOURCE_DOC = (
    f"Background material for testing.\n\n{COPIED}\n\n"
    "Additional unique sentences about measurement noise appear only here."
)


def _csrf(client: AsyncClient) -> str:
    token = client.cookies.get("rf_csrf")
    assert token
    return token


async def _register(client: AsyncClient, email: str) -> None:
    r = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "Password123!", "display_name": "Sim User"},
    )
    assert r.status_code == 200, r.text


async def _project(client: AsyncClient, title: str = "Sim Project") -> dict:
    headers = {"X-CSRF-Token": _csrf(client)}
    created = await client.post(
        "/api/v1/projects",
        headers=headers,
        json={"title": title, "status": "active", "research_field": "NLP"},
    )
    assert created.status_code == 200, created.text
    return created.json()


async def _set_section_text(client: AsyncClient, project_id: str, text: str) -> str:
    headers = {"X-CSRF-Token": _csrf(client)}
    ms = await client.get(f"/api/v1/projects/{project_id}/manuscript")
    assert ms.status_code == 200
    section = ms.json()["sections"][0]
    saved = await client.put(
        f"/api/v1/projects/{project_id}/sections/{section['id']}",
        headers=headers,
        json={
            "structured_content": {
                "type": "doc",
                "content": [{"type": "paragraph", "content": [{"type": "text", "text": text}]}],
                "plain_text": text,
            },
            "expected_revision": section["revision_number"],
        },
    )
    assert saved.status_code == 200, saved.text
    return section["id"]


async def _upload_txt(client: AsyncClient, project_id: str, name: str, text: str) -> dict:
    headers = {"X-CSRF-Token": _csrf(client)}
    r = await client.post(
        f"/api/v1/projects/{project_id}/files/upload",
        headers=headers,
        files={"file": (name, text.encode("utf-8"), "text/plain")},
        data={"process_sync": "true"},
    )
    assert r.status_code == 200, r.text
    return r.json()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_exact_copied_sentence_and_report_footer(client: AsyncClient) -> None:
    await _register(client, "simexact@example.com")
    project = await _project(client)
    await _upload_txt(client, project["id"], "source.txt", SOURCE_DOC)
    await _set_section_text(
        client,
        project["id"],
        f"Introduction follows. {COPIED} We then discuss limits.",
    )
    headers = {"X-CSRF-Token": _csrf(client)}
    run = await client.post(
        f"/api/v1/projects/{project['id']}/similarity/run",
        headers=headers,
        json={"threshold_profile": "default"},
    )
    assert run.status_code == 200, run.text
    body = run.json()
    assert body["status"] == "completed"
    report = body["report"]
    assert report["footer"]["disclaimer"]
    assert (
        "Turnitin" in report["footer"]["disclaimer"]
        or "human review" in report["footer"]["disclaimer"].lower()
    )
    assert report["coverage"]["limitations"]
    assert report["coverage"]["licensed_provider_status"] == "not_configured"
    assert any(f["classification"] == "exact_textual_overlap" for f in report["findings"])
    # No misleading single overall percentage field
    assert "overall_percent" not in report
    assert "overall_similarity" not in report


@pytest.mark.integration
@pytest.mark.asyncio
async def test_proper_quotation_and_common_phrase(client: AsyncClient) -> None:
    await _register(client, "simquote@example.com")
    project = await _project(client)
    await _upload_txt(client, project["id"], "source.txt", SOURCE_DOC)
    quoted = f'In this paper we note that "{COPIED}" (Smith, 2020).'
    await _set_section_text(client, project["id"], quoted + " Future work remains.")
    headers = {"X-CSRF-Token": _csrf(client)}
    run = await client.post(
        f"/api/v1/projects/{project['id']}/similarity/run",
        headers=headers,
        json={},
    )
    assert run.status_code == 200, run.text
    classes = {f["classification"] for f in run.json()["report"]["findings"]}
    assert "proper_quotation" in classes or "exact_textual_overlap" in classes
    # common phrase alone
    await _set_section_text(client, project["id"], "In this paper we propose a method.")
    run2 = await client.post(
        f"/api/v1/projects/{project['id']}/similarity/run",
        headers=headers,
        json={"exclude_common_phrases": False},
    )
    assert run2.status_code == 200
    # Should not claim zero plagiarism language
    meta = await client.get(f"/api/v1/projects/{project['id']}/similarity/meta")
    assert "Zero plagiarism" in meta.json()["language"]["forbidden_claims"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_citation_but_excessive_and_light_paraphrase(client: AsyncClient) -> None:
    await _register(client, "simcite@example.com")
    project = await _project(client)
    await _upload_txt(client, project["id"], "source.txt", SOURCE_DOC)
    # Same sentence with citation — still excessive if exact
    text = f"{COPIED} (Doe, 2021)."
    await _set_section_text(client, project["id"], text)
    headers = {"X-CSRF-Token": _csrf(client)}
    run = await client.post(
        f"/api/v1/projects/{project['id']}/similarity/run",
        headers=headers,
        json={},
    )
    assert run.status_code == 200
    classes = {f["classification"] for f in run.json()["report"]["findings"]}
    assert (
        "excessive_similarity_despite_citation" in classes
        or "exact_textual_overlap" in classes
        or "properly_cited_paraphrase" in classes
    )

    # Light paraphrase
    para = "Neural widgets cut latency when the batch size is thirty two during synthetic trials."
    await _set_section_text(client, project["id"], para)
    run2 = await client.post(
        f"/api/v1/projects/{project['id']}/similarity/run",
        headers=headers,
        json={"threshold_profile": "strict"},
    )
    assert run2.status_code == 200
    assert run2.json()["report"]["method_explanations"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_bibliography_self_overlap_false_positive_rewrite(client: AsyncClient) -> None:
    await _register(client, "simflow@example.com")
    project = await _project(client)
    headers = {"X-CSRF-Token": _csrf(client)}

    # Bibliography-like content
    bib = "@article{x2020, title={Neural widgets reduce latency}, year={2020}}"
    headers_up = {"X-CSRF-Token": _csrf(client)}
    bib_upload = await client.post(
        f"/api/v1/projects/{project['id']}/files/upload",
        headers=headers_up,
        files={"file": ("refs.bib", bib.encode("utf-8"), "text/x-bibtex")},
        data={"process_sync": "true"},
    )
    assert bib_upload.status_code == 200, bib_upload.text
    await _set_section_text(client, project["id"], bib)
    # Put text in references section if present
    ms = await client.get(f"/api/v1/projects/{project['id']}/manuscript")
    refs = next((s for s in ms.json()["sections"] if "reference" in s["title"].lower()), None)
    if refs:
        await client.put(
            f"/api/v1/projects/{project['id']}/sections/{refs['id']}",
            headers=headers,
            json={
                "structured_content": {
                    "type": "doc",
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [{"type": "text", "text": bib}],
                        }
                    ],
                    "plain_text": bib,
                },
                "expected_revision": refs["revision_number"],
            },
        )

    # Self-overlap via authorized prior
    prior = await _project(client, "Prior Paper")
    await _set_section_text(client, prior["id"], f"Prior unique lead-in. {COPIED}")
    await _set_section_text(client, project["id"], f"Current paper states: {COPIED}")
    await _upload_txt(client, project["id"], "src2.txt", "Unrelated filler document content here.")

    run = await client.post(
        f"/api/v1/projects/{project['id']}/similarity/run",
        headers=headers,
        json={"authorized_prior_project_ids": [prior["id"]]},
    )
    assert run.status_code == 200, run.text
    report = run.json()["report"]
    report_id = report["id"]
    findings = report["findings"]
    assert findings
    finding_id = findings[0]["id"]

    # False positive resolution
    resolved = await client.post(
        f"/api/v1/projects/{project['id']}/similarity/findings/{finding_id}/resolve",
        headers=headers,
        json={"action": "false_positive", "note": "Intentional reuse for test"},
    )
    assert resolved.status_code == 200
    assert resolved.json()["resolution"]["action"] == "false_positive"

    # Rewrite workflow
    rewrite = await client.post(
        f"/api/v1/projects/{project['id']}/similarity/findings/{finding_id}/rewrite",
        headers=headers,
    )
    assert rewrite.status_code == 200
    assert rewrite.json()["resolution"]["rewrite_proposed"]
    assert rewrite.json()["resolution"]["rewrite_diff"]

    accepted = await client.post(
        f"/api/v1/projects/{project['id']}/similarity/findings/{finding_id}/rewrite/accept",
        headers=headers,
        json={},
    )
    assert accepted.status_code == 200
    assert accepted.json()["status"] == "rewritten"
    assert accepted.json()["rerun_job_id"]

    download = await client.get(
        f"/api/v1/projects/{project['id']}/similarity/reports/{report_id}/download"
    )
    assert download.status_code == 200
    assert "Sources checked" in download.text or "sources" in download.text.lower()
    assert "human review" in download.text.lower()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_no_source_safe_summary_and_isolation(client: AsyncClient) -> None:
    await _register(client, "simnone@example.com")
    project = await _project(client)
    await _set_section_text(
        client,
        project["id"],
        "Completely original wording about indigo marmots and lunar cheese.",
    )
    headers = {"X-CSRF-Token": _csrf(client)}
    run = await client.post(
        f"/api/v1/projects/{project['id']}/similarity/run",
        headers=headers,
        json={},
    )
    assert run.status_code == 200
    summary = run.json()["report"]["summary_text"]
    assert "No significant textual overlap was identified within the sources checked." in summary
    assert "plagiarism-free" not in summary.lower()
    assert "zero plagiarism" not in summary.lower()

    # Reproducible fingerprint
    run2 = await client.post(
        f"/api/v1/projects/{project['id']}/similarity/run",
        headers=headers,
        json={},
    )
    assert run.json()["report"]["content_sha256"] == run2.json()["report"]["content_sha256"]

    await client.post("/api/v1/auth/logout", headers=headers)
    await _register(client, "simintruder@example.com")
    other = {"X-CSRF-Token": _csrf(client)}
    denied = await client.get(
        f"/api/v1/projects/{project['id']}/similarity/reports/{run.json()['report']['id']}",
        headers=other,
    )
    assert denied.status_code == 404
