"""Read existing failed probe JSON only. Does not collect or invent historical Win32 data."""
import argparse
import hashlib
import json
from pathlib import Path

SOURCE='MarkingJig.REND.SLDASM'


def summarize(root):
    def read(name):return json.loads((root/name).read_text(encoding='utf-8-sig'))
    report=read('native-output/report.json');after=read('vm-copy-OS-postcheck.stdout')
    first=report['source_files_before'][SOURCE];last=after['files'][SOURCE]
    channels=('path_before','handle_before','handle_after','path_after')
    changes={channel:{key:dict(before=first[channel].get(key),after=last[channel].get(key))
                     for key in sorted(set(first[channel])|set(last[channel])) if first[channel].get(key)!=last[channel].get(key)}
             for channel in channels}
    same_hash=first['sha256']==last['sha256']
    return dict(schema='swcli.existing-probe-python-file-channels.v1',source=SOURCE,source_sha256=first['sha256'],
        file_content_hash_equal=same_hash,changes=changes,
        path_ctime_equals_birthtime=all(row[channel]['st_ctime_ns']==row[channel]['st_birthtime_ns']
                                     for row in (first,last) for channel in ('path_before','path_after')),
        python_held_ctime_changed=first['handle_before']['st_ctime_ns']!=last['handle_before']['st_ctime_ns'],
        historical_win32_basic_standard_fileid_available=False,
        content_write_inferred=False,cause_inferred=False,
        primary_failure=report['failure'],open_errors=report['cases'][0]['open_errors'],open_warnings=report['cases'][0]['open_warnings'],
        application_or_CAD_calls=0,old_probe_success=False,source_records=dict(before=first,after=last),
        input_sha256={name:hashlib.sha256((root/name).read_bytes()).hexdigest()
                      for name in ('native-output/report.json','vm-copy-OS-postcheck.stdout')},
        limits=['Python observations are from distinct phases/handles, not an atomic system snapshot.',
                'CPython source explains possible field meanings, not why a specific metadata timestamp changed.',
                'No fabricated historical Win32 times, no tolerance/normalization and no source/CAS policy change.'])


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('evidence',type=Path);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    with args.output.open('x',encoding='utf-8') as f:json.dump(summarize(args.evidence),f,indent=2);f.write('\n')
