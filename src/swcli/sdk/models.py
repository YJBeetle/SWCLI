"""Generated from operation/result schemas; edit scripts/dev/generate-sdk.py instead."""

from typing import Dict, List, Literal, TypedDict, Union
from .runtime import JSONValue


class _DocumentStateRequired(TypedDict):
    title: str
    path: str
    type: int
    modified: bool
    update_stamp: Union[int, None]


class DocumentState(_DocumentStateRequired, total=False):
    document_id: str
    current: bool
    active: bool


class ArtifactContentError(TypedDict):
    code: str
    message: str


class _ArtifactContentRequired(TypedDict):
    status: Literal['ready', 'attached', 'too_large', 'unavailable', 'unsupported']
    limit_bytes: Literal[8388608]


class ArtifactContent(_ArtifactContentRequired, total=False):
    data_base64: str
    sha256: str
    media_type: str
    preview_media_type: str
    uri: str
    preview_size_bytes: int
    preview_sha256: str
    error: ArtifactContentError


class _ArtifactRequired(TypedDict):
    kind: str
    path: str
    size_bytes: int


class Artifact(_ArtifactRequired, total=False):
    format: Literal['STEP', 'STP', 'GLB', 'STL', '3MF', 'AMF', 'PDF', 'DWG']
    media_type: str
    content: ArtifactContent


class _LeaseStateRequired(TypedDict):
    document_id: str
    session_id: str
    expires_in_seconds: float


class LeaseState(_LeaseStateRequired, total=False):
    lease_id: str


class DaemonHealthParameters(TypedDict):
    pass


class DaemonHealthResultRecoveryErrorVariant1(TypedDict):
    code: str
    message: str


class DaemonHealthResultHostVariant1(TypedDict):
    revision: str
    solidworks_revision: str
    language: str
    process_id: int
    visible: bool
    startup_wait_seconds: float
    owned_by_daemon: bool
    shared_interactive: bool
    platform: Literal['windows', 'macos-wine', 'linux-wine']


class DaemonHealthResult(TypedDict):
    server_version: str
    protocol_versions: List[str]
    worker_alive: bool
    host_connected: bool
    recovery_required: bool
    recovery_error: Union[DaemonHealthResultRecoveryErrorVariant1, None]
    host: Union[DaemonHealthResultHostVariant1, None]


DaemonRuntimeStatusParameters = DaemonHealthParameters


class DaemonRuntimeStatusResultSwProcessesItem(TypedDict):
    process_id: int
    visible: Union[bool, None]


class DaemonRuntimeStatusResult(TypedDict):
    daemon_running: Union[bool, None]
    host_connected: Union[bool, None]
    sw_running: Union[bool, None]
    user_sw_running: Union[bool, None]
    daemon_sw_owned: Union[bool, None]
    daemon_sw_visible: Union[bool, None]
    other_sw_running: Union[bool, None]
    daemon_reachable: bool
    daemon_state: Literal['unknown', 'stopped', 'starting', 'ready', 'degraded']
    daemon_sw_pid: Union[int, None]
    visibility_source: Literal['startup-report', 'top-level-windows', 'unavailable']
    visibility_current: bool
    sw_processes: Union[List[DaemonRuntimeStatusResultSwProcessesItem], None]
    pid_namespace: Literal['windows', 'unavailable']
    process_scope: Literal['daemon-host', 'client-host', 'unavailable']
    health: Union[Dict[str, JSONValue], None]
    probe_errors: List[ArtifactContentError]


class DaemonCapabilitiesParameters(TypedDict, total=False):
    include_schemas: bool
    operation: str


class DaemonCapabilitiesResultTransport(TypedDict):
    tls: bool
    authenticated: bool


class DaemonCapabilitiesResultWorkspaceVariant2(TypedDict):
    root: str
    max_file_bytes: int
    chunk_bytes: int
    active_upload_limit: int
    active_download_limit: int
    expires_after_seconds: int


class DaemonCapabilitiesResultExportFormats(TypedDict):
    part: List[str]
    assembly: List[str]
    drawing: List[str]


class DaemonCapabilitiesResultRequestReplay(TypedDict):
    supported: Literal[True]
    max_entries: int
    max_bytes: int
    scope: Literal['daemon']


class _DaemonCapabilitiesResultRequired(TypedDict):
    export_formats: DaemonCapabilitiesResultExportFormats
    protocol_versions: List[str]
    server_version: str
    host: Union[DaemonHealthResultHostVariant1, None]
    operations: List[str]
    request_replay: DaemonCapabilitiesResultRequestReplay
    worker_alive: bool
    host_connected: bool
    recovery_required: bool
    recovery_error: Union[DaemonHealthResultRecoveryErrorVariant1, None]


class DaemonCapabilitiesResult(_DaemonCapabilitiesResultRequired, total=False):
    transport: DaemonCapabilitiesResultTransport
    workspace: Union[None, DaemonCapabilitiesResultWorkspaceVariant2]
    operation_schemas: Dict[str, Dict[str, JSONValue]]
    operation_result_schemas: Dict[str, Dict[str, JSONValue]]


DaemonShutdownParameters = DaemonHealthParameters


class _DaemonShutdownResultRequired(TypedDict):
    stopping: Literal[True]


class DaemonShutdownResult(_DaemonShutdownResultRequired, total=False):
    host_already_disconnected: bool


class DocumentCreateParameters(TypedDict, total=False):
    type: Literal['part', 'assembly', 'drawing']
    template: str
    projection: Literal['first-angle', 'third-angle']


class DocumentCreateResultWarningsItem(TypedDict):
    code: str
    message: str


class DocumentCreateResultError(TypedDict):
    type: str
    message: str


class _DocumentCreateResultTemplateRequired(TypedDict):
    ok: bool
    path: Union[str, None]
    source: str


class DocumentCreateResultTemplate(_DocumentCreateResultTemplateRequired, total=False):
    configured_path: Union[str, None]
    searched_roots: List[str]


class _DocumentCreateResultSheetRequired(TypedDict):
    name: str
    properties: List[Union[float, bool]]
    format_path: str
    format_available: bool
    projection: Literal['first-angle', 'third-angle']


class DocumentCreateResultSheet(_DocumentCreateResultSheetRequired, total=False):
    unit: Literal['meter']


class _DocumentCreateResultViewsItemRequired(TypedDict):
    name: str
    path: str
    configuration: str
    position: List[float]
    outline: List[float]
    scale: List[float]
    transform: List[float]


class DocumentCreateResultViewsItem(_DocumentCreateResultViewsItemRequired, total=False):
    unit: Literal['meter']
    coordinate_system: Literal['sheet']
    role: Literal['front', 'top', 'left', 'right']


class DocumentCreateResultDiagnosticsIssuesItem(TypedDict):
    index: int
    name: str
    type: str
    code: int
    severity: Literal['error', 'warning']


class DocumentCreateResultDiagnostics(TypedDict):
    healthy: bool
    issues: List[DocumentCreateResultDiagnosticsIssuesItem]
    issue_count: int
    scanned_feature_count: int
    truncated: bool
    limit: int


class DocumentCreateResultCleanupErrorsItem(TypedDict):
    stage: str
    error: str


class _DocumentCreateResultRequired(TypedDict):
    ok: bool
    action: Literal['document.create']


class DocumentCreateResult(_DocumentCreateResultRequired, total=False):
    document: DocumentState
    session_id: str
    warnings: List[DocumentCreateResultWarningsItem]
    error: DocumentCreateResultError
    created: Literal[True]
    template: DocumentCreateResultTemplate
    sheet: DocumentCreateResultSheet
    views: List[DocumentCreateResultViewsItem]
    diagnostics: DocumentCreateResultDiagnostics
    cleanup_errors: List[DocumentCreateResultCleanupErrorsItem]


class DrawingStandardViewsParameters(TypedDict):
    source_document_id: str
    configuration: str


class DrawingStandardViewsResultSource(TypedDict, total=False):
    path: str
    configuration: str
    type: int
    modified: bool
    update_stamp: Union[int, None]
    needs_rebuild: int


class DrawingStandardViewsResultMutation(TypedDict):
    attempted: bool
    may_have_changed: bool


class DrawingStandardViewsResultVerification(TypedDict, total=False):
    passed: bool
    source_unchanged: bool
    layout_verified: bool


class _DrawingStandardViewsResultRequired(TypedDict):
    ok: bool
    action: Literal['drawing.standard-views']


class DrawingStandardViewsResult(_DrawingStandardViewsResultRequired, total=False):
    document: DocumentState
    session_id: str
    warnings: List[DocumentCreateResultWarningsItem]
    error: DocumentCreateResultError
    coordinate_system: Literal['sheet']
    source_document_id: str
    source: DrawingStandardViewsResultSource
    sheet: DocumentCreateResultSheet
    views: List[DocumentCreateResultViewsItem]
    mutation: DrawingStandardViewsResultMutation
    rebuilt: bool
    verification: DrawingStandardViewsResultVerification
    diagnostics: DocumentCreateResultDiagnostics
    cleanup_errors: List[DocumentCreateResultCleanupErrorsItem]


class _AssemblyAddComponentParametersRequired(TypedDict):
    path: str


class AssemblyAddComponentParameters(_AssemblyAddComponentParametersRequired, total=False):
    configuration: str
    x_mm: float
    y_mm: float
    z_mm: float


class AssemblyAddComponentResultComponent(TypedDict):
    name: str
    path: str
    configuration: str


class AssemblyAddComponentResultPlacementRequestedCenter(TypedDict):
    x: float
    y: float
    z: float


