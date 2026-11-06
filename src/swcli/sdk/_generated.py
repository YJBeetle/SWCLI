"""Generated typed operation methods; regenerate from the public catalog."""
from __future__ import annotations

from typing import Dict, List, Literal, Optional, Protocol, Union, cast
from . import models
from .runtime import JSONValue, Response, UNSET, Unset


class Dispatcher(Protocol):
    def _execute(self, operation: str, parameters: Optional[Dict[str, object]] = None, *, request_id: Optional[str] = None, document_id: Optional[str] = None, expected_update_stamp: Optional[int] = None, lease_id: Optional[str] = None) -> Response[JSONValue]: ...


class DocumentLeaseOperations:
    def __init__(self, client: Dispatcher) -> None:
        self._client = client

    def acquire(self, *, ttl_seconds: Union[float, Unset] = UNSET, document_id: Optional[str] = None, request_id: Optional[str] = None) -> Response[models.DocumentLeaseAcquireResult]:
        """document.lease.acquire; runtime validation enforces bounds, conditions and context."""
        parameters: Dict[str, object] = {}
        if ttl_seconds is not UNSET:
            parameters['ttl_seconds'] = ttl_seconds
        return cast("Response[models.DocumentLeaseAcquireResult]", self._client._execute('document.lease.acquire', parameters, request_id=request_id, document_id=document_id))


    def status(self, *, document_id: Optional[str] = None, request_id: Optional[str] = None) -> Response[models.DocumentLeaseStatusResult]:
        """document.lease.status; runtime validation enforces bounds, conditions and context."""
        parameters: Dict[str, object] = {}
        return cast("Response[models.DocumentLeaseStatusResult]", self._client._execute('document.lease.status', parameters, request_id=request_id, document_id=document_id))


    def renew(self, *, ttl_seconds: Union[float, Unset] = UNSET, lease_id: str, request_id: Optional[str] = None) -> Response[models.DocumentLeaseRenewResult]:
        """document.lease.renew; runtime validation enforces bounds, conditions and context."""
        parameters: Dict[str, object] = {}
        if ttl_seconds is not UNSET:
            parameters['ttl_seconds'] = ttl_seconds
        return cast("Response[models.DocumentLeaseRenewResult]", self._client._execute('document.lease.renew', parameters, request_id=request_id, lease_id=lease_id))


    def release(self, *, lease_id: str, request_id: Optional[str] = None) -> Response[models.DocumentLeaseReleaseResult]:
        """document.lease.release; runtime validation enforces bounds, conditions and context."""
        parameters: Dict[str, object] = {}
        return cast("Response[models.DocumentLeaseReleaseResult]", self._client._execute('document.lease.release', parameters, request_id=request_id, lease_id=lease_id))


class AssemblyOperations:
    def __init__(self, client: Dispatcher) -> None:
        self._client = client

    def add_component(self, *, path: str, configuration: Union[str, Unset] = UNSET, x_mm: Union[float, Unset] = UNSET, y_mm: Union[float, Unset] = UNSET, z_mm: Union[float, Unset] = UNSET, document_id: Optional[str] = None, expected_update_stamp: Optional[int] = None, lease_id: Optional[str] = None, request_id: Optional[str] = None) -> Response[models.AssemblyAddComponentResult]:
        """assembly.add-component; runtime validation enforces bounds, conditions and context."""
        parameters: Dict[str, object] = {}
        parameters['path'] = path
        if configuration is not UNSET:
            parameters['configuration'] = configuration
        if x_mm is not UNSET:
            parameters['x_mm'] = x_mm
        if y_mm is not UNSET:
            parameters['y_mm'] = y_mm
        if z_mm is not UNSET:
            parameters['z_mm'] = z_mm
        return cast("Response[models.AssemblyAddComponentResult]", self._client._execute('assembly.add-component', parameters, request_id=request_id, document_id=document_id, expected_update_stamp=expected_update_stamp, lease_id=lease_id))


class DaemonOperations:
    def __init__(self, client: Dispatcher) -> None:
        self._client = client

    def health(self, *, request_id: Optional[str] = None) -> Response[models.DaemonHealthResult]:
        """daemon.health; runtime validation enforces bounds, conditions and context."""
        parameters: Dict[str, object] = {}
        return cast("Response[models.DaemonHealthResult]", self._client._execute('daemon.health', parameters, request_id=request_id))


    def runtime_status(self, *, request_id: Optional[str] = None) -> Response[models.DaemonRuntimeStatusResult]:
        """daemon.runtime-status; runtime validation enforces bounds, conditions and context."""
        parameters: Dict[str, object] = {}
        return cast("Response[models.DaemonRuntimeStatusResult]", self._client._execute('daemon.runtime-status', parameters, request_id=request_id))


    def capabilities(self, *, include_schemas: Union[bool, Unset] = UNSET, operation: Union[str, Unset] = UNSET, request_id: Optional[str] = None) -> Response[models.DaemonCapabilitiesResult]:
        """daemon.capabilities; runtime validation enforces bounds, conditions and context."""
        parameters: Dict[str, object] = {}
        if include_schemas is not UNSET:
            parameters['include_schemas'] = include_schemas
        if operation is not UNSET:
            parameters['operation'] = operation
        return cast("Response[models.DaemonCapabilitiesResult]", self._client._execute('daemon.capabilities', parameters, request_id=request_id))


    def shutdown(self, *, request_id: Optional[str] = None) -> Response[models.DaemonShutdownResult]:
        """daemon.shutdown; runtime validation enforces bounds, conditions and context."""
        parameters: Dict[str, object] = {}
        return cast("Response[models.DaemonShutdownResult]", self._client._execute('daemon.shutdown', parameters, request_id=request_id))


