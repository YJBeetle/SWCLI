"""Explicit private opening-transition probe. No CAD imports, writes, or execution here.
The original strict WorkingCopy baseline is never replaced. Every raw field is kept.
"""
from copy import deepcopy
import file_forensics as forensic

TOP = forensic.SOURCE
ACCESS_TIME_POLICY = 'record-only'


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def changes(before, after, path=()):
    """Exact recursive comparison, including unknown/new fields; never strip metadata."""
    # This collector summary has a variable key set (equal ctimes -> no entry).
    # Keep its complete raw dictionaries as one derived field, never normalize times.
    if len(path)==4 and path[0]=='raw' and path[3]=='raw_python_cross_channel_differences':
        return [] if before==after else [dict(path=list(path),before=before,after=after)]
    if type(before) is not type(after):
        return [dict(path=list(path), before=before, after=after)]
    if isinstance(before, dict):
        if before.keys()!=after.keys():
            return [dict(path=list(path),before=before,after=after)]
        return [item for key in before for item in changes(before[key], after[key], path+(key,))]
    if isinstance(before, list):
        require(len(before) == len(after), 'metadata row count changed: '+repr(path))
        return [item for i, (a, b) in enumerate(zip(before, after)) for item in changes(a, b, path+(i,))]
    return [] if before == after else [dict(path=list(path), before=before, after=after)]


def opening_allowed(path):
    if tuple(path[:2]) == ('stable', TOP):
        return tuple(path[2:]) in (('handle_before','st_ctime_ns'), ('handle_after','st_ctime_ns'))
    if tuple(path[:2]) != ('raw', TOP) or len(path) < 4 or path[2] not in (0, 1):
        return False
    return tuple(path[3:]) in (('python_held','st_ctime_ns'),
                                ('raw_python_cross_channel_differences',),
                                ('win32_held','basic','ChangeTime'),
                                ('win32_path_reopen','basic','ChangeTime'))


def capture_frame(copy, label, frame):
    """Two raw snapshots + full SHA per file, enclosed by unchanged stable_file reads.
    Explicit record-only access time policy; every other metadata field stays strict.
    This is a bounded OS read, never a new standalone experiment or a CAD retry.
    """
    frame.update(label=label, complete=False, access_time_policy=ACCESS_TIME_POLICY,
                 stable={}, raw={}, captures={}, native_channel_changes={})
    frame['stable'] = copy.snapshot()
    for name, pinned in copy.files.items():
        row = frame['captures'][name] = {}
        forensic.collect(forensic.NativeBackend(), str(copy.root/name), pinned['sha256'], row, access_time_policy=ACCESS_TIME_POLICY)
        require(row.get('complete') is True and not row['first_error'] and not row['cleanup_errors'],
                'phase raw capture failed: '+name+'; '+str(row.get('first_error')))
        require(row['hash']['bytes_read'] == pinned['size_bytes'], 'phase full hash size differs')
        frame['raw'][name] = deepcopy(row['snapshots'])
        frame['native_channel_changes'][name]=[]
        for snapshot in row['snapshots']:
            for channel, stable_key in (('python_path','path_before'),('python_held','handle_before')):
                for key, expected in frame['stable'][name][stable_key].items():
                    require(snapshot[channel][key] == expected, 'stable/raw sampling disagreement: '+name+':'+channel+':'+key)
            # Only access time is record-only across native sampling channels.
            native = snapshot['win32_held']
            reopened = snapshot['win32_path_reopen']
            frame['native_channel_changes'][name].append({} if native==reopened else dict(held=deepcopy(native),reopened=deepcopy(reopened)))
            require(forensic.native_stability(native,ACCESS_TIME_POLICY)==forensic.native_stability(reopened,ACCESS_TIME_POLICY),
                    'held/reopened native sampling disagreement: '+name)
    require(copy.snapshot() == frame['stable'], 'source changed during multi-file phase capture')
    frame['complete'] = True


