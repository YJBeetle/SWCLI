"""Offline source/ZIP/path refusal tests; never imports native CAD modules."""
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path, PureWindowsPath
import tempfile
import unittest
from unittest import mock
import zipfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('step_original_import', ROOT / 'scripts/ci/prepare-step-import-original.py')
original = importlib.util.module_from_spec(spec)
spec.loader.exec_module(original)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def run(head, identifier, source=False):
    result = dict(id=identifier, event='workflow_dispatch', path=original.WORKFLOW,
                  workflow_id=original.WORKFLOW_ID, head_sha=head, head_branch=original.BRANCH,
                  run_attempt=1, repository=dict(id=original.REPOSITORY_ID, full_name=original.REPOSITORY),
                  head_repository=dict(id=original.REPOSITORY_ID, full_name=original.REPOSITORY))
    if source:
        result.update(status='completed', conclusion='failure')
    return result


def fixture():
    entries, rows, expected = {}, [], []
    for name, _, protocol, geometry, surface in original.OUTPUTS:
        raw = ('immutable fixture ' + name).encode()
        expected.append((name, sha(raw), protocol, geometry, surface))
        rows.append(dict(path=str(original.ORIGINAL_DIRECTORY / name), sha256=sha(raw), protocol=protocol,
                         geometry=geometry, surface=surface))
        entries['swcli-native-smoke/step-public/' + name] = raw
    entries[original.REPORT_MEMBER] = json.dumps(dict(success=True, source_commit=original.SOURCE_HEAD, outputs=rows)).encode()
    return entries, tuple(expected), rows


def archive(entries):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w') as out:
        for name, raw in entries.items():
            out.writestr(name, raw)
    return stream.getvalue()