class DimensionOperations:
    def __init__(self, client: Dispatcher) -> None:
        self._client = client

    def discover_diameter(self, *, sketch_id: str, document_id: Optional[str] = None, expected_update_stamp: Optional[int] = None, request_id: Optional[str] = None) -> Response[models.DimensionDiscoverDiameterResult]:
        """dimension.discover-diameter; runtime validation enforces bounds, conditions and context."""
        parameters: Dict[str, object] = {}
        parameters['sketch_id'] = sketch_id
        return cast("Response[models.DimensionDiscoverDiameterResult]", self._client._execute('dimension.discover-diameter', parameters, request_id=request_id, document_id=document_id, expected_update_stamp=expected_update_stamp))


    def discover_rectangle(self, *, sketch_id: str, document_id: Optional[str] = None, expected_update_stamp: Optional[int] = None, request_id: Optional[str] = None) -> Response[models.DimensionDiscoverRectangleResult]:
        """dimension.discover-rectangle; runtime validation enforces bounds, conditions and context."""
        parameters: Dict[str, object] = {}
        parameters['sketch_id'] = sketch_id
        return cast("Response[models.DimensionDiscoverRectangleResult]", self._client._execute('dimension.discover-rectangle', parameters, request_id=request_id, document_id=document_id, expected_update_stamp=expected_update_stamp))


    def inspect(self, *, dimension_id: str, document_id: Optional[str] = None, expected_update_stamp: Optional[int] = None, request_id: Optional[str] = None) -> Response[models.DimensionInspectResult]:
        """dimension.inspect; runtime validation enforces bounds, conditions and context."""
        parameters: Dict[str, object] = {}
        parameters['dimension_id'] = dimension_id
        return cast("Response[models.DimensionInspectResult]", self._client._execute('dimension.inspect', parameters, request_id=request_id, document_id=document_id, expected_update_stamp=expected_update_stamp))


    def set(self, *, dimension_id: str, value_mm: float, document_id: Optional[str] = None, expected_update_stamp: Optional[int] = None, lease_id: Optional[str] = None, request_id: Optional[str] = None) -> Response[models.DimensionSetResult]:
        """dimension.set; runtime validation enforces bounds, conditions and context."""
        parameters: Dict[str, object] = {}
        parameters['dimension_id'] = dimension_id
        parameters['value_mm'] = value_mm
        return cast("Response[models.DimensionSetResult]", self._client._execute('dimension.set', parameters, request_id=request_id, document_id=document_id, expected_update_stamp=expected_update_stamp, lease_id=lease_id))