class AssemblyAddComponentResultPlacement(TypedDict):
    unit: Literal['millimeter']
    method: Literal['native-approximate-component-center']
    requested_center: AssemblyAddComponentResultPlacementRequestedCenter


class _AssemblyAddComponentResultRequired(TypedDict):
    ok: bool
    action: Literal['assembly.add-component']


class AssemblyAddComponentResult(_AssemblyAddComponentResultRequired, total=False):
    document: DocumentState
    session_id: str
    warnings: List[DocumentCreateResultWarningsItem]
    error: DocumentCreateResultError
    inserted: Literal[True]
    component: AssemblyAddComponentResultComponent
    component_count_before: int
    component_count_after: int
    placement: AssemblyAddComponentResultPlacement


class _DocumentOpenParametersRequired(TypedDict):
    path: str


class DocumentOpenParameters(_DocumentOpenParametersRequired, total=False):
    read_only: bool
    configuration: str


class _DocumentOpenResultRequired(TypedDict):
    ok: bool
    action: Literal['document.open']


class DocumentOpenResult(_DocumentOpenResultRequired, total=False):
    document: DocumentState
    session_id: str
    warnings: List[DocumentCreateResultWarningsItem]
    error: DocumentCreateResultError
    path: str
    read_only: bool
    configuration: Union[str, None]
    api_errors: int
    api_warnings: int


DocumentListParameters = DaemonHealthParameters


class _DocumentListResultRequired(TypedDict):
    ok: bool
    action: Literal['document.list']


class DocumentListResult(_DocumentListResultRequired, total=False):
    document: DocumentState
    session_id: str
    warnings: List[DocumentCreateResultWarningsItem]
    error: DocumentCreateResultError
    current_document_id: Union[str, None]
    documents: List[DocumentState]
    count: int


class DocumentUseParameters(TypedDict):
    pass


class _DocumentUseResultRequired(TypedDict):
    ok: bool
    action: Literal['document.use']


class DocumentUseResult(_DocumentUseResultRequired, total=False):
    document: DocumentState
    session_id: str
    warnings: List[DocumentCreateResultWarningsItem]
    error: DocumentCreateResultError


class DocumentLeaseAcquireParameters(TypedDict, total=False):
    ttl_seconds: float


class _DocumentLeaseAcquireResultRequired(TypedDict):
    ok: bool
    action: Literal['document.lease.acquire']


class DocumentLeaseAcquireResult(_DocumentLeaseAcquireResultRequired, total=False):
    document: DocumentState
    session_id: str
    warnings: List[DocumentCreateResultWarningsItem]
    error: DocumentCreateResultError
    lease: LeaseState


class DocumentLeaseStatusParameters(TypedDict):
    pass


class _DocumentLeaseStatusResultRequired(TypedDict):
    ok: bool
    action: Literal['document.lease.status']


class DocumentLeaseStatusResult(_DocumentLeaseStatusResultRequired, total=False):
    document: DocumentState
    session_id: str
    warnings: List[DocumentCreateResultWarningsItem]
    error: DocumentCreateResultError
    lease: Union[LeaseState, None]
    leased: bool
    owned_by_session: bool


class DocumentLeaseRenewParameters(TypedDict, total=False):
    ttl_seconds: float


class _DocumentLeaseRenewResultRequired(TypedDict):
    ok: bool
    action: Literal['document.lease.renew']


class DocumentLeaseRenewResult(_DocumentLeaseRenewResultRequired, total=False):
    document: DocumentState
    session_id: str
    warnings: List[DocumentCreateResultWarningsItem]
    error: DocumentCreateResultError
    lease: LeaseState


class DocumentLeaseReleaseParameters(TypedDict):
    pass


class _DocumentLeaseReleaseResultRequired(TypedDict):
    ok: bool
    action: Literal['document.lease.release']


class DocumentLeaseReleaseResult(_DocumentLeaseReleaseResultRequired, total=False):
    document: DocumentState
    session_id: str
    warnings: List[DocumentCreateResultWarningsItem]
    error: DocumentCreateResultError
    lease: LeaseState
    released: bool


class DocumentInspectParameters(TypedDict, total=False):
    detail: Literal['summary', 'structure']
    max_features: int


class DocumentInspectResultStructureConfigurations(TypedDict):
    active: Union[str, None]
    names: List[str]
    count: int


class DocumentInspectResultStructureUnitsVariant1(TypedDict):
    raw: List[float]


class DocumentInspectResultStructureUnitsVariant2Length(TypedDict):
    code: int
    name: str


class DocumentInspectResultStructureUnitsVariant2(TypedDict):
    length: DocumentInspectResultStructureUnitsVariant2Length
    fraction_base: int
    fraction_value: int
    significant_digits: int
    round_to_fraction: bool


class DocumentInspectResultStructureFeaturesItemsItem(TypedDict):
    index: int
    name: str
    type: str
    visibility: int


class DocumentInspectResultStructureFeatures(TypedDict):
    order: Literal['model-definition']
    count: int
    truncated: bool
    limit: int
    items: List[DocumentInspectResultStructureFeaturesItemsItem]


class DocumentInspectResultStructureBodiesItemsItemApproximateBoundingBoxVariant1(TypedDict):
    coordinate_system: Literal['model']
    unit: Literal['meter']
    minimum: AssemblyAddComponentResultPlacementRequestedCenter
    maximum: AssemblyAddComponentResultPlacementRequestedCenter
    size_mm: AssemblyAddComponentResultPlacementRequestedCenter
    accuracy: Literal['approximate']


class DocumentInspectResultStructureBodiesItemsItem(TypedDict):
    name: str
    type: DocumentInspectResultStructureUnitsVariant2Length
    visible: bool
    face_count: int
    edge_count: int
    approximate_bounding_box: Union[DocumentInspectResultStructureBodiesItemsItemApproximateBoundingBoxVariant1, None]


class DocumentInspectResultStructureBodies(TypedDict):
    applicable: bool
    count: int
    items: List[DocumentInspectResultStructureBodiesItemsItem]


class DocumentInspectResultStructure(TypedDict):
    configurations: DocumentInspectResultStructureConfigurations
    units: Union[DocumentInspectResultStructureUnitsVariant1, DocumentInspectResultStructureUnitsVariant2]
    features: DocumentInspectResultStructureFeatures
    bodies: DocumentInspectResultStructureBodies


class _DocumentInspectResultRequired(TypedDict):
    ok: bool
    action: Literal['document.inspect']


class DocumentInspectResult(_DocumentInspectResultRequired, total=False):
    document: DocumentState
    session_id: str
    warnings: List[DocumentCreateResultWarningsItem]
    error: DocumentCreateResultError
    needs_rebuild: int
    structure: DocumentInspectResultStructure


class DocumentPropertiesParameters(TypedDict, total=False):
    name: str
    configuration: str


class DocumentPropertiesResultPropertiesItem(TypedDict):
    name: str
    type: str
    type_code: int
    raw_value: str
    evaluated_value: str
    resolution: Literal['cached', 'resolved']
    was_resolved: bool
    linked: bool


class _DocumentPropertiesResultRequired(TypedDict):
    ok: bool
    action: Literal['document.properties']


class DocumentPropertiesResult(_DocumentPropertiesResultRequired, total=False):
    document: DocumentState
    session_id: str
    warnings: List[DocumentCreateResultWarningsItem]
    error: DocumentCreateResultError
    scope: Literal['document', 'configuration']
    configuration: str
    requested_name: Union[str, None]
    properties: List[DocumentPropertiesResultPropertiesItem]


class DocumentPropertySummaryParameters(TypedDict, total=False):
    name: str


class DocumentPropertySummaryResultConfigurationsItem(TypedDict):
    configuration: str
    properties: List[DocumentPropertiesResultPropertiesItem]


class _DocumentPropertySummaryResultRequired(TypedDict):
    ok: bool
    action: Literal['document.property-summary']


class DocumentPropertySummaryResult(_DocumentPropertySummaryResultRequired, total=False):
    document: DocumentState
    session_id: str
    warnings: List[DocumentCreateResultWarningsItem]
    error: DocumentCreateResultError
    requested_name: Union[str, None]
    configurations: List[DocumentPropertySummaryResultConfigurationsItem]


class _DocumentPropertyAddParametersRequired(TypedDict):
    name: str
    value: str


class DocumentPropertyAddParameters(_DocumentPropertyAddParametersRequired, total=False):
    configuration: str
    type: Literal['integer', 'double', 'yes-no', 'text', 'date']


class _DocumentPropertyAddResultRequired(TypedDict):
    ok: bool
    action: Literal['document.property-add']


class DocumentPropertyAddResult(_DocumentPropertyAddResultRequired, total=False):
    document: DocumentState
    session_id: str
    warnings: List[DocumentCreateResultWarningsItem]
    error: DocumentCreateResultError
    scope: Literal['document', 'configuration']
    configuration: str
    name: str
    before: Union[DocumentPropertiesResultPropertiesItem, None]
    property: Union[DocumentPropertiesResultPropertiesItem, None]
    changed: bool
    mutation: DrawingStandardViewsResultMutation


class _DocumentPropertySetParametersRequired(TypedDict):
    name: str
    value: str


class DocumentPropertySetParameters(_DocumentPropertySetParametersRequired, total=False):
    configuration: str
    expected_value: str


class _DocumentPropertySetResultRequired(TypedDict):
    ok: bool
    action: Literal['document.property-set']


