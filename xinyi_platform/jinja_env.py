from pathlib import Path

from fastapi.templating import Jinja2Templates
from jinja2 import ChoiceLoader, FileSystemLoader

from xinyi_platform.config import Settings
from xinyi_platform.ui_common.install import _TEMPLATE_DIR as _UI_TEMPLATE_DIR


def make_templates() -> Jinja2Templates:
    business_dir = "xinyi_platform/templates"
    templates = Jinja2Templates(directory=business_dir)
    templates.env.loader = ChoiceLoader([
        FileSystemLoader(business_dir),
        FileSystemLoader(str(_UI_TEMPLATE_DIR)),
    ])
    settings = Settings()
    templates.env.globals["brand"] = settings.brand_name
    templates.env.globals["platform_url"] = settings.base_url
    templates.env.globals["manager_url"] = settings.manager_url
    return templates