class DocumentOperations:
    def __init__(self, client: Dispatcher) -> None:
        self._client = client
        self.lease = DocumentLeaseOperations(client)

    def create(self, *, type: Union[Literal['part', 'assembly', 'drawing'], Unset] = UNSET, template: Union[str, Unset] = UNSET, projection: Union[Literal['first-angle', 'third-angle'], Unset] = UNSET, request_id: Optional[str] = None) -> Response[models.DocumentCreateResult]:
        """document.create; runtime validation enforces bounds, conditions and context."""
        parameters: Dict[str, object] = {}
        if type is not UNSET:
            parameters['type'] = type
        if template is not UNSET:
            parameters['template'] = template
        if projection is not UNSET:
            parameters['projection'] = projection
        return cast("Response[models.DocumentCreateResult]", self._client._execute('document.create', parameters, request_id=request_id))


    def open(self, *, path: str, read_only: Union[bool, Unset] = UNSET, configuration: Union[str, Unset] = UNSET, request_id: Optional[str] = None) -> Response[models.DocumentOpenResult]:
        """document.open; runtime validation enforces bounds, conditions and context."""
        parameters: Dict[str, object] = {}
        parameters['path'] = path
        if read_only is not UNSET:
            parameters['read_only'] = read_only
        if configuration is not UNSET:
            parameters['configuration'] = configuration
        return cast("Response[models.DocumentOpenResult]", self._client._execute('document.open', parameters, request_id=request_id))


    def list(self, *, request_id: Optional[str] = None) -> Response[models.DocumentListResult]:
        """document.list; runtime validation enforces bounds, conditions and context."""
        parameters: Dict[str, object] = {}
        return cast("Response[models.DocumentListResult]", self._client._execute('document.list', parameters, request_id=request_id))


    def use(self, *, document_id: str, request_id: Optional[str] = None) -> Response[models.DocumentUseResult]:
        """document.use; runtime validation enforces bounds, conditions and context."""
        parameters: Dict[str, object] = {}
        return cast("Response[models.DocumentUseResult]", self._client._execute('document.use', parameters, request_id=request_id, document_id=document_id))


    def inspect(self, *, detail: Union[Literal['summary', 'structure'], Unset] = UNSET, max_features: Union[int, Unset] = UNSET, document_id: Optional[str] = None, expected_update_stamp: Optional[int] = None, request_id: Optional[str] = None) -> Response[models.DocumentInspectResult]:
        """document.inspect; runtime validation enforces bounds, conditions and context."""
        parameters: Dict[str, object] = {}
        if detail is not UNSET:
            parameters['detail'] = detail
        if max_features is not UNSET:
            parameters['max_features'] = max_features
        return cast("Response[models.DocumentInspectResult]", self._client._execute('document.inspect', parameters, request_id=request_id, document_id=document_id, expected_update_stamp=expected_update_stamp))


    def properties(self, *, name: Union[str, Unset] = UNSET, configuration: Union[str, Unset] = UNSET, document_id: Optional[str] = None, expected_update_stamp: Optional[int] = None, request_id: Optional[str] = None) -> Response[models.DocumentPropertiesResult]:
        """document.properties; runtime validation enforces bounds, conditions and context."""
        parameters: Dict[str, object] = {}
        if name is not UNSET:
            parameters['name'] = name
        if configuration is not UNSET:
            parameters['configuration'] = configuration
        return cast("Response[models.DocumentPropertiesResult]", self._client._execute('document.properties', parameters, request_id=request_id, document_id=document_id, expected_update_stamp=expected_update_stamp))


    def property_summary(self, *, name: Union[str, Unset] = UNSET, document_id: Optional[str] = None, expected_update_stamp: Optional[int] = None, request_id: Optional[str] = None) -> Response[models.DocumentPropertySummaryResult]:
        """document.property-summary; runtime validation enforces bounds, conditions and context."""
        parameters: Dict[str, object] = {}
        if name is not UNSET:
            parameters['name'] = name
        return cast("Response[models.DocumentPropertySummaryResult]", self._client._execute('document.property-summary', parameters, request_id=request_id, document_id=document_id, expected_update_stamp=expected_update_stamp))


    def property_add(self, *, name: str, value: str, configuration: Union[str, Unset] = UNSET, type: Union[Literal['integer', 'double', 'yes-no', 'text', 'date'], Unset] = UNSET, document_id: Optional[str] = None, expected_update_stamp: Optional[int] = None, lease_id: Optional[str] = None, request_id: Optional[str] = None) -> Response[models.DocumentPropertyAddResult]:
        """document.property-add; runtime validation enforces bounds, conditions and context."""
        parameters: Dict[str, object] = {}
        parameters['name'] = name
        parameters['value'] = value
        if configuration is not UNSET:
            parameters['configuration'] = configuration
        if type is not UNSET:
            parameters['type'] = type
        return cast("Response[models.DocumentPropertyAddResult]", self._client._execute('document.property-add', parameters, request_id=request_id, document_id=document_id, expected_update_stamp=expected_update_stamp, lease_id=lease_id))


    def property_set(self, *, name: str, value: str, configuration: Union[str, Unset] = UNSET, expected_value: Union[str, Unset] = UNSET, document_id: Optional[str] = None, expected_update_stamp: Optional[int] = None, lease_id: Optional[str] = None, request_id: Optional[str] = None) -> Response[models.DocumentPropertySetResult]:
        """document.property-set; runtime validation enforces bounds, conditions and context."""
        parameters: Dict[str, object] = {}
        parameters['name'] = name
        parameters['value'] = value
        if configuration is not UNSET:
            parameters['configuration'] = configuration
        if expected_value is not UNSET:
            parameters['expected_value'] = expected_value
        return cast("Response[models.DocumentPropertySetResult]", self._client._execute('document.property-set', parameters, request_id=request_id, document_id=document_id, expected_update_stamp=expected_update_stamp, lease_id=lease_id))


    def property_delete(self, *, name: str, configuration: Union[str, Unset] = UNSET, expected_value: Union[str, Unset] = UNSET, document_id: Optional[str] = None, expected_update_stamp: Optional[int] = None, lease_id: Optional[str] = None, request_id: Optional[str] = None) -> Response[models.DocumentPropertyDeleteResult]:
        """document.property-delete; runtime validation enforces bounds, conditions and context."""
        parameters: Dict[str, object] = {}
        parameters['name'] = name
        if configuration is not UNSET:
            parameters['configuration'] = configuration
        if expected_value is not UNSET:
            parameters['expected_value'] = expected_value
        return cast("Response[models.DocumentPropertyDeleteResult]", self._client._execute('document.property-delete', parameters, request_id=request_id, document_id=document_id, expected_update_stamp=expected_update_stamp, lease_id=lease_id))


    def line_font(self, *, document_id: Optional[str] = None, expected_update_stamp: Optional[int] = None, request_id: Optional[str] = None) -> Response[models.DocumentLineFontResult]:
        """document.line-font; runtime validation enforces bounds, conditions and context."""
        parameters: Dict[str, object] = {}
        return cast("Response[models.DocumentLineFontResult]", self._client._execute('document.line-font', parameters, request_id=request_id, document_id=document_id, expected_update_stamp=expected_update_stamp))


    def line_font_set(self, *, field: Literal['visible_edges.style', 'visible_edges.weight', 'hidden_edges.style', 'hidden_edges.weight'], value: int, expected_options: Dict[str, JSONValue], document_id: Optional[str] = None, expected_update_stamp: Optional[int] = None, lease_id: Optional[str] = None, request_id: Optional[str] = None) -> Response[models.DocumentLineFontSetResult]:
        """document.line-font-set; runtime validation enforces bounds, conditions and context."""
        parameters: Dict[str, object] = {}
        parameters['field'] = field
        parameters['value'] = value
        parameters['expected_options'] = expected_options
        return cast("Response[models.DocumentLineFontSetResult]", self._client._execute('document.line-font-set', parameters, request_id=request_id, document_id=document_id, expected_update_stamp=expected_update_stamp, lease_id=lease_id))


    def annotation_options(self, *, document_id: Optional[str] = None, expected_update_stamp: Optional[int] = None, request_id: Optional[str] = None) -> Response[models.DocumentAnnotationOptionsResult]:
        """document.annotation-options; runtime validation enforces bounds, conditions and context."""
        parameters: Dict[str, object] = {}
        return cast("Response[models.DocumentAnnotationOptionsResult]", self._client._execute('document.annotation-options', parameters, request_id=request_id, document_id=document_id, expected_update_stamp=expected_update_stamp))


    def annotation_option_set(self, *, field: Literal['arrow.edge_vertex', 'arrow.face_surface', 'arrow.unattached', 'bent_leader.enabled', 'bent_leader.length_mm', 'zero.leading', 'zero.trailing'], value: Union[str, bool, float], expected_value: Union[str, bool, float], document_id: Optional[str] = None, expected_update_stamp: Optional[int] = None, lease_id: Optional[str] = None, request_id: Optional[str] = None) -> Response[models.DocumentAnnotationOptionSetResult]:
        """document.annotation-option-set; runtime validation enforces bounds, conditions and context."""
        parameters: Dict[str, object] = {}
        parameters['field'] = field
        parameters['value'] = value
        parameters['expected_value'] = expected_value
        return cast("Response[models.DocumentAnnotationOptionSetResult]", self._client._execute('document.annotation-option-set', parameters, request_id=request_id, document_id=document_id, expected_update_stamp=expected_update_stamp, lease_id=lease_id))


    def units(self, *, document_id: Optional[str] = None, expected_update_stamp: Optional[int] = None, request_id: Optional[str] = None) -> Response[models.DocumentUnitsResult]:
        """document.units; runtime validation enforces bounds, conditions and context."""
        parameters: Dict[str, object] = {}
        return cast("Response[models.DocumentUnitsResult]", self._client._execute('document.units', parameters, request_id=request_id, document_id=document_id, expected_update_stamp=expected_update_stamp))


    def units_set(self, *, length_unit: Union[Literal['mm', 'inch'], Unset] = UNSET, decimal_places: Union[int, Unset] = UNSET, expected_length_unit: Union[Literal['mm', 'inch'], Unset] = UNSET, expected_decimal_places: Union[int, Unset] = UNSET, document_id: Optional[str] = None, expected_update_stamp: Optional[int] = None, lease_id: Optional[str] = None, request_id: Optional[str] = None) -> Response[models.DocumentUnitsSetResult]:
        """document.units-set; runtime validation enforces bounds, conditions and context."""
        parameters: Dict[str, object] = {}
        if length_unit is not UNSET:
            parameters['length_unit'] = length_unit
        if decimal_places is not UNSET:
            parameters['decimal_places'] = decimal_places
        if expected_length_unit is not UNSET:
            parameters['expected_length_unit'] = expected_length_unit
        if expected_decimal_places is not UNSET:
            parameters['expected_decimal_places'] = expected_decimal_places
        return cast("Response[models.DocumentUnitsSetResult]", self._client._execute('document.units-set', parameters, request_id=request_id, document_id=document_id, expected_update_stamp=expected_update_stamp, lease_id=lease_id))


    def summary(self, *, document_id: Optional[str] = None, expected_update_stamp: Optional[int] = None, request_id: Optional[str] = None) -> Response[models.DocumentSummaryResult]:
        """document.summary; runtime validation enforces bounds, conditions and context."""
        parameters: Dict[str, object] = {}
        return cast("Response[models.DocumentSummaryResult]", self._client._execute('document.summary', parameters, request_id=request_id, document_id=document_id, expected_update_stamp=expected_update_stamp))


    def summary_set(self, *, field: Literal['title', 'subject', 'author', 'keywords', 'comment'], value: str, expected_value: Union[str, Unset] = UNSET, document_id: Optional[str] = None, expected_update_stamp: Optional[int] = None, lease_id: Optional[str] = None, request_id: Optional[str] = None) -> Response[models.DocumentSummarySetResult]:
        """document.summary-set; runtime validation enforces bounds, conditions and context."""
        parameters: Dict[str, object] = {}
        parameters['field'] = field
        parameters['value'] = value
        if expected_value is not UNSET:
            parameters['expected_value'] = expected_value
        return cast("Response[models.DocumentSummarySetResult]", self._client._execute('document.summary-set', parameters, request_id=request_id, document_id=document_id, expected_update_stamp=expected_update_stamp, lease_id=lease_id))


    def close(self, *, discard: Union[bool, Unset] = UNSET, document_id: Optional[str] = None, expected_update_stamp: Optional[int] = None, lease_id: Optional[str] = None, request_id: Optional[str] = None) -> Response[models.DocumentCloseResult]:
        """document.close; runtime validation enforces bounds, conditions and context."""
        parameters: Dict[str, object] = {}
        if discard is not UNSET:
            parameters['discard'] = discard
        return cast("Response[models.DocumentCloseResult]", self._client._execute('document.close', parameters, request_id=request_id, document_id=document_id, expected_update_stamp=expected_update_stamp, lease_id=lease_id))


    def measure(self, *, max_bodies: Union[int, Unset] = UNSET, document_id: Optional[str] = None, expected_update_stamp: Optional[int] = None, request_id: Optional[str] = None) -> Response[models.DocumentMeasureResult]:
        """document.measure; runtime validation enforces bounds, conditions and context."""
        parameters: Dict[str, object] = {}
        if max_bodies is not UNSET:
            parameters['max_bodies'] = max_bodies
        return cast("Response[models.DocumentMeasureResult]", self._client._execute('document.measure', parameters, request_id=request_id, document_id=document_id, expected_update_stamp=expected_update_stamp))


    def save(self, *, document_id: Optional[str] = None, expected_update_stamp: Optional[int] = None, lease_id: Optional[str] = None, request_id: Optional[str] = None) -> Response[models.DocumentSaveResult]:
        """document.save; runtime validation enforces bounds, conditions and context."""
        parameters: Dict[str, object] = {}
        return cast("Response[models.DocumentSaveResult]", self._client._execute('document.save', parameters, request_id=request_id, document_id=document_id, expected_update_stamp=expected_update_stamp, lease_id=lease_id))


    def save_as(self, *, output: str, document_id: Optional[str] = None, expected_update_stamp: Optional[int] = None, lease_id: Optional[str] = None, request_id: Optional[str] = None) -> Response[models.DocumentSaveAsResult]:
        """document.save-as; runtime validation enforces bounds, conditions and context."""
        parameters: Dict[str, object] = {}
        parameters['output'] = output
        return cast("Response[models.DocumentSaveAsResult]", self._client._execute('document.save-as', parameters, request_id=request_id, document_id=document_id, expected_update_stamp=expected_update_stamp, lease_id=lease_id))


    def diagnose(self, *, max_features: Union[int, Unset] = UNSET, document_id: Optional[str] = None, expected_update_stamp: Optional[int] = None, request_id: Optional[str] = None) -> Response[models.DocumentDiagnoseResult]:
        """document.diagnose; runtime validation enforces bounds, conditions and context."""
        parameters: Dict[str, object] = {}
        if max_features is not UNSET:
            parameters['max_features'] = max_features
        return cast("Response[models.DocumentDiagnoseResult]", self._client._execute('document.diagnose', parameters, request_id=request_id, document_id=document_id, expected_update_stamp=expected_update_stamp))


    def rebuild(self, *, force: Union[bool, Unset] = UNSET, top_only: Union[bool, Unset] = UNSET, max_features: Union[int, Unset] = UNSET, document_id: Optional[str] = None, expected_update_stamp: Optional[int] = None, lease_id: Optional[str] = None, request_id: Optional[str] = None) -> Response[models.DocumentRebuildResult]:
        """document.rebuild; runtime validation enforces bounds, conditions and context."""
        parameters: Dict[str, object] = {}
        if force is not UNSET:
            parameters['force'] = force
        if top_only is not UNSET:
            parameters['top_only'] = top_only
        if max_features is not UNSET:
            parameters['max_features'] = max_features
        return cast("Response[models.DocumentRebuildResult]", self._client._execute('document.rebuild', parameters, request_id=request_id, document_id=document_id, expected_update_stamp=expected_update_stamp, lease_id=lease_id))


    def render(self, *, output: str, width: Union[int, Unset] = UNSET, height: Union[int, Unset] = UNSET, view: Union[Literal['current', 'front', 'back', 'left', 'right', 'top', 'bottom', 'isometric', 'trimetric', 'dimetric'], Unset] = UNSET, fit: Union[bool, Unset] = UNSET, overwrite: Union[bool, Unset] = UNSET, include_content: Union[bool, Unset] = UNSET, document_id: Optional[str] = None, expected_update_stamp: Optional[int] = None, lease_id: Optional[str] = None, request_id: Optional[str] = None) -> Response[models.DocumentRenderResult]:
        """document.render; runtime validation enforces bounds, conditions and context."""
        parameters: Dict[str, object] = {}
        parameters['output'] = output
        if width is not UNSET:
            parameters['width'] = width
        if height is not UNSET:
            parameters['height'] = height
        if view is not UNSET:
            parameters['view'] = view
        if fit is not UNSET:
            parameters['fit'] = fit
        if overwrite is not UNSET:
            parameters['overwrite'] = overwrite
        if include_content is not UNSET:
            parameters['include_content'] = include_content
        return cast("Response[models.DocumentRenderResult]", self._client._execute('document.render', parameters, request_id=request_id, document_id=document_id, expected_update_stamp=expected_update_stamp, lease_id=lease_id))


    def export(self, *, output: str, overwrite: Union[bool, Unset] = UNSET, strict: Union[bool, Unset] = UNSET, include_content: Union[bool, Unset] = UNSET, document_id: Optional[str] = None, expected_update_stamp: Optional[int] = None, lease_id: Optional[str] = None, request_id: Optional[str] = None) -> Response[models.DocumentExportResult]:
        """document.export; runtime validation enforces bounds, conditions and context."""
        parameters: Dict[str, object] = {}
        parameters['output'] = output
        if overwrite is not UNSET:
            parameters['overwrite'] = overwrite
        if strict is not UNSET:
            parameters['strict'] = strict
        if include_content is not UNSET:
            parameters['include_content'] = include_content
        return cast("Response[models.DocumentExportResult]", self._client._execute('document.export', parameters, request_id=request_id, document_id=document_id, expected_update_stamp=expected_update_stamp, lease_id=lease_id))