class DocumentPropertySetResult(_DocumentPropertySetResultRequired, total=False):
    document: DocumentState
    session_id: str
    warnings: List[DocumentCreateResultWarningsItem]
    error: DocumentCreateResultError
    scope: Literal['document', 'configuration']
    configuration: str
    name: str
    before: Union[DocumentPropertiesResultPropertiesItem, None]
    property: Union[DocumentPropertiesResultPropertiesItem, None]
    changed: bool
    mutation: DrawingStandardViewsResultMutation


class _DocumentPropertyDeleteParametersRequired(TypedDict):
    name: str


class DocumentPropertyDeleteParameters(_DocumentPropertyDeleteParametersRequired, total=False):
    configuration: str
    expected_value: str


class _DocumentPropertyDeleteResultRequired(TypedDict):
    ok: bool
    action: Literal['document.property-delete']


class DocumentPropertyDeleteResult(_DocumentPropertyDeleteResultRequired, total=False):
    document: DocumentState
    session_id: str
    warnings: List[DocumentCreateResultWarningsItem]
    error: DocumentCreateResultError
    scope: Literal['document', 'configuration']
    configuration: str
    name: str
    before: Union[DocumentPropertiesResultPropertiesItem, None]
    property: Union[DocumentPropertiesResultPropertiesItem, None]
    changed: bool
    mutation: DrawingStandardViewsResultMutation


class DocumentImageQualityParameters(TypedDict):
    pass


class DocumentImageQualityResultQualityNative(TypedDict):
    shaded_mode: int
    shaded_deviation_m: float
    optimize_edge_length: bool
    save_tessellation: bool
    apply_to_referenced_parts: bool


class DocumentImageQualityResultQualityDeviationRange(TypedDict):
    status: int
    bounds_m: List[float]


class DocumentImageQualityResultQuality(TypedDict):
    shaded_mode: Literal['coarse', 'fine', 'custom', 'other']
    shaded_deviation_mm: float
    optimize_edge_length: bool
    save_tessellation: bool
    apply_to_referenced_parts: bool
    native: DocumentImageQualityResultQualityNative
    deviation_range: DocumentImageQualityResultQualityDeviationRange


class _DocumentImageQualityResultRequired(TypedDict):
    ok: bool
    action: Literal['document.image-quality']


class DocumentImageQualityResult(_DocumentImageQualityResultRequired, total=False):
    document: DocumentState
    session_id: str
    warnings: List[DocumentCreateResultWarningsItem]
    error: DocumentCreateResultError
    quality: DocumentImageQualityResultQuality
    finalization_error: DocumentCreateResultError


class DocumentImageQualitySetParameters(TypedDict):
    field: Literal['shaded_mode', 'shaded_deviation_mm', 'optimize_edge_length']
    value: Union[str, float, bool]
    expected_quality: DocumentImageQualityResultQuality


class DocumentImageQualitySetResultLinkedChangesItemVariant1(TypedDict):
    field: Literal['shaded_deviation_mm']
    before: float
    after: float
    reason: Literal['shaded-mode-coupling']


class DocumentImageQualitySetResultLinkedChangesItemVariant2(TypedDict):
    field: Literal['shaded_mode']
    before: Literal['coarse', 'fine', 'custom']
    after: Literal['custom']
    reason: Literal['shaded-deviation-coupling']


class _DocumentImageQualitySetResultRequired(TypedDict):
    ok: bool
    action: Literal['document.image-quality-set']


class DocumentImageQualitySetResult(_DocumentImageQualitySetResultRequired, total=False):
    document: DocumentState
    session_id: str
    warnings: List[DocumentCreateResultWarningsItem]
    error: DocumentCreateResultError
    field: Literal['shaded_mode', 'shaded_deviation_mm', 'optimize_edge_length']
    before: DocumentImageQualityResultQuality
    quality: DocumentImageQualityResultQuality
    observed_quality: DocumentImageQualityResultQuality
    changed: bool
    mutation: DrawingStandardViewsResultMutation
    native_return: JSONValue
    finalization_error: DocumentCreateResultError
    linked_changes: List[Union[DocumentImageQualitySetResultLinkedChangesItemVariant1, DocumentImageQualitySetResultLinkedChangesItemVariant2]]


DocumentAnnotationOptionsParameters = DocumentImageQualityParameters


class _DocumentAnnotationOptionsResultRequired(TypedDict):
    ok: bool
    action: Literal['document.annotation-options']


class DocumentAnnotationOptionsResult(_DocumentAnnotationOptionsResultRequired, total=False):
    document: DocumentState
    session_id: str
    warnings: List[DocumentCreateResultWarningsItem]
    error: DocumentCreateResultError
    options: Dict[str, JSONValue]


class DocumentAnnotationOptionSetParameters(TypedDict):
    field: Literal['arrow.edge_vertex', 'arrow.face_surface', 'arrow.unattached', 'bent_leader.enabled', 'bent_leader.length_mm', 'zero.leading', 'zero.trailing']
    value: Union[str, bool, float]
    expected_value: Union[str, bool, float]


class _DocumentAnnotationOptionSetResultRequired(TypedDict):
    ok: bool
    action: Literal['document.annotation-option-set']


class DocumentAnnotationOptionSetResult(_DocumentAnnotationOptionSetResultRequired, total=False):
    document: DocumentState
    session_id: str
    warnings: List[DocumentCreateResultWarningsItem]
    error: DocumentCreateResultError
    field: Literal['arrow.edge_vertex', 'arrow.face_surface', 'arrow.unattached', 'bent_leader.enabled', 'bent_leader.length_mm', 'zero.leading', 'zero.trailing']
    before: Dict[str, JSONValue]
    options: Dict[str, JSONValue]
    changed: bool
    mutation: DrawingStandardViewsResultMutation


DocumentUnitsParameters = DocumentImageQualityParameters


class DocumentUnitsResultUnitsNativeUnits(TypedDict):
    length_unit: int
    fraction_base: int
    fraction_value: int
    significant_digits: int
    round_to_fraction: int


class DocumentUnitsResultUnits(TypedDict):
    length_unit: Literal['mm', 'inch', 'other']
    decimal_places: int
    native_units: DocumentUnitsResultUnitsNativeUnits


class _DocumentUnitsResultRequired(TypedDict):
    ok: bool
    action: Literal['document.units']


class DocumentUnitsResult(_DocumentUnitsResultRequired, total=False):
    document: DocumentState
    session_id: str
    warnings: List[DocumentCreateResultWarningsItem]
    error: DocumentCreateResultError
    units: DocumentUnitsResultUnits


class DocumentUnitsSetParameters(TypedDict, total=False):
    length_unit: Literal['mm', 'inch']
    decimal_places: int
    expected_length_unit: Literal['mm', 'inch']
    expected_decimal_places: int


class _DocumentUnitsSetResultRequired(TypedDict):
    ok: bool
    action: Literal['document.units-set']


class DocumentUnitsSetResult(_DocumentUnitsSetResultRequired, total=False):
    document: DocumentState
    session_id: str
    warnings: List[DocumentCreateResultWarningsItem]
    error: DocumentCreateResultError
    before: DocumentUnitsResultUnits
    units: DocumentUnitsResultUnits
    changed: bool
    mutation: DrawingStandardViewsResultMutation


DocumentSummaryParameters = DocumentImageQualityParameters


class DocumentSummaryResultFields(TypedDict):
    title: str
    subject: str
    author: str
    keywords: str
    comment: str
    saved_by: str
    created_at: str
    saved_at: str


class _DocumentSummaryResultRequired(TypedDict):
    ok: bool
    action: Literal['document.summary']


class DocumentSummaryResult(_DocumentSummaryResultRequired, total=False):
    document: DocumentState
    session_id: str
    warnings: List[DocumentCreateResultWarningsItem]
    error: DocumentCreateResultError
    fields: DocumentSummaryResultFields
    saved_version_history: List[str]


class _DocumentSummarySetParametersRequired(TypedDict):
    field: Literal['title', 'subject', 'author', 'keywords', 'comment']
    value: str


class DocumentSummarySetParameters(_DocumentSummarySetParametersRequired, total=False):
    expected_value: str


class _DocumentSummarySetResultRequired(TypedDict):
    ok: bool
    action: Literal['document.summary-set']


class DocumentSummarySetResult(_DocumentSummarySetResultRequired, total=False):
    document: DocumentState
    session_id: str
    warnings: List[DocumentCreateResultWarningsItem]
    error: DocumentCreateResultError
    field: Literal['title', 'subject', 'author', 'keywords', 'comment']
    value: str
    before_value: str
    changed: bool
    mutation: DrawingStandardViewsResultMutation


class DocumentCloseParameters(TypedDict, total=False):
    discard: bool


class _DocumentCloseResultRequired(TypedDict):
    ok: bool
    action: Literal['document.close']


class DocumentCloseResult(_DocumentCloseResultRequired, total=False):
    document: DocumentState
    session_id: str
    warnings: List[DocumentCreateResultWarningsItem]
    error: DocumentCreateResultError
    discard: bool
    closed: bool


class DocumentMeasureParameters(TypedDict, total=False):
    max_bodies: int


class DocumentMeasureResultMetrics(TypedDict):
    solid_body_count: int
    volume_mm3: float
    surface_area_mm2: float
    centroid_mm: AssemblyAddComponentResultPlacementRequestedCenter


class DocumentMeasureResultBodiesItem(TypedDict):
    index: int
    volume_mm3: float
    surface_area_mm2: float
    centroid_mm: AssemblyAddComponentResultPlacementRequestedCenter


