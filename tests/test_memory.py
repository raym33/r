"""Tests for memory backends."""

import subprocess
from unittest.mock import patch

from r_cli.core.memory import Memory


def test_gbrain_save_session_captures_only_new_entries(mock_config):
    config = mock_config.model_copy(deep=True)
    config.memory.provider = "gbrain"
    memory = Memory(config, namespace="writer")
    memory.add_short_term("First idea", entry_type="user_input")
    memory.add_short_term("First answer", entry_type="agent_response")

    with (
        patch("r_cli.core.memory.shutil.which", return_value="/usr/bin/gbrain"),
        patch(
            "r_cli.core.memory.subprocess.run",
            return_value=subprocess.CompletedProcess(["gbrain"], 0, "ok", ""),
        ) as run,
    ):
        memory.save_session()
        memory.save_session()
        memory.add_short_term("Second idea", entry_type="user_input")
        memory.save_session()

    assert run.call_count == 3


def test_gbrain_search_is_used_for_relevant_context(mock_config):
    config = mock_config.model_copy(deep=True)
    config.memory.provider = "gbrain"
    config.memory.gbrain_retrieval_command = "query"
    memory = Memory(config, namespace="writer")
    memory.add_short_term("Current discussion", entry_type="user_input")

    with (
        patch("r_cli.core.memory.shutil.which", return_value="/usr/bin/gbrain"),
        patch(
            "r_cli.core.memory.subprocess.run",
            return_value=subprocess.CompletedProcess(["gbrain"], 0, "Brain answer", ""),
        ),
    ):
        context = memory.get_relevant_context("discussion")

    assert "Contexto reciente" in context
    assert "Current discussion" in context
    assert "[Brain] Brain answer" in context


def test_gbrain_falls_back_to_local_storage_when_unavailable(mock_config):
    config = mock_config.model_copy(deep=True)
    config.memory.provider = "gbrain"
    memory = Memory(config, namespace="writer")

    with patch("r_cli.core.memory.shutil.which", return_value=None):
        memory.add_document("alpha beta gamma", doc_id="doc1")
        results = memory.search("beta", n_results=3)

    assert results
    assert results[0]["content"] == "alpha beta gamma"