class DrawingOperations:
    def __init__(self, client: Dispatcher) -> None:
        self._client = client

    def standard_views(self, *, source_document_id: str, configuration: str, document_id: Optional[str] = None, expected_update_stamp: Optional[int] = None, lease_id: Optional[str] = None, request_id: Optional[str] = None) -> Response[models.DrawingStandardViewsResult]:
        """drawing.standard-views; runtime validation enforces bounds, conditions and context."""
        parameters: Dict[str, object] = {}
        parameters['source_document_id'] = source_document_id
        parameters['configuration'] = configuration
        return cast("Response[models.DrawingStandardViewsResult]", self._client._execute('drawing.standard-views', parameters, request_id=request_id, document_id=document_id, expected_update_stamp=expected_update_stamp, lease_id=lease_id))


class EntityOperations:
    def __init__(self, client: Dispatcher) -> None:
        self._client = client

    def list(self, *, kind: Union[Literal['face', 'edge'], Unset] = UNSET, max_faces: Union[int, Unset] = UNSET, max_edges: Union[int, Unset] = UNSET, document_id: Optional[str] = None, expected_update_stamp: Optional[int] = None, request_id: Optional[str] = None) -> Response[models.EntityListResult]:
        """entity.list; runtime validation enforces bounds, conditions and context."""
        parameters: Dict[str, object] = {}
        if kind is not UNSET:
            parameters['kind'] = kind
        if max_faces is not UNSET:
            parameters['max_faces'] = max_faces
        if max_edges is not UNSET:
            parameters['max_edges'] = max_edges
        return cast("Response[models.EntityListResult]", self._client._execute('entity.list', parameters, request_id=request_id, document_id=document_id, expected_update_stamp=expected_update_stamp))


    def inspect(self, *, entity_id: str, kind: Union[Literal['face', 'edge'], Unset] = UNSET, document_id: Optional[str] = None, expected_update_stamp: Optional[int] = None, request_id: Optional[str] = None) -> Response[models.EntityInspectResult]:
        """entity.inspect; runtime validation enforces bounds, conditions and context."""
        parameters: Dict[str, object] = {}
        parameters['entity_id'] = entity_id
        if kind is not UNSET:
            parameters['kind'] = kind
        return cast("Response[models.EntityInspectResult]", self._client._execute('entity.inspect', parameters, request_id=request_id, document_id=document_id, expected_update_stamp=expected_update_stamp))