class _DocumentMeasureResultRequired(TypedDict):
    ok: bool
    action: Literal['document.measure']


class DocumentMeasureResult(_DocumentMeasureResultRequired, total=False):
    document: DocumentState
    session_id: str
    warnings: List[DocumentCreateResultWarningsItem]
    error: DocumentCreateResultError
    scope: Literal['sum-of-solid-bodies']
    coordinate_system: Literal['part-model']
    method: Literal['native-body-mass-properties']
    metrics: DocumentMeasureResultMetrics
    bodies: List[DocumentMeasureResultBodiesItem]


class DocumentSaveParameters(TypedDict):
    pass


class _DocumentSaveResultRequired(TypedDict):
    ok: bool
    action: Literal['document.save']


class DocumentSaveResult(_DocumentSaveResultRequired, total=False):
    document: DocumentState
    session_id: str
    warnings: List[DocumentCreateResultWarningsItem]
    error: DocumentCreateResultError
    api_saved: bool
    save_errors: int
    save_error_names: List[str]
    save_warnings: int
    save_warning_names: List[str]
    document_after: DocumentState


class DocumentSaveAsParameters(TypedDict):
    output: str


class DocumentSaveAsResultFileVerification(TypedDict):
    non_empty: bool
    minimum_size_valid: bool


class DocumentSaveAsResultArtifact(TypedDict):
    kind: Literal['native-document']
    format: Literal['SLDPRT', 'SLDASM', 'SLDDRW']
    path: str
    size_bytes: int


class _DocumentSaveAsResultRequired(TypedDict):
    ok: bool
    action: Literal['document.save-as']


class DocumentSaveAsResult(_DocumentSaveAsResultRequired, total=False):
    document: DocumentState
    session_id: str
    warnings: List[DocumentCreateResultWarningsItem]
    error: DocumentCreateResultError
    output: str
    document_before: DocumentState
    api_saved: bool
    save_errors: int
    save_error_names: List[str]
    save_warnings: None
    file_verification: DocumentSaveAsResultFileVerification
    artifact: DocumentSaveAsResultArtifact


class DocumentDiagnoseParameters(TypedDict, total=False):
    max_features: int


class _DocumentDiagnoseResultRequired(TypedDict):
    ok: bool
    action: Literal['document.diagnose']


class DocumentDiagnoseResult(_DocumentDiagnoseResultRequired, total=False):
    document: DocumentState
    session_id: str
    warnings: List[DocumentCreateResultWarningsItem]
    error: DocumentCreateResultError
    needs_rebuild: int
    diagnostics: DocumentCreateResultDiagnostics


class DocumentRebuildParameters(TypedDict, total=False):
    force: bool
    top_only: bool
    max_features: int


class _DocumentRebuildResultRequired(TypedDict):
    ok: bool
    action: Literal['document.rebuild']


class DocumentRebuildResult(_DocumentRebuildResultRequired, total=False):
    document: DocumentState
    session_id: str
    warnings: List[DocumentCreateResultWarningsItem]
    error: DocumentCreateResultError
    force: bool
    top_only: bool
    rebuilt: bool
    needs_rebuild_before: int
    needs_rebuild_after: int
    diagnostics: DocumentCreateResultDiagnostics


class _DocumentRenderParametersRequired(TypedDict):
    output: str


class DocumentRenderParameters(_DocumentRenderParametersRequired, total=False):
    width: int
    height: int
    view: Literal['current', 'front', 'back', 'left', 'right', 'top', 'bottom', 'isometric', 'trimetric', 'dimetric']
    fit: bool
    overwrite: bool
    include_content: bool


class DocumentRenderResultRequestedSize(TypedDict):
    width: int
    height: int
    unit: Literal['pixel']


class DocumentRenderResultView(TypedDict):
    name: str
    standard_id: Union[int, None]


class _DocumentRenderResultArtifactRequired(TypedDict):
    kind: Literal['image']
    path: str
    size_bytes: int
    media_type: Literal['image/bmp']


class DocumentRenderResultArtifact(_DocumentRenderResultArtifactRequired, total=False):
    format: Literal['STEP', 'STP', 'GLB', 'STL', '3MF', 'AMF', 'PDF', 'DWG']
    content: ArtifactContent


class _DocumentRenderResultRequired(TypedDict):
    ok: bool
    action: Literal['document.render']


class DocumentRenderResult(_DocumentRenderResultRequired, total=False):
    document: DocumentState
    session_id: str
    warnings: List[DocumentCreateResultWarningsItem]
    error: DocumentCreateResultError
    output: str
    requested_size: DocumentRenderResultRequestedSize
    view: DocumentRenderResultView
    fit: bool
    api_saved: bool
    actual_size: Union[DocumentRenderResultRequestedSize, None]
    artifact: DocumentRenderResultArtifact


class _DocumentExportParametersRequired(TypedDict):
    output: str


class DocumentExportParameters(_DocumentExportParametersRequired, total=False):
    overwrite: bool
    strict: bool
    include_content: bool


class _DocumentExportResultArtifactRequired(TypedDict):
    kind: Literal['cad-export']
    path: str
    size_bytes: int
    format: Literal['STEP', 'STP', 'GLB', 'STL', '3MF', 'AMF', 'PDF', 'DWG']


class DocumentExportResultArtifact(_DocumentExportResultArtifactRequired, total=False):
    media_type: str
    content: ArtifactContent


class _DocumentExportResultRequired(TypedDict):
    ok: bool
    action: Literal['document.export']


class DocumentExportResult(_DocumentExportResultRequired, total=False):
    document: DocumentState
    session_id: str
    warnings: List[DocumentCreateResultWarningsItem]
    error: DocumentCreateResultError
    output: str
    artifact: DocumentExportResultArtifact


class SketchListParameters(TypedDict, total=False):
    max_sketches: int


class SketchListResultSketchesItemOwnerVariant2(TypedDict):
    name: str
    type: str


class SketchListResultSketchesItem(TypedDict):
    sketch_id: str
    name: str
    type: Literal['ProfileFeature']
    constraint_status: int
    absorbed: bool
    owner: Union[None, SketchListResultSketchesItemOwnerVariant2]


class _SketchListResultRequired(TypedDict):
    ok: bool
    action: Literal['sketch.list']


class SketchListResult(_SketchListResultRequired, total=False):
    document: DocumentState
    session_id: str
    warnings: List[DocumentCreateResultWarningsItem]
    error: DocumentCreateResultError
    sketches: List[SketchListResultSketchesItem]
    count: int


FeatureListParameters = DocumentDiagnoseParameters


class FeatureListResultFeaturesItem(TypedDict):
    feature_id: str
    name: str
    type: str
    native_type: Literal['Boss', 'Extrusion', 'BaseBody', 'Cut']
    kind: Literal['boss-extrude', 'cut-extrude']


class FeatureListResultObservationBefore(TypedDict):
    configuration: str
    update_stamp: int
    modified: bool
    editing: bool
    foreground_present: bool


class _FeatureListResultObservationRequired(TypedDict):
    before: FeatureListResultObservationBefore
    unchanged: bool


class FeatureListResultObservation(_FeatureListResultObservationRequired, total=False):
    after: FeatureListResultObservationBefore


class _FeatureListResultRequired(TypedDict):
    ok: bool
    action: Literal['feature.list']


class FeatureListResult(_FeatureListResultRequired, total=False):
    document: DocumentState
    session_id: str
    warnings: List[DocumentCreateResultWarningsItem]
    error: DocumentCreateResultError
    scope: Literal['part-extrusions']
    features: List[FeatureListResultFeaturesItem]
    count: int
    observation: FeatureListResultObservation


class EntityListParameters(TypedDict, total=False):
    kind: Literal['face', 'edge']
    max_faces: int
    max_edges: int


class EntityListResultEntitiesItemVariant1SurfaceGeometryPlane(TypedDict):
    point_mm: List[float]
    surface_normal: List[float]
    outward_normal: List[float]


class EntityListResultEntitiesItemVariant1SurfaceGeometry(TypedDict):
    available: Literal[True]
    coordinate_system: Literal['part-model']
    boundary: Literal['untrimmed-surface']
    face_normal_opposes_surface: bool
    plane: EntityListResultEntitiesItemVariant1SurfaceGeometryPlane


class EntityListResultEntitiesItemVariant1(TypedDict):
    entity_id: str
    kind: Literal['face']
    surface_kind: Literal['plane']
    area_mm2: float
    area_accuracy: Literal['approximate']
    surface_geometry: EntityListResultEntitiesItemVariant1SurfaceGeometry


class EntityListResultEntitiesItemVariant2SurfaceGeometryCylinder(TypedDict):
    axis_point_mm: List[float]
    axis_direction: List[float]
    radius_mm: float


class EntityListResultEntitiesItemVariant2SurfaceGeometry(TypedDict):
    available: Literal[True]
    coordinate_system: Literal['part-model']
    boundary: Literal['untrimmed-surface']
    face_normal_opposes_surface: bool
    cylinder: EntityListResultEntitiesItemVariant2SurfaceGeometryCylinder


class EntityListResultEntitiesItemVariant2(TypedDict):
    entity_id: str
    kind: Literal['face']
    surface_kind: Literal['cylinder']
    area_mm2: float
    area_accuracy: Literal['approximate']
    surface_geometry: EntityListResultEntitiesItemVariant2SurfaceGeometry


class EntityListResultEntitiesItemVariant3SurfaceGeometry(TypedDict):
    available: Literal[False]
    reason: Literal['unsupported-surface-kind']


