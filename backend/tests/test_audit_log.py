import json

from app import audit_log


def test_log_tool_call_success_writes_valid_json_line(caplog):
    with caplog.at_level("INFO", logger="jarvis.audit"):
        audit_log.log_tool_call(
            target="desktop",
            tool="desktop_click",
            arguments={"x": 1, "y": 2},
            result={"clicked": True},
        )

    assert len(caplog.messages) == 1
    entry = json.loads(caplog.messages[0])
    assert entry["target"] == "desktop"
    assert entry["tool"] == "desktop_click"
    assert entry["arguments"] == {"x": 1, "y": 2}
    assert entry["ok"] is True
    assert entry["result"] == {"clicked": True}
    assert "error" not in entry
    assert "timestamp" in entry


def test_log_tool_call_error_marks_ok_false_and_omits_result(caplog):
    with caplog.at_level("INFO", logger="jarvis.audit"):
        audit_log.log_tool_call(
            target="phone",
            tool="phone_run_command",
            arguments={"command": "rm -rf /"},
            error="Comando rechazado por el blocklist de seguridad",
        )

    entry = json.loads(caplog.messages[0])
    assert entry["ok"] is False
    assert entry["error"] == "Comando rechazado por el blocklist de seguridad"
    assert "result" not in entry


def test_log_tool_call_never_raises_for_non_json_native_arguments():
    class Weird:
        def __str__(self) -> str:
            return "weird-object"

    # No debe lanzar aunque el argumento no sea serializable de forma nativa
    # (json.dumps con default=str tiene que poder manejarlo).
    audit_log.log_tool_call(target="desktop", tool="x", arguments={"thing": Weird()}, result=None)


def test_log_tool_call_does_not_propagate_to_root_logger(caplog):
    """El logger de auditoría es un stream aparte — no debe duplicarse en el log
    general/consola de la app."""
    assert audit_log._audit_logger.propagate is False
