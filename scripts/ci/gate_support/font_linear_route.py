"""Owned Linear diagnostic checks using the public parser and daemon dispatcher."""
from pathlib import Path
from uuid import uuid4

from swcli.cli import _typed_operation, build_parser
from swcli.daemon.documents import DocumentLeaseConflict, DocumentRegistry
from swcli.daemon.operations import DocumentUpdateConflict, execute_operation
from swcli.daemon.server import validate_request
from swcli.document_font_scopes import FONT_SCOPES
from swcli.hosts.windows import _com_value
from swcli.hosts.windows_feature_inspection import _same
from swcli.protocol import PROTOCOL_VERSION
from swcli.result_schemas import validate_operation_result

SESSION = "linear-font-diagnostic"


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def refusal(call, error, text):
    try:
        call()
    except error as caught:
        require(text in str(caught), "Unexpected refusal: " + str(caught))
        return type(caught).__name__
    raise RuntimeError("Expected refusal missing")


class LinearRoute:
    """Observe the candidate route and guard the separate fixture-only writer."""

    def __init__(self, app, document, path, *, read_only):
        self.app, self.path = app, path
        self.registry = DocumentRegistry(app)
        self.entry = self.registry.register(document)
        self.registry.set_current(self.entry, session_id=SESSION)
        lease = None if read_only else self.registry.acquire_lease(self.entry, session_id=SESSION, ttl_seconds=1800)
        self.lease_id = None if lease is None else lease["lease_id"]
        self.parser = build_parser()

    def dispatch(self, operation, parameters, stamp, *, lease=None):
        request = validate_request(dict(
            api_version=PROTOCOL_VERSION, request_id="font-linear-" + uuid4().hex, operation=operation,
            parameters=parameters, document_id=self.entry.document_id, session_id=SESSION,
            expected_update_stamp=stamp, **({"lease_id": lease} if lease is not None else {}),
        ))
        result = execute_operation(self.app, request["operation"], request["parameters"], documents=self.registry,
            document_id=request["document_id"], session_id=request["session_id"],
            expected_update_stamp=request["expected_update_stamp"], lease_id=request.get("lease_id"))
        validate_operation_result(operation, result)
        return result

    def read(self, stamp, *, include_linear):
        args = ["document", "font-scopes", "--document", self.entry.document_id,
                "--if-update-stamp", str(stamp), "--json"]
        if include_linear:
            args.append("--include-linear")
        operation, parameters, as_json, document_id, parsed_stamp, lease = _typed_operation(self.parser.parse_args(args))
        require((operation, parameters, as_json, document_id, parsed_stamp, lease)
                == ("document.font-scopes", {"include_linear": True} if include_linear else {},
                    True, self.entry.document_id, stamp, None), "CLI mapped a different document font request")
        result = self.dispatch(operation, parameters, parsed_stamp)
        require(result["ok"] is True, "Public font read failed: " + str(result.get("error")))
        require(result["session_id"] == SESSION and result["document"]["document_id"] == self.entry.document_id
                and result["document"]["update_stamp"] == stamp and result["document"]["active"] is True
                and set(result["fonts"]) == set(FONT_SCOPES) and ("linear" in result) is include_linear,
                "Public font read changed the selected document or returned an unexpected shape")
        return result

    def negative_controls(self, stamp, fonts):
        controls = {
            "stale_stamp": refusal(lambda: self.read(stamp + 1, include_linear=True),
                                   DocumentUpdateConflict, "expected update stamp"),
            "wrong_session": refusal(lambda: self.registry.require_lease(
                self.entry, session_id="linear-font-contender", lease_id=self.lease_id),
                DocumentLeaseConflict, "belongs to session"),
            "missing_lease": refusal(lambda: self.registry.require_lease(
                self.entry, session_id=SESSION, lease_id=None), DocumentLeaseConflict, "active lease"),
        }
        parameters = dict(scope="linear", field="typeface", value="Arial", expected_fonts=fonts)
        controls["linear_public_write"] = refusal(
            lambda: self.dispatch("document.font-scope-set", parameters, stamp, lease=self.lease_id),
            ValueError, "scope")
        parameters["scope"] = "dimensions"
        result = self.dispatch("document.font-scope-set", parameters, stamp, lease=self.lease_id)
        require(result["ok"] is False and result["error"]["type"] == "DocumentFontScopeNotCalibrated"
                and result["mutation"] == dict(attempted=False, may_have_changed=False),
                "The total dimensions write did not remain closed")
        controls["total_public_write"] = result["mutation"]
        return controls

    def guard_write(self, document, path, stamp):
        entry = self.registry.resolve(self.entry.document_id, session_id=SESSION)
        require(_same(self.app, document, entry.document)
                and Path(_com_value(document, "GetPathName")).resolve() == path.resolve() == self.path.resolve(),
                "Private diagnostic selected a different document")
        lease = self.registry.require_lease(entry, session_id=SESSION, lease_id=self.lease_id)
        require(lease is not None and lease["session_id"] == SESSION
                and self.registry.describe(entry, session_id=SESSION)["update_stamp"] == stamp,
                "Private diagnostic lease or update stamp changed")
