"""Read-only inheritance witnesses for one isolated sheet drawing."""
from hashlib import sha256
import re

from swcli.font_snapshot import FONT_MEMBERS, font_snapshot
from swcli.hosts.windows import _com_value
from swcli.hosts import windows_document_font_scopes as guard

ENUM = {"dimensions": "swDisplayDimension", "tables": "swTableAnnotation_General"}
STYLE = ("typeface", "bold", "italic", "underline", "strikeout")


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def file_digest(path):
    digest = sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_drawing_input(scope, path, digest):
    if path is None and digest is None:
        return
    if scope not in ENUM or path is None or not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ValueError("inheritance requires one next scope, a drawing and its exact SHA-256")
    if path.suffix.lower() != ".slddrw" or path.is_symlink() or not path.is_file():
        raise ValueError("inheritance fixture must be a regular SLDDrw file")
    require(file_digest(path) == digest, "inheritance source SHA-256 differs")


def stage_drawing(path, digest, output):
    # Copy only after hash verification and recheck the copy before any CAD open.
    from shutil import copyfileobj
    destination = output / "inheritance-source.SLDDRW"
    with path.open("rb") as source, destination.open("xb") as target:
        copyfileobj(source, target)
    require(file_digest(destination) == digest, "staged inheritance drawing SHA-256 differs")
    return destination


def snapshot(use_doc, obj):
    require(type(use_doc) is bool and obj is not None, "font inheritance is unreadable")
    native = {member: guard._read_member(obj, member) for member in FONT_MEMBERS.values()}
    return {"use_document_font": use_doc, "font": font_snapshot(native), "native_font": native}


def collect_dimensions(view, enum):
    by_role = {}
    annotation = _com_value(view, "GetFirstAnnotation3")
    count = 0
    while annotation is not None:
        count += 1
        require(count <= 100, "drawing annotation enumeration exceeded fixture limit")
        if _com_value(annotation, "GetType") == enum:
            name = _com_value(annotation, "GetName")
            require(isinstance(name, str) and bool(name), "display dimension identity is unreadable")
            require(_com_value(annotation, "GetTextFormatCount") == 1, "display dimension must have one text format")
            observed = snapshot(annotation.GetUseDocTextFormat(0), annotation.GetTextFormat(0))
            role = "inherited" if observed["use_document_font"] else "local"
            require(role not in by_role, "expected exactly one dimension of each inheritance role")
            by_role[role] = dict(name=name, **observed)
        annotation = _com_value(annotation, "GetNext3")
    require(set(by_role) == {"inherited", "local"}, "drawing needs one inheriting and one local display dimension")
    require(by_role["inherited"]["name"] != by_role["local"]["name"], "display dimension identities collide")
    return by_role


def collect_table(view, enum):
    table = _com_value(view, "GetFirstTableAnnotation2")
    require(table is not None and _com_value(table, "GetNext") is None, "drawing needs exactly one table")
    require(_com_value(table, "Type") == enum, "inheritance fixture must contain one General table")
    require((_com_value(table, "RowCount"), _com_value(table, "ColumnCount")) == (1, 2),
            "General table fixture must be one data row by two columns")
    annotation = _com_value(table, "GetAnnotation")
    name = _com_value(annotation, "GetName")
    require(isinstance(name, str) and bool(name), "General table identity is unreadable")
    whole = snapshot(_com_value(table, "GetUseDocTextFormat"), _com_value(table, "GetTextFormat"))
    cells = {}
    for column, role in enumerate(("inherited", "local")):
        cell = snapshot(table.GetCellUseDocTextFormat(0, column), table.GetCellTextFormat(0, column))
        cells[role] = dict(cell=[0, column], **cell)
    return dict(name=name, table=whole, **cells)


def read_drawing(app, document, constants, scope):
    foreground = _com_value(app, "ActiveDoc")
    original = guard._state(document)
    identity = (_com_value(document, "GetPathName"), _com_value(document, "GetTitle"))
    edit = guard._edit_context(document)
    front_state = guard._other_foreground_snapshot(app, document, foreground)
    require(original[0] == 3 and _com_value(document, "GetSheetCount") == 1,
            "inheritance fixture must be a single-sheet drawing")
    require(_com_value(app, "GetDocumentCount") == 2, "unexpected open documents beside fixture and foreground")
    view = _com_value(document, "GetFirstView")
    require(view is not None and _com_value(view, "GetReferencedModelName") == ""
            and _com_value(view, "GetNextView") is None, "inheritance fixture requires a sheet without model views")
    enum = constants[ENUM[scope]]
    observed = collect_dimensions(view, enum) if scope == "dimensions" else collect_table(view, enum)
    guard._verify_identity(app, document, foreground, edit, original, identity, front_state)
    require(_com_value(app, "GetDocumentCount") == 2, "inheritance read changed the open document count")
    return observed


def effective(font):
    height = "height_points" if font["height_mode"] == "points" else "height_mm"
    return {name: font[name] for name in (*STYLE, "height_mode", height)}


def verify_observation(scope, observed, default, baseline=None):
    for row in ([observed["inherited"], observed["table"]] if scope == "tables" else [observed["inherited"]]):
        require(row["use_document_font"] is True, "fixture lost the document font flag")
        require(effective(row["font"]) == effective(default), "inherited font did not follow its document default")
    require(observed["local"]["use_document_font"] is False, "fixture lost the local font override")
    require(effective(observed["local"]["font"]) != effective(default), "local font does not contrast with the default")
    if baseline is None:
        return
    require(observed["local"] == baseline["local"], "local native/normalized font or identity changed")
    if scope == "dimensions":
        require(observed["inherited"]["name"] == baseline["inherited"]["name"], "inherited dimension identity changed")
    else:
        require(observed["name"] == baseline["name"], "General table identity changed")
    before = effective(baseline["inherited"]["font"])
    after = effective(observed["inherited"]["font"])
    require(all(before[name] != after[name] for name in STYLE),
            "inherited object did not demonstrate all five face/style changes")
    height_fields = set(after) - set(STYLE)
    require(any(before.get(key) != after[key] for key in height_fields),
            "inherited object did not demonstrate a height or mode change")
