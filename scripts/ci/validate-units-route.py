"""Reject ambiguous or wrong-ref units dispatches before private native setup."""
import json
import os

UNITS_REF='refs/heads/codex/docprops-units-expanded'


def validate_route(*,event,ref,native_full,units_calibration,units_public_acceptance,units_write_calibration=False):
    if any(type(v) is not bool for v in (native_full,units_calibration,units_public_acceptance,units_write_calibration)):
        raise ValueError('native route switches must be booleans')
    if event!='workflow_dispatch':
        if units_calibration or units_public_acceptance or units_write_calibration:
            raise ValueError('units profiles require workflow_dispatch')
        return 'default'
    if native_full and (units_calibration or units_public_acceptance or units_write_calibration):
        raise ValueError('native_full and targeted units profiles are mutually exclusive')
    if units_write_calibration and not units_calibration:
        raise ValueError('write diagnostics require units_calibration')
    if units_public_acceptance and not units_calibration:
        raise ValueError('units_public_acceptance requires units_calibration')
    if (units_calibration or units_public_acceptance or units_write_calibration) and ref!=UNITS_REF:
        raise ValueError('units profiles require their exact branch ref')
    if units_write_calibration:return 'units-write-public' if units_public_acceptance else 'units-write-diagnostic'
    return 'units-public' if units_public_acceptance else 'units-read-cas' if units_calibration else 'full' if native_full else 'portable'


def main():
    route=validate_route(event=os.environ['ROUTE_EVENT'],ref=os.environ['ROUTE_REF'],
        native_full=json.loads(os.environ['ROUTE_NATIVE_FULL']),
        units_calibration=json.loads(os.environ['ROUTE_UNITS_CALIBRATION']),
        units_public_acceptance=json.loads(os.environ['ROUTE_UNITS_PUBLIC']),
        units_write_calibration=json.loads(os.environ.get('ROUTE_UNITS_WRITE','false')))
    if route=='units-write-public':
        # Fail before any private native setup when no independently reviewed
        # production domain exists. Diagnostic success never populates it.
        import sys
        from pathlib import Path
        sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'src'))
        from swcli.document_unit_profile import CALIBRATED_UNIT_WRITES, CALIBRATED_UNIT_SYSTEM_RESULTS
        if not CALIBRATED_UNIT_WRITES or not CALIBRATED_UNIT_SYSTEM_RESULTS:
            raise ValueError('public unit writes require manually reviewed finite domains and system results')
    print('Validated native route: '+route)

if __name__=='__main__':main()