class EntityListResultEntitiesItemVariant3(TypedDict):
    entity_id: str
    kind: Literal['face']
    surface_kind: Literal['unclassified']
    area_mm2: float
    area_accuracy: Literal['approximate']
    surface_geometry: EntityListResultEntitiesItemVariant3SurfaceGeometry


class EntityListResultEntitiesItemVariant4ParameterData(TypedDict):
    coordinate_system: Literal['part-model']
    interpretation: Literal['native-edge-parameter-data']
    start_point_mm: List[float]
    end_point_mm: List[float]
    u_min_native: float
    u_max_native: float
    curve_and_edge_same_direction: bool
    curve_type: Literal[3001]


class EntityListResultEntitiesItemVariant4CurveGeometryLine(TypedDict):
    root_point_mm: List[float]
    direction: List[float]


class EntityListResultEntitiesItemVariant4CurveGeometry(TypedDict):
    available: Literal[True]
    coordinate_system: Literal['part-model']
    boundary: Literal['untrimmed-curve']
    line: EntityListResultEntitiesItemVariant4CurveGeometryLine


class EntityListResultEntitiesItemVariant4(TypedDict):
    entity_id: str
    kind: Literal['edge']
    curve_kind: Literal['line']
    parameter_data: EntityListResultEntitiesItemVariant4ParameterData
    curve_geometry: EntityListResultEntitiesItemVariant4CurveGeometry


class EntityListResultEntitiesItemVariant5ParameterData(TypedDict):
    coordinate_system: Literal['part-model']
    interpretation: Literal['native-edge-parameter-data']
    start_point_mm: List[float]
    end_point_mm: List[float]
    u_min_native: float
    u_max_native: float
    curve_and_edge_same_direction: bool
    curve_type: Literal[3002]


class EntityListResultEntitiesItemVariant5CurveGeometryCircle(TypedDict):
    center_mm: List[float]
    axis_direction: List[float]
    radius_mm: float


class EntityListResultEntitiesItemVariant5CurveGeometry(TypedDict):
    available: Literal[True]
    coordinate_system: Literal['part-model']
    boundary: Literal['untrimmed-curve']
    circle: EntityListResultEntitiesItemVariant5CurveGeometryCircle


class EntityListResultEntitiesItemVariant5(TypedDict):
    entity_id: str
    kind: Literal['edge']
    curve_kind: Literal['circle']
    parameter_data: EntityListResultEntitiesItemVariant5ParameterData
    curve_geometry: EntityListResultEntitiesItemVariant5CurveGeometry


class EntityListResultEntitiesItemVariant6ParameterData(TypedDict):
    coordinate_system: Literal['part-model']
    interpretation: Literal['native-edge-parameter-data']
    start_point_mm: List[float]
    end_point_mm: List[float]
    u_min_native: float
    u_max_native: float
    curve_and_edge_same_direction: bool
    curve_type: int


class EntityListResultEntitiesItemVariant6CurveGeometry(TypedDict):
    available: Literal[False]
    reason: Literal['unsupported-curve-kind']


class EntityListResultEntitiesItemVariant6(TypedDict):
    entity_id: str
    kind: Literal['edge']
    curve_kind: Literal['unclassified']
    parameter_data: EntityListResultEntitiesItemVariant6ParameterData
    curve_geometry: EntityListResultEntitiesItemVariant6CurveGeometry


class _EntityListResultRequired(TypedDict):
    ok: bool
    action: Literal['entity.list']


class EntityListResult(_EntityListResultRequired, total=False):
    document: DocumentState
    session_id: str
    warnings: List[DocumentCreateResultWarningsItem]
    error: DocumentCreateResultError
    scope: Literal['single-solid-part-faces', 'single-solid-part-edges']
    body_count: Literal[1]
    face_count: int
    edge_count: int
    observation: FeatureListResultObservation
    entities: List[Union[EntityListResultEntitiesItemVariant1, EntityListResultEntitiesItemVariant2, EntityListResultEntitiesItemVariant3, EntityListResultEntitiesItemVariant4, EntityListResultEntitiesItemVariant5, EntityListResultEntitiesItemVariant6]]


class _EntityInspectParametersRequired(TypedDict):
    entity_id: str


class EntityInspectParameters(_EntityInspectParametersRequired, total=False):
    kind: Literal['face', 'edge']


class _EntityInspectResultRequired(TypedDict):
    ok: bool
    action: Literal['entity.inspect']


class EntityInspectResult(_EntityInspectResultRequired, total=False):
    document: DocumentState
    session_id: str
    warnings: List[DocumentCreateResultWarningsItem]
    error: DocumentCreateResultError
    scope: Literal['single-solid-part-faces', 'single-solid-part-edges']
    body_count: Literal[1]
    face_count: int
    edge_count: int
    observation: FeatureListResultObservation
    entity: Union[EntityListResultEntitiesItemVariant1, EntityListResultEntitiesItemVariant2, EntityListResultEntitiesItemVariant3, EntityListResultEntitiesItemVariant4, EntityListResultEntitiesItemVariant5, EntityListResultEntitiesItemVariant6]


class FeatureInspectParameters(TypedDict):
    feature_id: str


class FeatureInspectResultDefinitionVariant1(TypedDict):
    depth_mm: float
    end_condition: int
    reverse_direction: bool
    both_directions: bool
    thin: bool
    from_type: int
    forward_draft: bool
    reverse_draft: bool
    merge: bool


class FeatureInspectResultDefinitionVariant2(TypedDict):
    depth_mm: float
    end_condition: int
    reverse_direction: bool
    both_directions: bool
    thin: bool
    from_type: int
    forward_draft: bool
    reverse_draft: bool
    feature_scope: bool


class _FeatureInspectResultRequired(TypedDict):
    ok: bool
    action: Literal['feature.inspect']


class FeatureInspectResult(_FeatureInspectResultRequired, total=False):
    document: DocumentState
    session_id: str
    warnings: List[DocumentCreateResultWarningsItem]
    error: DocumentCreateResultError
    feature: FeatureListResultFeaturesItem
    definition: Union[FeatureInspectResultDefinitionVariant1, FeatureInspectResultDefinitionVariant2]
    observation: FeatureListResultObservation


class FeatureSetDepthParameters(TypedDict):
    feature_id: str
    depth_mm: float


class FeatureSetDepthResultMutation(TypedDict):
    staging_attempted: bool
    configuration_scope_applied: bool
    commit_attempted: bool
    committed: bool


class FeatureSetDepthResultMeasurementBefore(TypedDict):
    solid_body_count: Literal[1]
    volume_mm3: float
    surface_area_mm2: float
    centroid_mm: AssemblyAddComponentResultPlacementRequestedCenter


class FeatureSetDepthResultVerification(TypedDict):
    passed: bool
    method: Literal['guarded-equal-depth', 'native-blind-depth-preserved-profile-and-scope']
    absolute_tolerance_mm: float


class FeatureSetDepthResultSelectionChecksPreflightSelectionAccess(TypedDict):
    attempted: bool
    acquired: bool
    release_attempted: bool
    released: bool
    state_restored: bool


class _FeatureSetDepthResultSelectionChecksPreflightObservationRequired(TypedDict):
    before: FeatureListResultObservationBefore


class FeatureSetDepthResultSelectionChecksPreflightObservation(_FeatureSetDepthResultSelectionChecksPreflightObservationRequired, total=False):
    after: FeatureListResultObservationBefore
    update_stamp_changed: bool


class _FeatureSetDepthResultSelectionChecksPreflightRequired(TypedDict):
    ok: bool
    selection_access: FeatureSetDepthResultSelectionChecksPreflightSelectionAccess


class FeatureSetDepthResultSelectionChecksPreflight(_FeatureSetDepthResultSelectionChecksPreflightRequired, total=False):
    observation: FeatureSetDepthResultSelectionChecksPreflightObservation
    error: DocumentCreateResultError
    warnings: List[DocumentCreateResultWarningsItem]


class FeatureSetDepthResultSelectionChecks(TypedDict, total=False):
    preflight: FeatureSetDepthResultSelectionChecksPreflight
    postflight: FeatureSetDepthResultSelectionChecksPreflight


class _FeatureSetDepthResultRequired(TypedDict):
    ok: bool
    action: Literal['feature.set-depth']
    feature_id: str
    mutation: FeatureSetDepthResultMutation


class FeatureSetDepthResult(_FeatureSetDepthResultRequired, total=False):
    document: DocumentState
    session_id: str
    warnings: List[DocumentCreateResultWarningsItem]
    error: DocumentCreateResultError
    feature: FeatureListResultFeaturesItem
    requested_depth_mm: float
    before_depth_mm: float
    depth_changed: Union[bool, None]
    modification_may_have_happened: bool
    definition_after: Union[FeatureInspectResultDefinitionVariant1, FeatureInspectResultDefinitionVariant2]
    measurement_before: FeatureSetDepthResultMeasurementBefore
    measurement_after: FeatureSetDepthResultMeasurementBefore
    final_state: FeatureListResultObservationBefore
    rebuilt: bool
    verification: FeatureSetDepthResultVerification
    selection_checks: FeatureSetDepthResultSelectionChecks


class _SketchInspectParametersRequired(TypedDict):
    sketch_id: str


class SketchInspectParameters(_SketchInspectParametersRequired, total=False):
    max_segments: int


class SketchInspectResultSegmentsItemGeometryVariant2(TypedDict):
    kind: Literal['line']
    start_mm: AssemblyAddComponentResultPlacementRequestedCenter
    end_mm: AssemblyAddComponentResultPlacementRequestedCenter