class FeatureOperations:
    def __init__(self, client: Dispatcher) -> None:
        self._client = client

    def list(self, *, max_features: Union[int, Unset] = UNSET, document_id: Optional[str] = None, expected_update_stamp: Optional[int] = None, request_id: Optional[str] = None) -> Response[models.FeatureListResult]:
        """feature.list; runtime validation enforces bounds, conditions and context."""
        parameters: Dict[str, object] = {}
        if max_features is not UNSET:
            parameters['max_features'] = max_features
        return cast("Response[models.FeatureListResult]", self._client._execute('feature.list', parameters, request_id=request_id, document_id=document_id, expected_update_stamp=expected_update_stamp))


    def inspect(self, *, feature_id: str, document_id: Optional[str] = None, expected_update_stamp: Optional[int] = None, request_id: Optional[str] = None) -> Response[models.FeatureInspectResult]:
        """feature.inspect; runtime validation enforces bounds, conditions and context."""
        parameters: Dict[str, object] = {}
        parameters['feature_id'] = feature_id
        return cast("Response[models.FeatureInspectResult]", self._client._execute('feature.inspect', parameters, request_id=request_id, document_id=document_id, expected_update_stamp=expected_update_stamp))


    def set_depth(self, *, feature_id: str, depth_mm: float, document_id: Optional[str] = None, expected_update_stamp: Optional[int] = None, lease_id: Optional[str] = None, request_id: Optional[str] = None) -> Response[models.FeatureSetDepthResult]:
        """feature.set-depth; runtime validation enforces bounds, conditions and context."""
        parameters: Dict[str, object] = {}
        parameters['feature_id'] = feature_id
        parameters['depth_mm'] = depth_mm
        return cast("Response[models.FeatureSetDepthResult]", self._client._execute('feature.set-depth', parameters, request_id=request_id, document_id=document_id, expected_update_stamp=expected_update_stamp, lease_id=lease_id))


    def fillet(self, *, entity_id: str, radius_mm: float, document_id: Optional[str] = None, expected_update_stamp: Optional[int] = None, lease_id: Optional[str] = None, request_id: Optional[str] = None) -> Response[models.FeatureFilletResult]:
        """feature.fillet; runtime validation enforces bounds, conditions and context."""
        parameters: Dict[str, object] = {}
        parameters['entity_id'] = entity_id
        parameters['radius_mm'] = radius_mm
        return cast("Response[models.FeatureFilletResult]", self._client._execute('feature.fillet', parameters, request_id=request_id, document_id=document_id, expected_update_stamp=expected_update_stamp, lease_id=lease_id))


    def extrude(self, *, sketch_id: str, depth_mm: float, reverse: Union[bool, Unset] = UNSET, merge: Union[bool, Unset] = UNSET, document_id: Optional[str] = None, expected_update_stamp: Optional[int] = None, lease_id: Optional[str] = None, request_id: Optional[str] = None) -> Response[models.FeatureExtrudeResult]:
        """feature.extrude; runtime validation enforces bounds, conditions and context."""
        parameters: Dict[str, object] = {}
        parameters['sketch_id'] = sketch_id
        parameters['depth_mm'] = depth_mm
        if reverse is not UNSET:
            parameters['reverse'] = reverse
        if merge is not UNSET:
            parameters['merge'] = merge
        return cast("Response[models.FeatureExtrudeResult]", self._client._execute('feature.extrude', parameters, request_id=request_id, document_id=document_id, expected_update_stamp=expected_update_stamp, lease_id=lease_id))


    def cut_extrude(self, *, sketch_id: str, end_condition: Union[Literal['blind', 'through-all'], Unset] = UNSET, depth_mm: Union[float, Unset] = UNSET, reverse: Union[bool, Unset] = UNSET, document_id: Optional[str] = None, expected_update_stamp: Optional[int] = None, lease_id: Optional[str] = None, request_id: Optional[str] = None) -> Response[models.FeatureCutExtrudeResult]:
        """feature.cut-extrude; runtime validation enforces bounds, conditions and context."""
        parameters: Dict[str, object] = {}
        parameters['sketch_id'] = sketch_id
        if end_condition is not UNSET:
            parameters['end_condition'] = end_condition
        if depth_mm is not UNSET:
            parameters['depth_mm'] = depth_mm
        if reverse is not UNSET:
            parameters['reverse'] = reverse
        return cast("Response[models.FeatureCutExtrudeResult]", self._client._execute('feature.cut-extrude', parameters, request_id=request_id, document_id=document_id, expected_update_stamp=expected_update_stamp, lease_id=lease_id))


