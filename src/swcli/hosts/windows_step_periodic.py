"""Three-preference transaction for guarded STEP periodic-face exports."""
from contextlib import contextmanager
from .native_trace import native_call
from .windows_step_export import StepExportError, _read_native_enum_constants

TOGGLE = 'swStepExportSplitPeriodic'


def read_periodic_constant(path):
    return _read_native_enum_constants(path, {'swUserPreferenceToggle_e': {TOGGLE}})[TOGGLE]


@contextmanager
def periodic_preferences(app, integer_keys, desired_integers, geometry_domain, value, verify_context, result, *, swconst):
    """Full three-value CAS; restore only owned original/target values, never foreign values."""
    keys = {**integer_keys, TOGGLE: read_periodic_constant(swconst)}
    stages, returns = [], []

    def snapshot(phase):
        values = {}
        for name, key in keys.items():
            getter = app.GetUserPreferenceToggle if name == TOGGLE else app.GetUserPreferenceIntegerValue
            observed = native_call('step-export', phase + '.' + name, lambda: getter(key))
            if type(observed) is not (bool if name == TOGGLE else int):
                raise StepExportError('StepPreferenceUnavailable', 'unreadable STEP preference: ' + name)
            values[name] = observed
        stages.append({'phase': phase, 'values': values})
        return values

    def write(name, target, phase):
        setter = app.SetUserPreferenceToggle if name == TOGGLE else app.SetUserPreferenceIntegerValue
        status = native_call('step-export', phase + '.' + name, lambda: setter(keys[name], target))
        row = dict(phase=phase, preference=name, return_type=type(status).__name__)
        if status is None or type(status) is bool:
            row['value'] = status
        returns.append(row)
        return status

    def accepted(name, status):
        # ISldWorks toggle setter is void; integer setter returns bool (installed 2025 API).
        return status is None if name == TOGGLE else status is True

    before = snapshot('periodic-before')
    # The existing two-value domain remains unchanged; the toggle must be a strict bool.
    if before['swStepAP'] not in (203, 214) or before['swStepExportPreference'] not in set(geometry_domain):
        raise StepExportError('StepPreferenceUnsupported', 'original STEP preferences are not safely restorable')
    desired = {name: desired_integers[name] for name in integer_keys}
    desired[TOGGLE] = value
    evidence = result['step_preferences'] = dict(before=before, requested=desired, restored=False, stages=stages, setter_returns=returns)
    expected = dict(before)
    attempted = []
    first = None
    verify_context()
    try:
        for name in keys:
            if snapshot('periodic-cas-before-set') != expected:
                raise StepExportError('StepPreferenceConflict', 'complete STEP preference CAS changed')
            if before[name] == desired[name]:
                continue
            attempted.append(name)  # A throwing/False setter may already have changed its value.
            result['mutation'] = dict(attempted=True, may_have_changed=True)
            status = write(name, desired[name], 'periodic-set')
            expected[name] = desired[name]
            if not accepted(name, status):
                raise StepExportError('StepPreferenceRejected', 'STEP setter rejected ' + name)
            if snapshot('periodic-readback') != expected:
                raise StepExportError('StepPreferenceReadbackFailed', 'complete STEP readback differs')
        verify_context()
        if snapshot('periodic-before-export') != desired:
            raise StepExportError('StepPreferenceConflict', 'complete STEP CAS changed before export')
        yield
        if not result.get('error'):
            verify_context()
            if snapshot('periodic-after-export') != desired:
                raise StepExportError('StepPreferenceReadbackFailed', 'STEP preferences changed during export')
    except BaseException as exc:
        first = exc
        raise
    finally:
        failures = []
        for name in reversed(attempted):
            try:
                current = snapshot('periodic-restore-cas')[name]
                if current not in (before[name], desired[name]):
                    raise StepExportError('StepPreferenceConflict', 'foreign value left untouched: ' + name)
                if current != before[name] and not accepted(name, write(name, before[name], 'periodic-restore')):
                    raise RuntimeError('restore setter rejected ' + name)
            except Exception as exc:
                failures.append(dict(preference=name, type=type(exc).__name__, message=str(exc)))
        try:
            evidence['after'] = snapshot('periodic-restored')
            if evidence['after'] != before:
                raise RuntimeError('complete STEP preference restore differs')
        except Exception as exc:
            failures.append(dict(type=type(exc).__name__, message=str(exc)))
        evidence['restored'] = not failures
        if failures:
            result['ok'] = False
            result['preference_restore_errors'] = failures
        try:
            verify_context()
        except Exception as exc:
            if first is None and not result.get('error') and not failures:
                raise
            result.setdefault('warnings', []).append(dict(code='step-context-check-failed', message=str(exc)))
        if failures and first is None and not result.get('error'):
            raise StepExportError('StepPreferenceRestoreFailed', 'STEP restore failed; output must not be published')
