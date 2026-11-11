"""Fixed-list, data-only GLB exporter inventory. No CAD, target DLL loading or search."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import struct
import subprocess
import sys

INSTALL_ROOT = Path(r'C:\Program Files\SOLIDWORKS Corp\SOLIDWORKS')
SYSTEM_DIRS = (Path(r'C:\Windows\System32'), Path(r'C:\Windows\SysWOW64'))
POWERSHELL = Path(r'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe')
REQUIRED_FILES = ('sldgltfu.dll', 'spiop/files/code/bin/SPAXGLTFBase.dll',
                  'spiop/files/code/bin/SPAXGLTFVisualization.dll', 'spiop/files/code/bin/VisGltf.dll')
BACKGROUND_FILES = ('SWXRExporter.dll', 'SWXRExporter.tlb')
MAX_FILE = 256 * 1024 * 1024
MAX_IMPORTS = 256
MAX_CERT_BYTES = 1024 * 1024
MAX_JSON = 16 * 1024 * 1024
REPARSE = 0x400
SOURCE = dict(kind='coordinator-approved fixed list; original CI MSI excerpt, not runtime discovery',
              run_id=42405530053, installer_zip_sha256='eced0a0b91ec041025237d28aedc8cbe332b50f6df645ce2769355e9095c8055',
              original_lines=[81281,102990,102993,105287,17073,17074])


def checked(condition, message):
    if not condition:
        raise RuntimeError(message)


def error_record(error):
    return dict(type=type(error).__name__, message=str(error))


def stat_record(value):
    return dict(device=value.st_dev, file_id=value.st_ino, mode=value.st_mode, size=value.st_size,
                mtime_ns=value.st_mtime_ns, ctime_ns=value.st_ctime_ns,
                file_attributes=getattr(value, 'st_file_attributes', 0))


RAW_STAT_FIELDS = ('st_mode', 'st_ino', 'st_dev', 'st_nlink', 'st_uid', 'st_gid', 'st_size',
                   'st_atime', 'st_mtime', 'st_ctime', 'st_atime_ns', 'st_mtime_ns', 'st_ctime_ns',
                   'st_birthtime', 'st_birthtime_ns', 'st_rdev', 'st_blksize', 'st_blocks',
                   'st_file_attributes', 'st_reparse_tag', 'st_flags', 'st_gen', 'st_fstype')


def observed_stat(value):
    # Diagnostics never replace an existing guard error with a metadata error.
    raw, unavailable, errors = {}, [], {}
    for name in RAW_STAT_FIELDS:
        try:
            item = getattr(value, name)
            raw[name] = item if type(item) in (int, float, str, bool, type(None)) else dict(unserialized_type=type(item).__name__)
        except AttributeError:
            unavailable.append(name)
        except Exception as error:
            errors[name] = error_record(error)
    try:
        comparison = channel_stat(value)
    except Exception as error:
        comparison = dict(observation_error=error_record(error))
    return dict(comparison_fields=comparison, raw_fields=raw, unavailable_fields=unavailable, read_errors=errors)


def observe(record, stage, **values):
    if record is not None:
        record.update(stage=stage, **values)


def observe_comparison(record, name, before, after):
    if record is not None:
        left, right = record[before]['comparison_fields'], record[after]['comparison_fields']
        record.setdefault('comparison_differences', {})[name] = {
            key: {before:left.get(key), after:right.get(key)}
            for key in sorted(set(left) | set(right)) if left.get(key) != right.get(key)}


def regular(value):
    return stat.S_ISREG(value.st_mode) and not (getattr(value, 'st_file_attributes', 0) & REPARSE)


def parent_identity(path, *, observations=None):
    result = []
    for parent in reversed(path.parents):
        value = os.stat(parent, follow_symlinks=False)
        if observations is not None:
            observations.append(dict(path=str(parent), stat=observed_stat(value)))
        checked(stat.S_ISDIR(value.st_mode) and not (getattr(value, 'st_file_attributes', 0) & REPARSE),
                'parent is not a plain non-reparse directory: ' + str(parent))
        checked(value.st_dev and value.st_ino, 'parent identity is unavailable: ' + str(parent))
        result.append((str(parent), value.st_dev, value.st_ino, value.st_mode, getattr(value, 'st_file_attributes', 0)))
    return result


def probe(path):
    """One exact path only; absence is not a runtime dependency verdict."""
    try:
        parent_identity(path)
        value = os.stat(path, follow_symlinks=False)
        checked(regular(value), 'not a regular non-reparse file')
        return dict(path=str(path), status='present_regular_non_reparse', stat=stat_record(value))
    except FileNotFoundError:
        return dict(path=str(path), status='not_present_at_checked_path')
    except Exception as error:
        return dict(path=str(path), status='unknown', error=error_record(error))


def runtime_identity():
    return dict(os_name=os.name, platform=sys.platform, implementation=sys.implementation.name,
                version_info=list(sys.version_info), version=sys.version, word_bits=struct.calcsize('P') * 8)


def channel_stat(value):
    # Same-channel comparisons also retain birthtime when that channel exposes it.
    return dict(stat_record(value), birthtime_ns=getattr(value, 'st_birthtime_ns', None),
                link_count=getattr(value, 'st_nlink', None), reparse_tag=getattr(value, 'st_reparse_tag', None))


def path_handle_match(by_path, by_handle, *, observation=None):
    left, right = channel_stat(by_path), channel_stat(by_handle)
    runtime = runtime_identity()
    differences = [key for key in left if left[key] != right[key]]
    if not differences:
        decision = dict(rule='strict_equal', accepted=True, runtime=runtime, differing_fields=[])
    else:
        # Proven only for the inspected final, 64-bit Windows CPython 3.14.7.
        requirements = dict(
            runtime=(runtime['os_name'] == 'nt' and runtime['platform'] == 'win32'
                     and runtime['implementation'] == 'cpython' and runtime['version_info'] == [3,14,7,'final',0]
                     and runtime['word_bits'] == 64),
            ctime_is_only_difference=differences == ['ctime_ns'],
            exact_integer_fields=all(type(value) is int for value in (*left.values(), *right.values())),
            positive_equal_birthtime=(type(left['birthtime_ns']) is int and left['birthtime_ns'] > 0
                                     and left['birthtime_ns'] == right['birthtime_ns']),
            path_ctime_is_birthtime=left['ctime_ns'] == left['birthtime_ns'],
            positive_identity=(type(left['device']) is int and left['device'] > 0
                               and type(left['file_id']) is int and left['file_id'] > 0),
            raw_attributes_available=all(type(getattr(value, 'st_file_attributes', None)) is int for value in (by_path,by_handle)),
            links_equal=all(type(getattr(value, 'st_nlink', None)) is int for value in (by_path,by_handle))
                        and getattr(by_path,'st_nlink',None) == getattr(by_handle,'st_nlink',None)
                        and getattr(by_path,'st_nlink',0) > 0,
            reparse_tags_zero=all(type(getattr(value,'st_reparse_tag',None)) is int
                                  and value.st_reparse_tag == 0 for value in (by_path,by_handle)),
            regular_non_reparse=regular(by_path) and regular(by_handle))
        accepted = all(requirements.values())
        decision = dict(rule='win_cpython_3_14_7_path_creation_vs_handle_change_time' if accepted else 'strict_refusal',
                        candidate_rule='win_cpython_3_14_7_path_creation_vs_handle_change_time',
                        accepted=accepted, runtime=runtime, differing_fields=differences,
                        requirements=requirements, path_ctime_ns=left['ctime_ns'], handle_ctime_ns=right['ctime_ns'],
                        path_birthtime_ns=left['birthtime_ns'], handle_birthtime_ns=right['birthtime_ns'])
    if observation is not None:
        observation['path_handle_comparison'] = decision
    return decision['accepted']


def stable_read(path, *, observation=None):
    """Keep original guards; retain each obtained value before its check."""
    if observation is not None:
        observation.update(path=str(path), status='started', parents_before=[], parents_after=[])
    try:
        observe(observation, 'parents_before')
        parents = parent_identity(path, observations=observation['parents_before'] if observation is not None else None)
        observe(observation, 'stat_before')
        first = os.stat(path, follow_symlinks=False)
        observe(observation, 'before_checks', before=observed_stat(first) if observation is not None else None)
        checked(regular(first), 'input is not regular/non-reparse: ' + str(path))
        checked(first.st_dev and first.st_ino, 'input file identity is unavailable: ' + str(path))
        checked(0 <= first.st_size <= MAX_FILE, 'input exceeds byte bound')
        flags = os.O_RDONLY | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0)
        observe(observation, 'open')
        descriptor = os.open(path, flags)
        try:
            observe(observation, 'fstat_opened')
            opened = os.fstat(descriptor)
            observe(observation, 'opened_check', opened=observed_stat(opened) if observation is not None else None)
            observe_comparison(observation, 'opened_vs_before', 'before', 'opened')
            checked(path_handle_match(first, opened, observation=observation), 'input changed between path stat and open')
            observe(observation, 'read')
            with os.fdopen(descriptor, 'rb', closefd=False) as stream:
                data = stream.read(MAX_FILE + 1)
            observe(observation, 'read_size_check', bytes_read=len(data))
            checked(len(data) == first.st_size and len(data) <= MAX_FILE, 'input size changed during read')
            observe(observation, 'fstat_after')
            after_handle = os.fstat(descriptor)
            observe(observation, 'after_handle_check', after_handle=observed_stat(after_handle) if observation is not None else None)
            observe_comparison(observation, 'after_handle_vs_opened', 'opened', 'after_handle')
            checked(channel_stat(after_handle) == channel_stat(opened), 'input changed while descriptor was open')
            observe(observation, 'stat_after')
            after = os.stat(path, follow_symlinks=False)
            observe(observation, 'after_path_check', after_path=observed_stat(after) if observation is not None else None)
            observe_comparison(observation, 'after_path_vs_before', 'before', 'after_path')
            checked(regular(after) and channel_stat(after) == channel_stat(first), 'input path identity changed during read')
            observe(observation, 'parents_after')
            checked(parent_identity(path, observations=observation['parents_after'] if observation is not None else None) == parents,
                    'input parent identity changed during read')
        finally:
            os.close(descriptor)
            if observation is not None: observation['descriptor_closed'] = True
        observe(observation, 'hash')
        result = dict(path=str(path), stat=stat_record(first), birthtime_ns=getattr(first, 'st_birthtime_ns', None),
                      handle_stat=channel_stat(opened), sha256=hashlib.sha256(data).hexdigest())
        observe(observation, 'complete', status='complete', sha256=result['sha256'])
        return result, data
    except Exception as error:
        if observation is not None:
            observation.update(status='failed', failed_stage=observation.get('stage'), error=error_record(error))
        raise


def recorded_read(path, owner, key):
    # The object is attached before any I/O, so the caller's finally can persist it.
    observation = owner.setdefault('stable_reads', {}).setdefault(key, {})
    return stable_read(path, observation=observation)


class PE:
    """Bounded bytes parser; never map an image or invoke the Windows loader."""
    def __init__(self, data):
        self.data = data
        checked(data[:2] == b'MZ', 'DOS header missing')
        pe = self.u32(0x3c)
        checked(self.take(pe, 4) == b'PE\0\0', 'PE signature missing')
        self.machine, count = self.unpack('<HH', pe + 4)
        checked(0 < count <= 96, 'PE section count exceeds bound')
        optional_size = self.unpack('<H', pe + 20)[0]
        optional = pe + 24
        magic = self.unpack('<H', optional)[0]
        checked(magic in (0x10b, 0x20b), 'PE optional header kind is unknown')
        directory_offset, count_offset = (96, 92) if magic == 0x10b else (112, 108)
        checked(optional_size >= directory_offset, 'truncated optional header')
        self.image_base = self.unpack('<I' if magic == 0x10b else '<Q', optional + (28 if magic == 0x10b else 24))[0]
        self.header_size = self.u32(optional + 60)
        number = self.u32(optional + count_offset)
        checked(number <= 16 and directory_offset + number * 8 <= optional_size, 'invalid data directories')
        self.directories = [self.unpack('<II', optional + directory_offset + i * 8) for i in range(number)]
        self.sections = []
        for index in range(count):
            entry = optional + optional_size + index * 40
            self.take(entry, 40)
            virtual_size, rva, raw_size, raw = self.unpack('<IIII', entry + 8)
            checked(raw + raw_size <= len(data), 'section raw bytes exceed file')
            self.sections.append((rva, virtual_size, raw, raw_size))
        self.kind = 'PE32' if magic == 0x10b else 'PE32+'

    def take(self, offset, size):
        checked(type(offset) is int and 0 <= offset <= len(self.data) and 0 <= size <= len(self.data) - offset,
                'PE range exceeds file')
        return self.data[offset:offset + size]

    def unpack(self, pattern, offset):
        return struct.unpack(pattern, self.take(offset, struct.calcsize(pattern)))

    def u32(self, offset): return self.unpack('<I', offset)[0]

    def directory(self, index):
        return self.directories[index] if index < len(self.directories) else (0, 0)

    def rva(self, address, size):
        matches = []
        if address < self.header_size and address + size <= self.header_size:
            matches.append(address)
        for start, _, raw, raw_size in self.sections:
            if start <= address and address + size <= start + raw_size:
                matches.append(raw + address - start)
        checked(len(matches) == 1, 'RVA is unmapped or ambiguous in raw file bytes')
        self.take(matches[0], size)
        return matches[0]

    def library_name(self, address):
        # Read each byte through RVA mapping: never cross a raw-section boundary.
        value = bytearray()
        for index in range(256):
            byte = self.take(self.rva(address + index, 1), 1)[0]
            if byte == 0:
                name = value.decode('ascii')
                checked(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.+\-]*\.dll', name, re.I) is not None
                        and '..' not in name, 'unsafe or unsupported import library name')
                return name
            value.append(byte)
        raise RuntimeError('import library name exceeds bound')

    def imports(self):
        found = []
        for kind, directory_index, width in (('normal', 1, 20), ('delay', 13, 32)):
            address, length = self.directory(directory_index)
            if not address and not length:
                continue
            checked(address and width <= length <= MAX_FILE, 'import directory bound is invalid')
            terminated = False
            for offset in range(0, min(length // width, MAX_IMPORTS + 1) * width, width):
                fields = self.unpack('<' + 'I' * (width // 4), self.rva(address + offset, width))
                if not any(fields): terminated = True; break
                checked(len(found) < MAX_IMPORTS, 'import count exceeds bound')
                name_rva = fields[3] if kind == 'normal' else fields[1]
                if kind == 'delay':
                    checked(fields[0] in (0, 1), 'unknown delay import attributes')
                    if fields[0] == 0: name_rva -= self.image_base
                name = self.library_name(name_rva)
                found.append(dict(kind=kind, name=name, api_set_contract=name.lower().startswith(('api-ms-', 'ext-ms-'))))
            checked(terminated, 'unterminated import directory')
        return found

    def certificates(self):
        # IMAGE_DIRECTORY_ENTRY_SECURITY uses file offsets, not RVAs.
        offset, length = self.directory(4)
        if not offset and not length:
            return []
        checked(offset and offset % 8 == 0 and 8 <= length <= MAX_CERT_BYTES, 'certificate table bound/alignment is invalid')
        checked(offset >= max([self.header_size] + [raw + size for _, _, raw, size in self.sections]), 'certificate overlaps image bytes')
        self.take(offset, length)
        rows = []; end = offset + length
        while offset < end:
            checked(len(rows) < 16 and offset + 8 <= end, 'certificate count/table boundary is invalid')
            size, revision, kind = self.unpack('<IHH', offset)
            checked(8 <= size <= end - offset, 'invalid WIN_CERTIFICATE length')
            content = self.take(offset + 8, size - 8)
            rows.append(dict(revision=revision, certificate_type=kind, bytes=size,
                             sha256=hashlib.sha256(content).hexdigest(),
                             pkcs7_base64=base64.b64encode(content).decode('ascii') if revision == 0x200 and kind == 2 else None))
            offset += (size + 7) & ~7
        checked(offset == end, 'certificate alignment exceeds table')
        return rows


def dependency_locations(owner, name):
    checked(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.+\-]*\.dll', name, re.I) is not None and '..' not in name,
            'dependency basename is unsafe')
    result = []
    for directory in (owner.parent, INSTALL_ROOT, *SYSTEM_DIRS):
        candidate = directory / name
        if candidate not in result: result.append(candidate)
    return result


def dependencies(owner, imports):
    rows = []
    for item in imports:
        checks = []
        for candidate in dependency_locations(owner, item['name']):
            before, after = probe(candidate), probe(candidate)
            checks.append(before if before == after else dict(path=str(candidate), status='unknown', reason='path changed during presence check'))
        rows.append(dict(**item, checked_paths=checks,
                         static_path_match=any(c['status'] == 'present_regular_non_reparse' for c in checks),
                         runtime_resolution='unknown_not_executed',
                         not_found_is_not_runtime_missing=True))
    return rows


def collect(output, report, *, runner=subprocess.run):
    report.update(execution_kind='installed-glb-exporter-fixed-files-only-zero-CAD', contract=dict(kind='fixed-list zero-CAD read-only metadata', model_calls=0, cad_activations=0,
                                target_dll_loads=0, dependency_search_recursive=False, signature_verification=False,
                                runtime_dependency_acceptance=False),
                  fixed_list_source=SOURCE, install_root=str(INSTALL_ROOT),
                  system_lookup_dirs=[str(path) for path in SYSTEM_DIRS], files=[])
    checked(POWERSHELL.is_file(), 'fixed Windows PowerShell executable is unavailable; no install/fallback')
    parent_identity(POWERSHELL)
    checked(regular(os.stat(POWERSHELL, follow_symlinks=False)), 'fixed PowerShell executable is reparse/non-regular')
    report['collector_before'], _ = recorded_read(Path(__file__), report, 'collector_before')
    snapshots = {}; request = dict(install_root=str(INSTALL_ROOT), files=[])
    for relative in (*REQUIRED_FILES, *BACKGROUND_FILES):
        path = INSTALL_ROOT / relative
        row = dict(relative_path=relative, required=relative in REQUIRED_FILES, presence_before=probe(path))
        report['files'].append(row)
        if row['presence_before']['status'] == 'not_present_at_checked_path': continue
        checked(row['presence_before']['status'] == 'present_regular_non_reparse', 'unsafe/unreadable fixed input: ' + str(path))
        row['before'], data = recorded_read(path, row, 'before'); snapshots[relative] = row['before']
        certificates = []
        if path.suffix.lower() == '.dll':
            try:
                pe = PE(data)
                row['pe'] = dict(status='parsed', machine=pe.machine, machine_name={0x14c:'I386',0x8664:'AMD64',0xaa64:'ARM64'}.get(pe.machine,'unknown'), kind=pe.kind)
            except Exception as error:
                pe = None
                row['pe'] = dict(status='unknown', error=error_record(error))
            if relative in REQUIRED_FILES:
                try:
                    checked(pe is not None, 'PE header is unavailable')
                    row['static_imports'] = dict(status='parsed', libraries=pe.imports())
                    row['dependency_locations'] = dependencies(path, row['static_imports']['libraries'])
                except Exception as error:
                    row['static_imports'] = dict(status='unknown', error=error_record(error))
                    row['dependency_locations'] = []
            else:
                row['static_imports'] = dict(status='not_collected_background_file')
            try:
                checked(pe is not None, 'PE header is unavailable')
                certificates = pe.certificates()
                row['signature_table'] = dict(status='embedded_entries_present' if certificates else 'no_embedded_entries',
                                              entries=[{k:v for k,v in item.items() if k != 'pkcs7_base64'} for item in certificates],
                                              cryptographic_validity='unknown_not_verified', catalog_signature='unknown_not_queried')
            except Exception as error:
                row['signature_table'] = dict(status='unknown', error=error_record(error),
                                              cryptographic_validity='unknown_not_verified', catalog_signature='unknown_not_queried')
        else:
            row['pe'] = dict(status='not_applicable_standalone_tlb')
            row['static_imports'] = dict(status='not_collected_background_file')
            row['signature_table'] = dict(status='not_applicable_PE_table', catalog_signature='unknown_not_queried')
        request['files'].append(dict(relative_path=relative, expected_sha256=row['before']['sha256'],
                                     certificates=[item['pkcs7_base64'] for item in certificates if item['pkcs7_base64'] is not None]))
    helper = Path(__file__).with_name('inspect-installed-glb-exporter-metadata.ps1')
    report['helper_before'], _ = recorded_read(helper, report, 'helper_before')
    request_path, metadata_path = output/'metadata-request.json', output/'metadata.json'
    encoded = json.dumps(request,ensure_ascii=False,indent=2).encode('utf-8')
    checked(len(encoded) <= MAX_JSON, 'metadata request exceeds byte bound')
    request_path.write_bytes(encoded)
    report['request_before'], _ = recorded_read(request_path, report, 'request_before')
    first_error = None
    report['metadata_attempted'] = True
    try:
        result = runner([str(POWERSHELL), '-NoLogo', '-NoProfile', '-NonInteractive', '-File', str(helper),
                         '-RequestPath', str(request_path), '-OutputPath', str(metadata_path)],
                        capture_output=True, timeout=120, check=False)
        (output/'metadata.stdout.log').write_bytes(result.stdout)
        (output/'metadata.stderr.log').write_bytes(result.stderr)
        report['metadata_exit_code'] = result.returncode
        if metadata_path.is_file():
            checked(metadata_path.stat().st_size <= MAX_JSON, 'metadata response exceeds byte bound')
            report['metadata_response_file'], response = recorded_read(metadata_path, report, 'metadata_response_file')
            checked(len(response) <= MAX_JSON, 'metadata response exceeds byte bound')
            report['metadata'] = json.loads(response.decode('utf-8-sig'))
        checked(result.returncode == 0 and report.get('metadata',{}).get('success') is True, 'metadata helper failed; no retry/fallback')
        metadata = report['metadata']
        checked(metadata.get('kind') == 'data-only-file-version-and-embedded-CMS-metadata'
                and type(metadata.get('target_dll_loads')) is int and metadata['target_dll_loads'] == 0
                and type(metadata.get('cad_activations')) is int and metadata['cad_activations'] == 0
                and metadata.get('network_verification') is False and metadata.get('signature_verified') is False,
                'metadata helper zero-CAD/offline contract differs')
        observed = metadata['files']
        checked(type(observed) is list, 'metadata file list is invalid')
        checked(len(observed) == len(request['files']) and {item['relative_path'] for item in observed} == set(snapshots),
                'metadata fixed file set differs')
        for item in observed:
            checked(item['sha256_before'] == item['sha256_after'] == snapshots[item['relative_path']]['sha256'], 'metadata read different input bytes')
    except Exception as error:
        first_error = error
        if isinstance(error, subprocess.TimeoutExpired):
            (output/'metadata.stdout.log').write_bytes(error.stdout or b'')
            (output/'metadata.stderr.log').write_bytes(error.stderr or b'')
    finally:
        try:
            report['collector_after'], _ = recorded_read(Path(__file__), report, 'collector_after')
            checked(report['collector_after'] == report['collector_before'], 'collector script changed')
            report['request_after'], _ = recorded_read(request_path, report, 'request_after')
            checked(report['request_after'] == report['request_before'], 'metadata request changed')
            report['helper_after'], _ = recorded_read(helper, report, 'helper_after')
            checked(report['helper_after'] == report['helper_before'], 'metadata helper file changed')
            for row in report['files']:
                path = INSTALL_ROOT / row['relative_path']
                row['presence_after'] = probe(path)
                checked(row['presence_after'] == row['presence_before'], 'fixed source presence/stat changed')
                if row['relative_path'] in snapshots:
                    row['after'], _ = recorded_read(path, row, 'after')
                    checked(row['after'] == row['before'], 'fixed source stat/hash changed')
        except Exception as error:
            report['postcheck_error'] = error_record(error)
            if first_error is None: first_error = error
    if first_error is not None: raise first_error
    report['required_files_all_present'] = all(row['presence_before']['status'] == 'present_regular_non_reparse'
                                              for row in report['files'] if row['required'])
    report['all_existing_fixed_sources_stat_and_hash_unchanged'] = True
    report['collection_completed'] = True
    report['exporter_runtime_accepted'] = False


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,required=True)
    args = parser.parse_args(argv)
    checked(os.name == 'nt' and struct.calcsize('P') == 8, 'native 64-bit Windows Python required; no redirected System32 or host fallback')
    checked(args.output_dir.is_absolute(), 'absolute new output directory required')
    checked(all(root != args.output_dir and root not in args.output_dir.parents for root in (INSTALL_ROOT,*SYSTEM_DIRS)), 'output cannot modify inspected locations')
    parent_identity(args.output_dir)
    args.output_dir.mkdir(exist_ok=False)
    report = dict(collection_completed=False, exporter_runtime_accepted=False)
    try:
        collect(args.output_dir,report)
    except Exception as error:
        report['first_error'] = error_record(error)
        return 1
    finally:
        (args.output_dir/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return 0


if __name__ == '__main__':sys.exit(main())
