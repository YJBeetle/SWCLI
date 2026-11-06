"""Reject ambiguous or wrong-ref units dispatches before private native setup."""
import json
import os

UNITS_REF='refs/heads/codex/docprops-units-expanded'


def validate_route(*,event,ref,native_full,units_calibration,units_public_acceptance):
    if any(type(v) is not bool for v in (native_full,units_calibration,units_public_acceptance)):
        raise ValueError('native route switches must be booleans')
    if event!='workflow_dispatch':
        if units_calibration or units_public_acceptance:
            raise ValueError('units profiles require workflow_dispatch')
        return 'default'
    if native_full and (units_calibration or units_public_acceptance):
        raise ValueError('native_full and targeted units profiles are mutually exclusive')
    if units_public_acceptance and not units_calibration:
        raise ValueError('units_public_acceptance requires units_calibration')
    if (units_calibration or units_public_acceptance) and ref!=UNITS_REF:
        raise ValueError('units profiles require their exact branch ref')
    return 'units-public' if units_public_acceptance else 'units-read-cas' if units_calibration else 'full' if native_full else 'portable'


def main():
    route=validate_route(event=os.environ['ROUTE_EVENT'],ref=os.environ['ROUTE_REF'],
        native_full=json.loads(os.environ['ROUTE_NATIVE_FULL']),
        units_calibration=json.loads(os.environ['ROUTE_UNITS_CALIBRATION']),
        units_public_acceptance=json.loads(os.environ['ROUTE_UNITS_PUBLIC']))
    print('Validated native route: '+route)

if __name__=='__main__':main()
