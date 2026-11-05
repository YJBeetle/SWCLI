import unittest
from unittest import mock

from swcli.runtime_state import snapshot, result_schema, native_inventory
from swcli.result_schemas import validate_operation_result
from jsonschema import Draft202012Validator


def health(owned=True, visible=False):
    return {"worker_alive": True, "host_connected": True, "host": {
        "process_id": 10, "owned_by_daemon": owned, "visible": visible,
    }}


def inventory(rows):
    return {"processes": rows, "pid_namespace": "windows", "errors": []}


class RuntimeStateTests(unittest.TestCase):
    def check(self, value):
        Draft202012Validator(result_schema()).validate(value)
        validate_operation_result("daemon.runtime-status", value)
        return value

    def test_owned_hidden_and_current_window_observation(self):
        value = self.check(snapshot(health(), inventory=inventory([{"process_id": 10, "visible": False}])))
        self.assertTrue(value["daemon_running"])
        self.assertTrue(value["sw_running"])
        self.assertFalse(value["user_sw_running"])
        self.assertFalse(value["daemon_sw_visible"])
        self.assertTrue(value["visibility_current"])
        self.assertFalse(value["other_sw_running"])
        self.assertEqual(value["process_scope"], "daemon-host")

    def test_attached_user_window_is_not_claimed_as_daemon_owned(self):
        value = self.check(snapshot(health(False), inventory=inventory([{"process_id": 10, "visible": True}])))
        self.assertTrue(value["user_sw_running"])
        self.assertFalse(value["daemon_sw_owned"])
        self.assertTrue(value["daemon_sw_visible"])

    def test_unmanaged_other_process_is_not_guessed_to_be_a_user_instance(self):
        value = self.check(snapshot(health(), inventory=inventory([
            {"process_id": 10, "visible": False}, {"process_id": 11, "visible": True},
        ])))
        self.assertTrue(value["other_sw_running"])
        self.assertIsNone(value["user_sw_running"])

    def test_no_daemon_and_existing_process_proves_running_not_origin(self):
        value = self.check(snapshot(inventory=inventory([{"process_id": 11, "visible": True}]), daemon_running=False, reachable=False, scope="client-host"))
        self.assertFalse(value["daemon_running"])
        self.assertTrue(value["sw_running"])
        self.assertIsNone(value["user_sw_running"])
        self.assertIsNone(value["daemon_sw_visible"])

    def test_empty_inventory_and_missing_host_override_stale_health(self):
        value = self.check(snapshot(health(False, True), inventory=inventory([])))
        self.assertFalse(value["sw_running"])
        self.assertFalse(value["host_connected"])
        self.assertFalse(value["user_sw_running"])
        self.assertIsNone(value["daemon_sw_visible"])

    def test_missing_attached_pid_does_not_assign_another_pid_to_user(self):
        value = self.check(snapshot(health(False), inventory=inventory([{"process_id": 11, "visible": True}])))
        self.assertFalse(value["host_connected"])
        self.assertIsNone(value["user_sw_running"])

    def test_remote_or_legacy_health_labels_visibility_as_startup_cached(self):
        value = self.check(snapshot(health()))
        self.assertTrue(value["sw_running"])
        self.assertFalse(value["daemon_sw_visible"])
        self.assertFalse(value["visibility_current"])
        self.assertEqual(value["visibility_source"], "startup-report")
        self.assertIsNone(value["sw_processes"])
        self.assertIsNone(value["other_sw_running"])

    def test_probe_failure_is_unknown_not_empty(self):
        value = self.check(snapshot(inventory={"processes": None, "pid_namespace": "windows", "errors": [{"code": "Denied", "message": "blocked"}]}, daemon_running=None, reachable=False))
        self.assertIsNone(value["sw_running"])
        self.assertEqual(value["daemon_state"], "unknown")
        self.assertTrue(value["probe_errors"])

    def test_posix_client_never_claims_its_pids_are_windows_host_pids(self):
        with mock.patch("swcli.runtime_state.sys.platform", "darwin"), mock.patch("swcli.host_processes.solidworks_process_ids") as probe:
            self.assertIsNone(native_inventory()["processes"])
        probe.assert_not_called()