class _SketchInspectResultSegmentsItemGeometryVariant3Required(TypedDict):
    kind: Literal['arc']
    complete_circle: bool
    radius_mm: float
    center_mm: AssemblyAddComponentResultPlacementRequestedCenter


class SketchInspectResultSegmentsItemGeometryVariant3(_SketchInspectResultSegmentsItemGeometryVariant3Required, total=False):
    start_mm: AssemblyAddComponentResultPlacementRequestedCenter
    end_mm: AssemblyAddComponentResultPlacementRequestedCenter


class SketchInspectResultSegmentsItem(TypedDict):
    index: int
    type_code: int
    construction: bool
    geometry: Union[None, SketchInspectResultSegmentsItemGeometryVariant2, SketchInspectResultSegmentsItemGeometryVariant3]


class _SketchInspectResultRequired(TypedDict):
    ok: bool
    action: Literal['sketch.inspect']


class SketchInspectResult(_SketchInspectResultRequired, total=False):
    document: DocumentState
    session_id: str
    warnings: List[DocumentCreateResultWarningsItem]
    error: DocumentCreateResultError
    sketch: SketchListResultSketchesItem
    editing: bool
    coordinate_system: Literal['sketch-local']
    unit: Literal['millimeter']
    model_to_sketch_transform: List[float]
    segments: List[SketchInspectResultSegmentsItem]
    segment_count: int
    profile_segment_count: int
    geometry_complete: bool


class _SketchRectangleParametersRequired(TypedDict):
    plane: Literal['front', 'top', 'right']
    width_mm: float
    height_mm: float


class SketchRectangleParameters(_SketchRectangleParametersRequired, total=False):
    center_x_mm: float
    center_y_mm: float


class SketchRectangleResultDimensions(TypedDict):
    unit: Literal['millimeter']
    width: float
    height: float
    center_x: float
    center_y: float


class _SketchRectangleResultSketchRequired(TypedDict):
    name: str
    type: Literal['ProfileFeature']
    constraint_status: int
    dimensions_created: Literal[False]


class SketchRectangleResultSketch(_SketchRectangleResultSketchRequired, total=False):
    sketch_id: str


class SketchRectangleResultGeometryVerificationActualBoundsMmVariant1(TypedDict):
    min_x: float
    max_x: float
    min_y: float
    max_y: float


class SketchRectangleResultGeometryVerification(TypedDict):
    passed: bool
    method: Literal['sketch-local-line-bounds']
    segment_count: int
    profile_segment_count: int
    actual_bounds_mm: Union[SketchRectangleResultGeometryVerificationActualBoundsMmVariant1, None]
    absolute_tolerance_mm: float


class _SketchRectangleResultRequired(TypedDict):
    ok: bool
    action: Literal['sketch.rectangle']


class SketchRectangleResult(_SketchRectangleResultRequired, total=False):
    document: DocumentState
    session_id: str
    warnings: List[DocumentCreateResultWarningsItem]
    error: DocumentCreateResultError
    plane: Literal['front', 'top', 'right']
    coordinate_system: Literal['sketch-local']
    model_to_sketch_transform: List[float]
    dimensions: SketchRectangleResultDimensions
    sketch: SketchRectangleResultSketch
    geometry_verification: SketchRectangleResultGeometryVerification
    editing: bool


class SketchPolygonParametersVerticesMmItem(TypedDict):
    x: float
    y: float


class SketchPolygonParameters(TypedDict):
    plane: Literal['front', 'top', 'right']
    vertices_mm: List[SketchPolygonParametersVerticesMmItem]


class SketchPolygonResultDimensions(TypedDict):
    unit: Literal['millimeter']
    vertices_mm: List[SketchPolygonParametersVerticesMmItem]


class _SketchPolygonResultSketchRequired(TypedDict):
    sketch_id: str


class SketchPolygonResultSketch(_SketchPolygonResultSketchRequired, total=False):
    name: str
    type: Literal['ProfileFeature']
    constraint_status: int
    dimensions_created: Literal[False]


class SketchPolygonResultGeometryVerification(TypedDict):
    passed: bool
    method: Literal['sketch-local-polygon-edge-cycle']
    segment_count: int
    vertex_count: int
    contour_count: Literal[1]
    native_closed: Literal[True]
    actual_vertices_mm: List[SketchPolygonParametersVerticesMmItem]
    signed_area_mm2: float
    perimeter_mm: float
    centroid_mm: SketchPolygonParametersVerticesMmItem
    absolute_tolerance_mm: float


class _SketchPolygonResultRequired(TypedDict):
    ok: bool
    action: Literal['sketch.polygon']


class SketchPolygonResult(_SketchPolygonResultRequired, total=False):
    document: DocumentState
    session_id: str
    warnings: List[DocumentCreateResultWarningsItem]
    error: DocumentCreateResultError
    plane: Literal['front', 'top', 'right']
    coordinate_system: Literal['sketch-local']
    model_to_sketch_transform: List[float]
    dimensions: SketchPolygonResultDimensions
    sketch: SketchPolygonResultSketch
    geometry_verification: SketchPolygonResultGeometryVerification
    editing: bool


class _SketchCircleParametersRequired(TypedDict):
    plane: Literal['front', 'top', 'right']
    radius_mm: float


class SketchCircleParameters(_SketchCircleParametersRequired, total=False):
    center_x_mm: float
    center_y_mm: float


class SketchCircleResultDimensions(TypedDict):
    unit: Literal['millimeter']
    radius: float
    center_x: float
    center_y: float


class SketchCircleResultGeometryVerification(TypedDict):
    passed: bool
    method: Literal['sketch-local-circle']
    segment_count: int
    profile_segment_count: int
    complete_circle: bool
    actual_radius_mm: Union[float, None]
    actual_center_mm: Union[AssemblyAddComponentResultPlacementRequestedCenter, None]
    absolute_tolerance_mm: float


class _SketchCircleResultRequired(TypedDict):
    ok: bool
    action: Literal['sketch.circle']


class SketchCircleResult(_SketchCircleResultRequired, total=False):
    document: DocumentState
    session_id: str
    warnings: List[DocumentCreateResultWarningsItem]
    error: DocumentCreateResultError
    plane: Literal['front', 'top', 'right']
    coordinate_system: Literal['sketch-local']
    model_to_sketch_transform: List[float]
    dimensions: SketchCircleResultDimensions
    sketch: SketchRectangleResultSketch
    geometry_verification: SketchCircleResultGeometryVerification
    editing: bool


class SketchFixCenterParameters(TypedDict):
    sketch_id: str


class SketchFixCenterResultCenterBeforeGeometry(TypedDict):
    width_mm: float
    height_mm: float
    center_mm: AssemblyAddComponentResultPlacementRequestedCenter
    bounds_mm: List[float]
    profile_segment_count: Literal[4]
    construction_segment_count: Literal[2]
    max_abs_z_mm: float


class SketchFixCenterResultCenterBefore(TypedDict):
    method: Literal['sketch-local-center-relations']
    attached_to_both_diagonals: Literal[True]
    fixed: bool
    native_point_id: List[int]
    native_diagonal_ids: List[List[int]]
    identity_scope: Literal['exact-sketch-and-entity-kind-snapshot']
    geometry: SketchFixCenterResultCenterBeforeGeometry


class SketchFixCenterResultGeometryVerification(TypedDict):
    method: Literal['sketch-local-rectangle']
    passed: bool
    size_matched: bool
    center_preserved: bool
    expected_width_mm: float
    expected_height_mm: float
    expected_center_mm: AssemblyAddComponentResultPlacementRequestedCenter
    actual: SketchFixCenterResultCenterBeforeGeometry
    absolute_tolerance_mm: float


class _SketchFixCenterResultRequired(TypedDict):
    ok: bool
    action: Literal['sketch.fix-center']


class SketchFixCenterResult(_SketchFixCenterResultRequired, total=False):
    document: DocumentState
    session_id: str
    warnings: List[DocumentCreateResultWarningsItem]
    error: DocumentCreateResultError
    sketch_id: str
    created: bool
    center_before: SketchFixCenterResultCenterBefore
    center_in_edit: SketchFixCenterResultCenterBefore
    center: SketchFixCenterResultCenterBefore
    constraint_status_before: Literal[2, 3]
    constraint_status: Literal[2, 3]
    editing: bool
    modification_may_have_happened: Literal[True]
    geometry_verification: SketchFixCenterResultGeometryVerification


class SketchDimensionDiameterParameters(TypedDict):
    sketch_id: str
    diameter_mm: float


class SketchDimensionDiameterResultDimension(TypedDict, total=False):
    dimension_id: str
    sketch_id: str
    kind: Literal['diameter']
    unit: Literal['millimeter']
    value: Union[float, None]
    driven_state: int
    read_only: bool
    configuration: str
    native_name: str


class _SketchDimensionDiameterResultRequired(TypedDict):
    ok: bool
    action: Literal['sketch.dimension-diameter']


class SketchDimensionDiameterResult(_SketchDimensionDiameterResultRequired, total=False):
    document: DocumentState
    session_id: str
    warnings: List[DocumentCreateResultWarningsItem]
    error: DocumentCreateResultError
    sketch_id: str
    diameter_mm: float
    dimension: SketchDimensionDiameterResultDimension
    native_status: int
    geometry_verification: SketchCircleResultGeometryVerification
    constraint_status: int
    editing: bool


class SketchDimensionRectangleParameters(TypedDict):
    sketch_id: str
    width_mm: float
    height_mm: float