class PartOperations:
    def __init__(self, client: Dispatcher) -> None:
        self._client = client

    def create_box(self, *, output: str, width_mm: float, height_mm: float, depth_mm: float, template: Union[str, Unset] = UNSET, overwrite: Union[bool, Unset] = UNSET, request_id: Optional[str] = None) -> Response[models.PartCreateBoxResult]:
        """part.create-box; runtime validation enforces bounds, conditions and context."""
        parameters: Dict[str, object] = {}
        parameters['output'] = output
        parameters['width_mm'] = width_mm
        parameters['height_mm'] = height_mm
        parameters['depth_mm'] = depth_mm
        if template is not UNSET:
            parameters['template'] = template
        if overwrite is not UNSET:
            parameters['overwrite'] = overwrite
        return cast("Response[models.PartCreateBoxResult]", self._client._execute('part.create-box', parameters, request_id=request_id))


class SketchOperations:
    def __init__(self, client: Dispatcher) -> None:
        self._client = client

    def list(self, *, max_sketches: Union[int, Unset] = UNSET, document_id: Optional[str] = None, expected_update_stamp: Optional[int] = None, request_id: Optional[str] = None) -> Response[models.SketchListResult]:
        """sketch.list; runtime validation enforces bounds, conditions and context."""
        parameters: Dict[str, object] = {}
        if max_sketches is not UNSET:
            parameters['max_sketches'] = max_sketches
        return cast("Response[models.SketchListResult]", self._client._execute('sketch.list', parameters, request_id=request_id, document_id=document_id, expected_update_stamp=expected_update_stamp))


    def inspect(self, *, sketch_id: str, max_segments: Union[int, Unset] = UNSET, document_id: Optional[str] = None, expected_update_stamp: Optional[int] = None, request_id: Optional[str] = None) -> Response[models.SketchInspectResult]:
        """sketch.inspect; runtime validation enforces bounds, conditions and context."""
        parameters: Dict[str, object] = {}
        parameters['sketch_id'] = sketch_id
        if max_segments is not UNSET:
            parameters['max_segments'] = max_segments
        return cast("Response[models.SketchInspectResult]", self._client._execute('sketch.inspect', parameters, request_id=request_id, document_id=document_id, expected_update_stamp=expected_update_stamp))


    def rectangle(self, *, plane: Literal['front', 'top', 'right'], width_mm: float, height_mm: float, center_x_mm: Union[float, Unset] = UNSET, center_y_mm: Union[float, Unset] = UNSET, document_id: Optional[str] = None, expected_update_stamp: Optional[int] = None, lease_id: Optional[str] = None, request_id: Optional[str] = None) -> Response[models.SketchRectangleResult]:
        """sketch.rectangle; runtime validation enforces bounds, conditions and context."""
        parameters: Dict[str, object] = {}
        parameters['plane'] = plane
        parameters['width_mm'] = width_mm
        parameters['height_mm'] = height_mm
        if center_x_mm is not UNSET:
            parameters['center_x_mm'] = center_x_mm
        if center_y_mm is not UNSET:
            parameters['center_y_mm'] = center_y_mm
        return cast("Response[models.SketchRectangleResult]", self._client._execute('sketch.rectangle', parameters, request_id=request_id, document_id=document_id, expected_update_stamp=expected_update_stamp, lease_id=lease_id))


    def polygon(self, *, plane: Literal['front', 'top', 'right'], vertices_mm: List[models.SketchPolygonParametersVerticesMmItem], document_id: Optional[str] = None, expected_update_stamp: Optional[int] = None, lease_id: Optional[str] = None, request_id: Optional[str] = None) -> Response[models.SketchPolygonResult]:
        """sketch.polygon; runtime validation enforces bounds, conditions and context."""
        parameters: Dict[str, object] = {}
        parameters['plane'] = plane
        parameters['vertices_mm'] = vertices_mm
        return cast("Response[models.SketchPolygonResult]", self._client._execute('sketch.polygon', parameters, request_id=request_id, document_id=document_id, expected_update_stamp=expected_update_stamp, lease_id=lease_id))


    def circle(self, *, plane: Literal['front', 'top', 'right'], radius_mm: float, center_x_mm: Union[float, Unset] = UNSET, center_y_mm: Union[float, Unset] = UNSET, document_id: Optional[str] = None, expected_update_stamp: Optional[int] = None, lease_id: Optional[str] = None, request_id: Optional[str] = None) -> Response[models.SketchCircleResult]:
        """sketch.circle; runtime validation enforces bounds, conditions and context."""
        parameters: Dict[str, object] = {}
        parameters['plane'] = plane
        parameters['radius_mm'] = radius_mm
        if center_x_mm is not UNSET:
            parameters['center_x_mm'] = center_x_mm
        if center_y_mm is not UNSET:
            parameters['center_y_mm'] = center_y_mm
        return cast("Response[models.SketchCircleResult]", self._client._execute('sketch.circle', parameters, request_id=request_id, document_id=document_id, expected_update_stamp=expected_update_stamp, lease_id=lease_id))


    def fix_center(self, *, sketch_id: str, document_id: Optional[str] = None, expected_update_stamp: Optional[int] = None, lease_id: Optional[str] = None, request_id: Optional[str] = None) -> Response[models.SketchFixCenterResult]:
        """sketch.fix-center; runtime validation enforces bounds, conditions and context."""
        parameters: Dict[str, object] = {}
        parameters['sketch_id'] = sketch_id
        return cast("Response[models.SketchFixCenterResult]", self._client._execute('sketch.fix-center', parameters, request_id=request_id, document_id=document_id, expected_update_stamp=expected_update_stamp, lease_id=lease_id))


    def dimension_diameter(self, *, sketch_id: str, diameter_mm: float, document_id: Optional[str] = None, expected_update_stamp: Optional[int] = None, lease_id: Optional[str] = None, request_id: Optional[str] = None) -> Response[models.SketchDimensionDiameterResult]:
        """sketch.dimension-diameter; runtime validation enforces bounds, conditions and context."""
        parameters: Dict[str, object] = {}
        parameters['sketch_id'] = sketch_id
        parameters['diameter_mm'] = diameter_mm
        return cast("Response[models.SketchDimensionDiameterResult]", self._client._execute('sketch.dimension-diameter', parameters, request_id=request_id, document_id=document_id, expected_update_stamp=expected_update_stamp, lease_id=lease_id))


    def dimension_rectangle(self, *, sketch_id: str, width_mm: float, height_mm: float, document_id: Optional[str] = None, expected_update_stamp: Optional[int] = None, lease_id: Optional[str] = None, request_id: Optional[str] = None) -> Response[models.SketchDimensionRectangleResult]:
        """sketch.dimension-rectangle; runtime validation enforces bounds, conditions and context."""
        parameters: Dict[str, object] = {}
        parameters['sketch_id'] = sketch_id
        parameters['width_mm'] = width_mm
        parameters['height_mm'] = height_mm
        return cast("Response[models.SketchDimensionRectangleResult]", self._client._execute('sketch.dimension-rectangle', parameters, request_id=request_id, document_id=document_id, expected_update_stamp=expected_update_stamp, lease_id=lease_id))


