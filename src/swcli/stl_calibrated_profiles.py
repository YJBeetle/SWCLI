"""Exact STL tuples qualified by retained native output and independent audit.

This is bounded internal-native qualification used to authorize the separate
public gate. It is not full/release acceptance. No arbitrary interpolation,
rounding, clamping, model normalization, or unqualified host is permitted.
"""

from __future__ import annotations
from typing import Dict, TYPE_CHECKING
if TYPE_CHECKING:
    from .sdk.models import DocumentExportParametersStlOptions

QUALIFICATION: Dict[str, str] = {'dist_zip_sha256': 'd0b4d09f305787977e578af085043a49a2bae4baddd96c502ef6fe60312b390f',
 'internal_run': 'https://github.com/YJBeetle/SWCLI/actions/runs/42272270166',
 'native_source_sha256': '07c0450bc74de4af0677f5e3210b4a06801dd764b3b8151e9f6dcb9998aa997a',
 'original_zip_sha256': '900b434d209730dc351377e589512be1743953638e949d0e090431054a487617',
 'report_sha256': '7a78f8e642e771e1737016ec0ff210c0f46b15eba1f4091750e9a5f9ff5989d3',
 'scope': 'native-windows-github-exclusive-parts-stl',
 'solidworks_revision': '33.5.0',
 'source_commit': 'd8df4a874cc0c8460cf8615964420e7e9c20ff7b',
 'trace_sha256': '754a2fe537a836d751f0377d308cff087d9be81b4ea3ceb118b1c69d31296099'}

NATIVE_ENUMS: Dict[str, int] = {'swCM': 1,
 'swExportStlUnits': 211,
 'swFEET': 4,
 'swINCHES': 3,
 'swMETER': 2,
 'swMM': 0,
 'swSTLAngleTolerance': 3,
 'swSTLBinaryFormat': 69,
 'swSTLComponentsIntoOneFile': 72,
 'swSTLDeviation': 2,
 'swSTLPreview': 191,
 'swSTLQuality': 78,
 'swSTLQuality_Custom': 3,
 'swSTLShowInfoOnSave': 70}

PROFILES: Dict[str, DocumentExportParametersStlOptions] = {'angle-fine': {'angle_degrees': 10,
                'deviation_mm': 0.5335936864527374,
                'encoding': 'binary',
                'unit': 'mm'},
 'ascii-inch': {'angle_degrees': 10,
                'deviation_mm': 0.015392125570752039,
                'encoding': 'ascii',
                'unit': 'inch'},
 'binary-meter': {'angle_degrees': 10,
                  'deviation_mm': 0.015392125570752039,
                  'encoding': 'binary',
                  'unit': 'm'},
 'coarse': {'angle_degrees': 30,
            'deviation_mm': 0.5335936864527374,
            'encoding': 'binary',
            'unit': 'mm'},
 'deviation-fine': {'angle_degrees': 30,
                    'deviation_mm': 0.015392125570752039,
                    'encoding': 'binary',
                    'unit': 'mm'},
 'fine': {'angle_degrees': 10,
          'deviation_mm': 0.015392125570752039,
          'encoding': 'binary',
          'unit': 'mm'}}