class SketchDimensionRectangleResultDimensionsWidth(TypedDict, total=False):
    dimension_id: str
    sketch_id: str
    kind: Literal['width']
    unit: Literal['millimeter']
    value: Union[float, None]
    driven_state: int
    read_only: bool
    configuration: str
    native_name: str


class SketchDimensionRectangleResultDimensionsHeight(TypedDict, total=False):
    dimension_id: str
    sketch_id: str
    kind: Literal['height']
    unit: Literal['millimeter']
    value: Union[float, None]
    driven_state: int
    read_only: bool
    configuration: str
    native_name: str


class SketchDimensionRectangleResultDimensions(TypedDict, total=False):
    width: SketchDimensionRectangleResultDimensionsWidth
    height: SketchDimensionRectangleResultDimensionsHeight


class SketchDimensionRectangleResultNativeStatus(TypedDict, total=False):
    width: int
    height: int


class SketchDimensionRectangleResultGeometryBefore(TypedDict):
    width_mm: float
    height_mm: float
    center_mm: AssemblyAddComponentResultPlacementRequestedCenter
    bounds_mm: List[float]
    profile_segment_count: Literal[4]
    construction_segment_count: int
    max_abs_z_mm: float


class SketchDimensionRectangleResultStepsWidth(TypedDict):
    method: Literal['sketch-local-rectangle']
    passed: bool
    size_matched: bool
    center_preserved: bool
    expected_width_mm: float
    expected_height_mm: float
    expected_center_mm: AssemblyAddComponentResultPlacementRequestedCenter
    actual: SketchDimensionRectangleResultGeometryBefore
    absolute_tolerance_mm: float


class SketchDimensionRectangleResultSteps(TypedDict, total=False):
    width: SketchDimensionRectangleResultStepsWidth
    height: SketchDimensionRectangleResultStepsWidth


class _SketchDimensionRectangleResultRequired(TypedDict):
    ok: bool
    action: Literal['sketch.dimension-rectangle']


class SketchDimensionRectangleResult(_SketchDimensionRectangleResultRequired, total=False):
    document: DocumentState
    session_id: str
    warnings: List[DocumentCreateResultWarningsItem]
    error: DocumentCreateResultError
    sketch_id: str
    dimensions: SketchDimensionRectangleResultDimensions
    native_status: SketchDimensionRectangleResultNativeStatus
    geometry_before: SketchDimensionRectangleResultGeometryBefore
    steps: SketchDimensionRectangleResultSteps
    geometry_verification: SketchDimensionRectangleResultStepsWidth
    constraint_status: int
    editing: bool
    modification_may_have_happened: Literal[True]


class DimensionDiscoverDiameterParameters(TypedDict):
    sketch_id: str


class DimensionDiscoverDiameterResultEquationControl(TypedDict):
    controlled: bool
    equation_indices: List[int]


class DimensionDiscoverDiameterResultObservationBefore(TypedDict):
    update_stamp: int
    configuration: str
    editing: bool


class DimensionDiscoverDiameterResultObservation(TypedDict, total=False):
    before: DimensionDiscoverDiameterResultObservationBefore
    after: DimensionDiscoverDiameterResultObservationBefore
    configuration_matched: bool
    unchanged: bool


class _DimensionDiscoverDiameterResultRequired(TypedDict):
    ok: bool
    action: Literal['dimension.discover-diameter']


class DimensionDiscoverDiameterResult(_DimensionDiscoverDiameterResultRequired, total=False):
    document: DocumentState
    session_id: str
    warnings: List[DocumentCreateResultWarningsItem]
    error: DocumentCreateResultError
    sketch_id: str
    dimension: SketchDimensionDiameterResultDimension
    geometry_verification: SketchCircleResultGeometryVerification
    constraint_status: int
    editing: bool
    equation_control: DimensionDiscoverDiameterResultEquationControl
    design_table_controlled: bool
    observation: DimensionDiscoverDiameterResultObservation


DimensionDiscoverRectangleParameters = DimensionDiscoverDiameterParameters


class DimensionDiscoverRectangleResultInspectionsWidthDimension(TypedDict, total=False):
    kind: Literal['width']
    unit: Literal['millimeter']
    value: Union[float, None]
    driven_state: int
    read_only: bool
    configuration: str
    native_name: str


class DimensionDiscoverRectangleResultInspectionsWidthGeometryVerification(TypedDict):
    method: Literal['sketch-local-rectangle']
    passed: bool
    dimension_kind: Literal['width', 'height']
    expected_value_mm: float
    actual_width_mm: float
    actual_height_mm: float
    actual_center_mm: AssemblyAddComponentResultPlacementRequestedCenter
    bounds_mm: List[float]
    profile_segment_count: Literal[4]
    construction_segment_count: int
    max_abs_z_mm: float
    absolute_tolerance_mm: float


class _DimensionDiscoverRectangleResultInspectionsWidthRequired(TypedDict):
    ok: bool
    action: Literal['dimension.inspect']


class DimensionDiscoverRectangleResultInspectionsWidth(_DimensionDiscoverRectangleResultInspectionsWidthRequired, total=False):
    document: DocumentState
    session_id: str
    warnings: List[DocumentCreateResultWarningsItem]
    error: DocumentCreateResultError
    sketch_id: str
    dimension: DimensionDiscoverRectangleResultInspectionsWidthDimension
    geometry_verification: DimensionDiscoverRectangleResultInspectionsWidthGeometryVerification
    constraint_status: int
    editing: bool
    equation_control: DimensionDiscoverDiameterResultEquationControl
    design_table_controlled: bool
    modification_may_have_happened: Literal[True]
    observation: DimensionDiscoverDiameterResultObservation


class DimensionDiscoverRectangleResultInspectionsHeightDimension(TypedDict, total=False):
    kind: Literal['height']
    unit: Literal['millimeter']
    value: Union[float, None]
    driven_state: int
    read_only: bool
    configuration: str
    native_name: str


class _DimensionDiscoverRectangleResultInspectionsHeightRequired(TypedDict):
    ok: bool
    action: Literal['dimension.inspect']


class DimensionDiscoverRectangleResultInspectionsHeight(_DimensionDiscoverRectangleResultInspectionsHeightRequired, total=False):
    document: DocumentState
    session_id: str
    warnings: List[DocumentCreateResultWarningsItem]
    error: DocumentCreateResultError
    sketch_id: str
    dimension: DimensionDiscoverRectangleResultInspectionsHeightDimension
    geometry_verification: DimensionDiscoverRectangleResultInspectionsWidthGeometryVerification
    constraint_status: int
    editing: bool
    equation_control: DimensionDiscoverDiameterResultEquationControl
    design_table_controlled: bool
    modification_may_have_happened: Literal[True]
    observation: DimensionDiscoverDiameterResultObservation


class DimensionDiscoverRectangleResultInspections(TypedDict, total=False):
    width: DimensionDiscoverRectangleResultInspectionsWidth
    height: DimensionDiscoverRectangleResultInspectionsHeight


class _DimensionDiscoverRectangleResultRequired(TypedDict):
    ok: bool
    action: Literal['dimension.discover-rectangle']


class DimensionDiscoverRectangleResult(_DimensionDiscoverRectangleResultRequired, total=False):
    document: DocumentState
    session_id: str
    warnings: List[DocumentCreateResultWarningsItem]
    error: DocumentCreateResultError
    sketch_id: str
    dimensions: SketchDimensionRectangleResultDimensions
    geometry_verification: SketchDimensionRectangleResultStepsWidth
    constraint_status: int
    editing: bool
    observation: DimensionDiscoverDiameterResultObservation
    inspections: DimensionDiscoverRectangleResultInspections


class DimensionInspectParameters(TypedDict):
    dimension_id: str


class DimensionInspectResultDimension(TypedDict, total=False):
    dimension_id: str
    sketch_id: str
    kind: Literal['diameter', 'width', 'height']
    unit: Literal['millimeter']
    value: Union[float, None]
    driven_state: int
    read_only: bool
    configuration: str
    native_name: str


class _DimensionInspectResultRequired(TypedDict):
    ok: bool
    action: Literal['dimension.inspect']


class DimensionInspectResult(_DimensionInspectResultRequired, total=False):
    document: DocumentState
    session_id: str
    warnings: List[DocumentCreateResultWarningsItem]
    error: DocumentCreateResultError
    sketch_id: str
    dimension: DimensionInspectResultDimension
    geometry_verification: Union[SketchCircleResultGeometryVerification, DimensionDiscoverRectangleResultInspectionsWidthGeometryVerification]
    constraint_status: int
    editing: bool
    equation_control: DimensionDiscoverDiameterResultEquationControl
    design_table_controlled: bool
    modification_may_have_happened: Literal[True]
    observation: DimensionDiscoverDiameterResultObservation


class DimensionSetParameters(TypedDict):
    dimension_id: str
    value_mm: float


class DimensionSetResultDownstream(TypedDict):
    applicable: bool
    measurement_before: Union[DocumentMeasureResultMetrics, None]
    measurement_after: Union[DocumentMeasureResultMetrics, None]


class DimensionSetResultBeforeDimension(TypedDict, total=False):
    dimension_id: str
    sketch_id: str
    kind: Literal['width', 'height']
    unit: Literal['millimeter']
    value: Union[float, None]
    driven_state: int
    read_only: bool
    configuration: str
    native_name: str


class _DimensionSetResultBeforeRequired(TypedDict):
    ok: bool
    action: Literal['dimension.inspect']