class StepOriginalImportTests(unittest.TestCase):
    def test_exact_context_rejects_unreviewed_refs_mixed_profiles_and_reruns(self):
        with tempfile.TemporaryDirectory() as directory:
            event = Path(directory).resolve() / 'event.json'
            inputs = dict(native_step_import_diagnostic='true', native_step_import_head='a'*40,
                          native_full='false', native_step_targeted='false', native_step_public_targeted='false')
            event.write_text(json.dumps(dict(inputs=inputs)))
            env = dict(GITHUB_REPOSITORY=original.REPOSITORY, GITHUB_REPOSITORY_ID=str(original.REPOSITORY_ID),
                       GITHUB_EVENT_NAME='workflow_dispatch', GITHUB_REF=original.REF, GITHUB_SHA='a'*40,
                       DIAGNOSTIC_WORKFLOW_SHA='a'*40, GITHUB_WORKFLOW_REF=original.REPOSITORY+'/'+original.WORKFLOW+'@'+original.REF,
                       GITHUB_RUN_ATTEMPT='1', GITHUB_RUN_ID='42', RUNNER_TEMP=str(original.ORIGINAL_TEMP), GITHUB_EVENT_PATH=str(event))
            self.assertFalse(original.current_context(env, 'a'*40, 'a'*40)['production_public_acceptance'])
            for key, value in (('GITHUB_REPOSITORY', 'fork/SWCLI'), ('GITHUB_EVENT_NAME', 'push'),
                               ('GITHUB_REF', 'refs/heads/main'), ('GITHUB_SHA', 'b'*40),
                               ('DIAGNOSTIC_WORKFLOW_SHA', 'b'*40), ('GITHUB_RUN_ATTEMPT', '2'),
                               ('RUNNER_TEMP', r'C:\other'), ('GH_HOST', 'untrusted.example')):
                with self.subTest(key=key), self.assertRaises(RuntimeError):
                    original.current_context(dict(env, **{key: value}), 'a'*40, 'a'*40)
            for key in ('native_full', 'native_step_targeted', 'native_step_public_targeted'):
                event.write_text(json.dumps(dict(inputs=dict(inputs, **{key: 'true'}))))
                with self.subTest(key=key), self.assertRaisesRegex(RuntimeError, 'exclusive'):
                    original.current_context(env, 'a'*40, 'a'*40)
            event.write_text(json.dumps(dict(inputs=inputs)))
            with self.assertRaises(RuntimeError):original.current_context(env, 'a'*39, 'a'*40)
            with self.assertRaises(RuntimeError):original.current_context(env, 'a'*40, 'b'*40)

    def test_run_and_artifact_identity_include_source_event_repository_attempt_digest(self):
        source = run(original.SOURCE_HEAD, original.SOURCE_RUN, True)
        original.validate_run(source, run_id=original.SOURCE_RUN, head=original.SOURCE_HEAD, source=True)
        for key, value in (('event', 'pull_request'), ('head_sha', 'b'*40), ('head_branch', 'main'),
                           ('workflow_id', 99), ('run_attempt', 2), ('status', 'in_progress'), ('conclusion', 'success')):
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                original.validate_run(dict(source, **{key: value}), run_id=original.SOURCE_RUN, head=original.SOURCE_HEAD, source=True)
        artifact = dict(id=original.ARTIFACT_ID, name=original.ARTIFACT_NAME, expired=False, digest='sha256:'+original.ZIP_SHA256,
                        workflow_run=dict(id=original.SOURCE_RUN, head_sha=original.SOURCE_HEAD, head_branch=original.BRANCH,
                                          repository_id=original.REPOSITORY_ID, head_repository_id=original.REPOSITORY_ID))
        original.validate_artifact(artifact)
        for key, value in (('id', 99), ('name', 'other'), ('expired', True), ('digest', 'sha256:'+'b'*64)):
            with self.subTest(key=key), self.assertRaises(RuntimeError):original.validate_artifact(dict(artifact, **{key:value}))
        wrong=copy.deepcopy(artifact);wrong['workflow_run']['head_repository_id']=99
        with self.assertRaises(RuntimeError):original.validate_artifact(wrong)

    def test_all_eight_members_and_receipt_hashes_are_validated_before_restoration(self):
        entries, expected, rows = fixture()
        raw = archive(entries)
        with mock.patch.object(original, 'OUTPUTS', expected), mock.patch.object(original, 'ZIP_SHA256', sha(raw)):
            report, files = original.validate_zip(raw)
            self.assertEqual(len(files), 8)
            self.assertEqual(report, entries[original.REPORT_MEMBER])
            with self.assertRaisesRegex(RuntimeError, 'ZIP SHA256'):original.validate_zip(raw+b'change')
        changes = []
        changed=dict(entries);changed['swcli-native-smoke/step-public/'+expected[-1][0]]=b'tampered';changes.append(changed)
        changed=dict(entries);r=json.loads(changed[original.REPORT_MEMBER]);r['outputs'][0]['path']=r'C:\other\part.step'
        changed[original.REPORT_MEMBER]=json.dumps(r).encode();changes.append(changed)
        changed=dict(entries);del changed['swcli-native-smoke/step-public/'+expected[-1][0]];changes.append(changed)
        changed=dict(entries);changed['../escape']=b'bad';changes.append(changed)
        changed=dict(entries);r=json.loads(changed[original.REPORT_MEMBER]);r['source_commit']='b'*40
        changed[original.REPORT_MEMBER]=json.dumps(r).encode();changes.append(changed)
        for changed in changes:
            bad=archive(changed)
            with self.subTest(members=list(changed)[-1]), mock.patch.object(original,'OUTPUTS',expected), \
                    mock.patch.object(original,'ZIP_SHA256',sha(bad)), self.assertRaises((RuntimeError,KeyError)):
                original.validate_zip(bad)

    def test_restore_is_exclusive_and_validates_last_conflict_before_any_copy(self):
        entries, _, rows = fixture()
        files=[(row,entries['swcli-native-smoke/step-public/'+PureWindowsPath(row['path']).name]) for row in rows]
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve();target=lambda row:root/PureWindowsPath(row['path']).name
            target(rows[-1]).write_bytes(b'existing different work')
            with self.assertRaisesRegex(RuntimeError,'overwrite'):original.restore_files(files,target=target)
            self.assertEqual(len(list(root.iterdir())),1)
            self.assertEqual(target(rows[-1]).read_bytes(),b'existing different work')
            target(rows[-1]).write_bytes(files[-1][1])
            stamp=target(rows[-1]).stat().st_mtime_ns
            original.restore_files(files,target=target)
            self.assertEqual(target(rows[-1]).stat().st_mtime_ns,stamp)
            self.assertEqual(len(list(root.iterdir())),8)
            original.verify_files(files,target=target)
            target(rows[0]).write_bytes(b'changed after prepare')
            with self.assertRaisesRegex(RuntimeError,'SHA256'):original.verify_files(files,target=target)

    def test_symlink_restoration_is_refused(self):
        if not hasattr(__import__('os'),'symlink'):self.skipTest('symlinks unavailable')
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve();(root/'real').mkdir()
            try:(root/'link').symlink_to(root/'real',target_is_directory=True)
            except OSError:self.skipTest('symlink creation requires privileges')
            with self.assertRaisesRegex(RuntimeError,'link/reparse'):original.plain_path(root/'link'/'part.step')

    def test_prepare_and_verify_keep_original_zip_and_report_bytes_and_no_native_calls(self):
        entries, expected, rows=fixture();raw=archive(entries)
        context=dict(run_id=42,head_sha='a'*40,production_public_acceptance=False)
        source=run(original.SOURCE_HEAD,original.SOURCE_RUN,True)
        artifact=dict(id=original.ARTIFACT_ID,name=original.ARTIFACT_NAME,expired=False,digest='sha256:'+sha(raw),size_in_bytes=len(raw),
                      workflow_run=dict(id=original.SOURCE_RUN,head_sha=original.SOURCE_HEAD,head_branch=original.BRANCH,
                                        repository_id=original.REPOSITORY_ID,head_repository_id=original.REPOSITORY_ID))
        replies=[run('a'*40,42),source,artifact,raw]
        api=mock.Mock();api.api.side_effect=replies
        restore=original.restore_files;verify=original.verify_files
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve();target=lambda row:root/'restored'/PureWindowsPath(row['path']).name
            with mock.patch.object(original,'OUTPUTS',expected), mock.patch.object(original,'ZIP_SHA256',sha(raw)), \
                    mock.patch.object(original,'restore_files',side_effect=lambda files:restore(files,target=target)), \
                    mock.patch.object(original,'verify_files',side_effect=lambda files,**kwargs:verify(files,target=kwargs.get('target',target))):
                output=root/'evidence'
                original.prepare(output,copy.deepcopy(context),api)
                self.assertEqual((output/'original.zip').read_bytes(),raw)
                self.assertEqual((output/'source-public-report.json').read_bytes(),entries[original.REPORT_MEMBER])
                original.verify(output,context)
                self.assertEqual(api.api.call_count,4)  # One current run, source run, metadata and ZIP; no retry.
                target(rows[-1]).write_bytes(b'late change')
                with self.assertRaisesRegex(RuntimeError,'SHA256'):original.verify(output,context)

    def test_bad_source_metadata_stops_before_download_or_target_copy(self):
        api=mock.Mock();api.api.side_effect=[run('a'*40,42),run('b'*40,original.SOURCE_RUN,True)]
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(original,'restore_files') as restore:
            with self.assertRaisesRegex(RuntimeError,'identity'):
                original.prepare(Path(directory).resolve()/'new',dict(run_id=42,head_sha='a'*40),api)
            self.assertEqual(api.api.call_count,2)
            restore.assert_not_called()
