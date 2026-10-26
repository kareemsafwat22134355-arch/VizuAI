from __future__ import annotations

from pathlib import Path

import orjson
from pydantic import BaseModel

from .analysis_models import VirProject
from .models import MonterProject


def load_project(path: Path) -> MonterProject:
    return MonterProject.model_validate(orjson.loads(path.read_bytes()))


def load_vir(path: Path) -> VirProject:
    return VirProject.model_validate(orjson.loads(path.read_bytes()))


def write_model(path: Path, model: BaseModel) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(orjson.dumps(model.model_dump(by_alias=True), option=orjson.OPT_INDENT_2))