class DimensionSetResultBefore(_DimensionSetResultBeforeRequired, total=False):
    document: DocumentState
    session_id: str
    warnings: List[DocumentCreateResultWarningsItem]
    error: DocumentCreateResultError
    sketch_id: str
    dimension: DimensionSetResultBeforeDimension
    geometry_verification: DimensionDiscoverRectangleResultInspectionsWidthGeometryVerification
    constraint_status: int
    editing: bool
    equation_control: DimensionDiscoverDiameterResultEquationControl
    design_table_controlled: bool
    modification_may_have_happened: Literal[True]
    observation: DimensionDiscoverDiameterResultObservation


class _DimensionSetResultRequired(TypedDict):
    ok: bool
    action: Literal['dimension.set']


class DimensionSetResult(_DimensionSetResultRequired, total=False):
    document: DocumentState
    session_id: str
    warnings: List[DocumentCreateResultWarningsItem]
    error: DocumentCreateResultError
    sketch_id: str
    dimension: DimensionInspectResultDimension
    value_mm: float
    before_value_mm: Union[float, None]
    native_status: int
    geometry_verification: Union[SketchCircleResultGeometryVerification, SketchDimensionRectangleResultStepsWidth]
    constraint_status: int
    editing: bool
    rebuilt: bool
    needs_rebuild: int
    diagnostics: DocumentCreateResultDiagnostics
    downstream: DimensionSetResultDownstream
    equation_control: DimensionDiscoverDiameterResultEquationControl
    design_table_controlled: bool
    modification_may_have_happened: Literal[True]
    before: DimensionSetResultBefore
    after: DimensionSetResultBefore
    final_state: DimensionDiscoverDiameterResultObservationBefore


class FeatureFilletParameters(TypedDict):
    entity_id: str
    radius_mm: float


class FeatureFilletResultMutation(TypedDict):
    attempted: bool
    creation_returned: bool
    may_have_changed: bool


class FeatureFilletResultFeature(TypedDict, total=False):
    name: str
    type: str
    feature_id: str


class FeatureFilletResultVerification(TypedDict, total=False):
    passed: bool
    radius_mm: float
    edge_count: int
    profile: Literal['circular']
    tangent_propagation: bool


class _FeatureFilletResultRequired(TypedDict):
    ok: bool
    action: Literal['feature.fillet']
    entity_id: str


class FeatureFilletResult(_FeatureFilletResultRequired, total=False):
    document: DocumentState
    session_id: str
    warnings: List[DocumentCreateResultWarningsItem]
    error: DocumentCreateResultError
    radius_mm: float
    mutation: FeatureFilletResultMutation
    feature: FeatureFilletResultFeature
    verification: FeatureFilletResultVerification
    rebuilt: bool
    diagnostics: DocumentCreateResultDiagnostics
    bodies: int
    before_volume_mm3: float
    after_volume_mm3: float
    cleanup_errors: List[DocumentCreateResultCleanupErrorsItem]


class _FeatureExtrudeParametersRequired(TypedDict):
    sketch_id: str
    depth_mm: float


class FeatureExtrudeParameters(_FeatureExtrudeParametersRequired, total=False):
    reverse: bool
    merge: bool


class _FeatureExtrudeResultFeatureRequired(TypedDict):
    name: str
    type: str


class FeatureExtrudeResultFeature(_FeatureExtrudeResultFeatureRequired, total=False):
    feature_id: str


class FeatureExtrudeResultGeometryVerification(TypedDict):
    passed: bool
    method: Literal['native-extrusion-definition']
    actual_depth_mm: float
    actual_reverse: bool
    actual_merge: bool
    end_condition: int
    both_directions: bool
    solid_body_count: int
    absolute_tolerance_mm: float


class _FeatureExtrudeResultRequired(TypedDict):
    ok: bool
    action: Literal['feature.extrude']


class FeatureExtrudeResult(_FeatureExtrudeResultRequired, total=False):
    document: DocumentState
    session_id: str
    warnings: List[DocumentCreateResultWarningsItem]
    error: DocumentCreateResultError
    sketch_id: str
    depth_mm: float
    reverse: bool
    merge: bool
    feature: FeatureExtrudeResultFeature
    rebuilt: bool
    diagnostics: DocumentCreateResultDiagnostics
    bodies: DocumentInspectResultStructureBodies
    geometry_verification: FeatureExtrudeResultGeometryVerification


class _FeatureCutExtrudeParametersRequired(TypedDict):
    sketch_id: str


class FeatureCutExtrudeParameters(_FeatureCutExtrudeParametersRequired, total=False):
    end_condition: Literal['blind', 'through-all']
    depth_mm: float
    reverse: bool


class FeatureCutExtrudeResultGeometryVerification(TypedDict):
    passed: bool
    method: Literal['native-cut-definition-and-volume']
    actual_depth_mm: Union[float, None]
    actual_reverse: bool
    native_reverse_direction: bool
    end_condition: int
    both_directions: bool
    volume_removed_mm3: float
    minimum_volume_change_mm3: float
    absolute_depth_tolerance_mm: Union[float, None]


class FeatureCutExtrudeResultThroughAllSettings(TypedDict, total=False):
    thin: bool
    feature_scope: bool
    from_type: int
    forward_draft: bool
    needs_rebuild: int


class _FeatureCutExtrudeResultRequired(TypedDict):
    ok: bool
    action: Literal['feature.cut-extrude']


class FeatureCutExtrudeResult(_FeatureCutExtrudeResultRequired, total=False):
    document: DocumentState
    session_id: str
    warnings: List[DocumentCreateResultWarningsItem]
    error: DocumentCreateResultError
    sketch_id: str
    depth_mm: Union[float, None]
    reverse: bool
    feature: FeatureExtrudeResultFeature
    rebuilt: bool
    diagnostics: DocumentCreateResultDiagnostics
    bodies: DocumentInspectResultStructureBodies
    geometry_verification: FeatureCutExtrudeResultGeometryVerification
    end_condition: Literal['blind', 'through-all']
    through_all_settings: FeatureCutExtrudeResultThroughAllSettings
    affected_scope: Literal['all-solid-bodies']
    measurement_before: DocumentMeasureResultMetrics
    measurement_after: DocumentMeasureResultMetrics


class _PartCreateBoxParametersRequired(TypedDict):
    output: str
    width_mm: float
    height_mm: float
    depth_mm: float


class PartCreateBoxParameters(_PartCreateBoxParametersRequired, total=False):
    template: str
    overwrite: bool


class PartCreateBoxResultDimensions(TypedDict):
    unit: Literal['millimeter']
    width: float
    height: float
    depth: float


class PartCreateBoxResultGeometryVerification(TypedDict):
    passed: bool
    method: str
    expected_size_mm: AssemblyAddComponentResultPlacementRequestedCenter
    actual_size_mm: Union[AssemblyAddComponentResultPlacementRequestedCenter, None]
    absolute_tolerance_mm: float
    note: str


class _PartCreateBoxResultRequired(TypedDict):
    ok: bool
    action: Literal['part.create-box']


class PartCreateBoxResult(_PartCreateBoxResultRequired, total=False):
    document: DocumentState
    session_id: str
    warnings: List[DocumentCreateResultWarningsItem]
    error: DocumentCreateResultError
    output: str
    dimensions: PartCreateBoxResultDimensions
    template: DocumentCreateResultTemplate
    rebuilt: bool
    diagnostics: DocumentCreateResultDiagnostics
    bodies: DocumentInspectResultStructureBodies
    geometry_verification: PartCreateBoxResultGeometryVerification
    save_errors: int
    save_warnings: Union[int, None]
    saved: bool
    feature: SketchListResultSketchesItemOwnerVariant2


class _WorkspaceUploadBeginParametersRequired(TypedDict):
    path: str
    size_bytes: int
    sha256: str


class WorkspaceUploadBeginParameters(_WorkspaceUploadBeginParametersRequired, total=False):
    overwrite: bool


class WorkspaceUploadBeginResult(TypedDict):
    transfer_id: str
    path: str
    size_bytes: int
    sha256: str
    offset: int
    chunk_bytes: int
    state: Literal['uploading', 'committed', 'aborted', 'failed', 'downloading', 'closed']


class WorkspaceUploadChunkParameters(TypedDict):
    transfer_id: str
    offset: int
    data: str


WorkspaceUploadChunkResult = WorkspaceUploadBeginResult


class WorkspaceUploadStatusParameters(TypedDict):
    transfer_id: str


WorkspaceUploadStatusResult = WorkspaceUploadBeginResult


WorkspaceUploadCommitParameters = WorkspaceUploadStatusParameters


WorkspaceUploadCommitResult = WorkspaceUploadBeginResult


WorkspaceUploadAbortParameters = WorkspaceUploadStatusParameters


WorkspaceUploadAbortResult = WorkspaceUploadBeginResult


class WorkspaceDownloadBeginParameters(TypedDict):
    path: str


WorkspaceDownloadBeginResult = WorkspaceUploadBeginResult


class WorkspaceDownloadChunkParameters(TypedDict):
    transfer_id: str
    offset: int
    length: int


class WorkspaceDownloadChunkResult(TypedDict):
    transfer_id: str
    path: str
    size_bytes: int
    sha256: str
    offset: int
    chunk_bytes: int
    state: Literal['uploading', 'committed', 'aborted', 'failed', 'downloading', 'closed']
    data: str


WorkspaceDownloadEndParameters = WorkspaceUploadStatusParameters


WorkspaceDownloadEndResult = WorkspaceUploadBeginResult