class PhaseGuard:
    """Only one preselected top ctime transition across OpenDoc; never across model reads.
    Duck-types WorkingCopy for Observation without changing WorkingCopy.before.
    """
    def __init__(self, copy, report, capture=capture_frame):
        self.copy, self.capture = copy, capture
        self.root, self.files = copy.root, copy.files
        self.origin = deepcopy(copy.before)
        self.before_open_frame = self.opened_frame = self.loaded_frame = None
        self.state = 'prepared'
        self.record = report['file_phases'] = dict(
            schema='swcli.markingjig-opening-phases.v2', policy='opening-transition-probe',
            state=self.state, original_strict_baseline=deepcopy(self.origin), frames=[],
            access_time_policy=ACCESS_TIME_POLICY, raw_access_times_strict=False, timestamp_normalization=False, tolerance=None,
            opening_transition_is_not_no_write_evidence=True,
            loaded_baseline_sealed=False, export_permitted=False)

    def external(self, path):
        return self.copy.external(path)

    def set_state(self, state):
        self.state = self.record['state'] = state

    def take(self, label):
        frame = {}
        self.record['frames'].append(frame)
        try:
            self.capture(self.copy, label, frame)
            require(frame.get('complete') is True, 'incomplete phase capture')
            require(frame.get('access_time_policy')==ACCESS_TIME_POLICY, 'phase access time policy differs')
            require(set(frame['stable']) == set(self.origin) == set(frame['raw']), 'phase file set changed')
            for name, original in self.origin.items():
                for snapshot in frame['raw'][name]:
                    path_stat, held_stat=snapshot['python_path'],snapshot['python_held']
                    expected={k:dict(path=path_stat[k],held=held_stat[k]) for k in forensic.FIELDS if path_stat[k]!=held_stat[k]}
                    require(snapshot['raw_python_cross_channel_differences']==expected, 'derived raw channel differences inconsistent')
                row = frame['stable'][name]
                require(row['sha256'] == original['sha256'] and row['size_bytes'] == original['size_bytes'],
                        'whole-experiment content changed: '+name)
                for channel in ('path_before','handle_before','handle_after','path_after'):
                    for key in ('st_dev','st_ino'):
                        require(row[channel][key] == original[channel][key], 'whole-experiment physical identity changed: '+name)
        except BaseException as error:
            frame['phase_error'] = forensic.record_error(error)
            raise
        return frame

    @staticmethod
    def metadata(frame, *, projected=False):
        raw={name:[forensic.snapshot_stability(row,ACCESS_TIME_POLICY) for row in rows]
             for name,rows in frame['raw'].items()} if projected else frame['raw']
        return dict(stable=frame['stable'], raw=raw)

    def strict(self, baseline, frame, reason):
        frame['baseline_raw_changes'] = changes(self.metadata(baseline), self.metadata(frame))
        delta = changes(self.metadata(baseline,projected=True), self.metadata(frame,projected=True))
        frame['baseline_changes'] = delta
        require(not delta, reason)

    def before_open(self):
        require(self.state == 'prepared', 'opening phase cannot repeat')
        self.copy.unchanged()
        frame = self.take('before-readonly-opening-sequence')
        require(frame['stable'] == self.origin, 'preopening original strict baseline changed')
        self.before_open_frame = frame
        self.set_state('opening')

    def after_open(self):
        require(self.state == 'opening', 'after-open capture outside one opening')
        frame = self.take('after-readonly-opening-sequence')
        self.record['opening_raw_changes'] = changes(self.metadata(self.before_open_frame), self.metadata(frame))
        delta = changes(self.metadata(self.before_open_frame,projected=True), self.metadata(frame,projected=True))
        self.record['opening_changes'] = delta
        require(all(opening_allowed(item['path']) for item in delta), 'opening changed fields outside top held-ctime/Win32 ChangeTime')
        if delta:
            wanted = {('stable', TOP, c, 'st_ctime_ns') for c in ('handle_before','handle_after')}
            for i in (0, 1):
                wanted.add(('raw', TOP, i, 'python_held', 'st_ctime_ns'))
                wanted.add(('raw', TOP, i, 'raw_python_cross_channel_differences'))
                for c in ('win32_held','win32_path_reopen'):
                    wanted.add(('raw', TOP, i, c, 'basic', 'ChangeTime'))
            require({tuple(item['path']) for item in delta} == wanted, 'incomplete top ctime/ChangeTime transition evidence')
        # A successful capture already matches stable/raw Python fields and both Win32
        # channels, so inconsistent or partial samples cannot establish a checkpoint.
        self.record['opening_classification'] = 'opening-metadata-transition' if delta else 'opening-metadata-unchanged'
        self.opened_frame = frame
        self.set_state('opened-not-admitted')

    def unchanged(self):
        require(self.state in ('opened-not-admitted','loaded'), 'model observation outside validated file phase')
        frame = self.take('model-gate-check' if self.state == 'opened-not-admitted' else 'loaded-stage-check')
        baseline = self.loaded_frame if self.state == 'loaded' else self.opened_frame
        self.strict(baseline, frame, 'same-channel metadata changed after opening; no new baseline')
        return frame['stable']

    def seal_loaded(self, model):
        require(self.state == 'opened-not-admitted', 'loaded baseline cannot be resealed')
        require(model.get('complete') is True, 'full model/reference/geometry admission incomplete')
        top = model.get('top', {})
        require(top.get('type') == 2 and top.get('readonly') is True and top.get('modified') is False
                and top.get('viewonly') is False, 'actual loaded model not readonly/clean/full')
        frame = self.take('seal-loaded-baseline-after-full-model-gate')
        self.strict(self.opened_frame, frame, 'metadata changed during complete admission')
        self.loaded_frame = deepcopy(frame)
        self.record['loaded_baseline_frame_index'] = len(self.record['frames'])-1
        self.record['loaded_baseline_sealed'] = True
        self.set_state('loaded')

    def postcheck(self):
        """OS-only, including after failure. Original business error belongs to harness."""
        if self.state in ('opened-not-admitted','loaded'):
            return self.unchanged()
        frame = self.take('failed-before-admission-postcheck')
        if self.before_open_frame is not None:
            self.strict(self.before_open_frame, frame, 'failed opening did not retain original metadata')
        else:
            require(frame['stable'] == self.origin, 'original strict baseline changed')
        return frame['stable']