class WorkspaceOperations:
    def __init__(self, client: Dispatcher) -> None:
        self._client = client

    def upload_begin(self, *, path: str, size_bytes: int, sha256: str, overwrite: Union[bool, Unset] = UNSET, request_id: Optional[str] = None) -> Response[models.WorkspaceUploadBeginResult]:
        """workspace.upload-begin; runtime validation enforces bounds, conditions and context."""
        parameters: Dict[str, object] = {}
        parameters['path'] = path
        parameters['size_bytes'] = size_bytes
        parameters['sha256'] = sha256
        if overwrite is not UNSET:
            parameters['overwrite'] = overwrite
        return cast("Response[models.WorkspaceUploadBeginResult]", self._client._execute('workspace.upload-begin', parameters, request_id=request_id))


    def upload_chunk(self, *, transfer_id: str, offset: int, data: str, request_id: Optional[str] = None) -> Response[models.WorkspaceUploadChunkResult]:
        """workspace.upload-chunk; runtime validation enforces bounds, conditions and context."""
        parameters: Dict[str, object] = {}
        parameters['transfer_id'] = transfer_id
        parameters['offset'] = offset
        parameters['data'] = data
        return cast("Response[models.WorkspaceUploadChunkResult]", self._client._execute('workspace.upload-chunk', parameters, request_id=request_id))


    def upload_status(self, *, transfer_id: str, request_id: Optional[str] = None) -> Response[models.WorkspaceUploadStatusResult]:
        """workspace.upload-status; runtime validation enforces bounds, conditions and context."""
        parameters: Dict[str, object] = {}
        parameters['transfer_id'] = transfer_id
        return cast("Response[models.WorkspaceUploadStatusResult]", self._client._execute('workspace.upload-status', parameters, request_id=request_id))


    def upload_commit(self, *, transfer_id: str, request_id: Optional[str] = None) -> Response[models.WorkspaceUploadCommitResult]:
        """workspace.upload-commit; runtime validation enforces bounds, conditions and context."""
        parameters: Dict[str, object] = {}
        parameters['transfer_id'] = transfer_id
        return cast("Response[models.WorkspaceUploadCommitResult]", self._client._execute('workspace.upload-commit', parameters, request_id=request_id))


    def upload_abort(self, *, transfer_id: str, request_id: Optional[str] = None) -> Response[models.WorkspaceUploadAbortResult]:
        """workspace.upload-abort; runtime validation enforces bounds, conditions and context."""
        parameters: Dict[str, object] = {}
        parameters['transfer_id'] = transfer_id
        return cast("Response[models.WorkspaceUploadAbortResult]", self._client._execute('workspace.upload-abort', parameters, request_id=request_id))


    def download_begin(self, *, path: str, request_id: Optional[str] = None) -> Response[models.WorkspaceDownloadBeginResult]:
        """workspace.download-begin; runtime validation enforces bounds, conditions and context."""
        parameters: Dict[str, object] = {}
        parameters['path'] = path
        return cast("Response[models.WorkspaceDownloadBeginResult]", self._client._execute('workspace.download-begin', parameters, request_id=request_id))


    def download_chunk(self, *, transfer_id: str, offset: int, length: int, request_id: Optional[str] = None) -> Response[models.WorkspaceDownloadChunkResult]:
        """workspace.download-chunk; runtime validation enforces bounds, conditions and context."""
        parameters: Dict[str, object] = {}
        parameters['transfer_id'] = transfer_id
        parameters['offset'] = offset
        parameters['length'] = length
        return cast("Response[models.WorkspaceDownloadChunkResult]", self._client._execute('workspace.download-chunk', parameters, request_id=request_id))


    def download_end(self, *, transfer_id: str, request_id: Optional[str] = None) -> Response[models.WorkspaceDownloadEndResult]:
        """workspace.download-end; runtime validation enforces bounds, conditions and context."""
        parameters: Dict[str, object] = {}
        parameters['transfer_id'] = transfer_id
        return cast("Response[models.WorkspaceDownloadEndResult]", self._client._execute('workspace.download-end', parameters, request_id=request_id))


class GeneratedAPI:
    def __init__(self) -> None:
        self.assembly = AssemblyOperations(self)
        self.daemon = DaemonOperations(self)
        self.dimension = DimensionOperations(self)
        self.document = DocumentOperations(self)
        self.drawing = DrawingOperations(self)
        self.entity = EntityOperations(self)
        self.feature = FeatureOperations(self)
        self.part = PartOperations(self)
        self.sketch = SketchOperations(self)
        self.workspace = WorkspaceOperations(self)

    def _execute(self, operation: str, parameters: Optional[Dict[str, object]] = None, *, request_id: Optional[str] = None, document_id: Optional[str] = None, expected_update_stamp: Optional[int] = None, lease_id: Optional[str] = None) -> Response[JSONValue]:
        raise NotImplementedError
