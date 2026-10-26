from __future__ import annotations

from pathlib import Path

import orjson
from pydantic import BaseModel

from .analysis_models import VirProject
from .ctl_models import CtlProgram
from .microscope_models import MicroscopeReport, StyleProfile
from .models import MonterProject
from .planning_models import EditPlan


def load_project(path: Path) -> MonterProject:
    return MonterProject.model_validate(orjson.loads(path.read_bytes()))


def load_vir(path: Path) -> VirProject:
    return VirProject.model_validate(orjson.loads(path.read_bytes()))


def load_edit_plan(path: Path) -> EditPlan:
    return EditPlan.model_validate(orjson.loads(path.read_bytes()))


def load_ctl(path: Path) -> CtlProgram:
    return CtlProgram.model_validate(orjson.loads(path.read_bytes()))


def load_microscope_report(path: Path) -> MicroscopeReport:
    return MicroscopeReport.model_validate(orjson.loads(path.read_bytes()))


def load_style_profile(path: Path) -> StyleProfile:
    return StyleProfile.model_validate(orjson.loads(path.read_bytes()))


def write_model(path: Path, model: BaseModel) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(orjson.dumps(model.model_dump(by_alias=True), option=orjson.OPT_INDENT_2))
