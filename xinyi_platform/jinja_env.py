from fastapi.templating import Jinja2Templates
from jinja2 import ChoiceLoader, FileSystemLoader

from xinyi_platform.ui_common.install import _TEMPLATE_DIR as _UI_TEMPLATE_DIR


def make_templates() -> Jinja2Templates:
    business_dir = "xinyi_platform/templates"
    templates = Jinja2Templates(directory=business_dir)
    templates.env.loader = ChoiceLoader([
        FileSystemLoader(business_dir),
        FileSystemLoader(str(_UI_TEMPLATE_DIR)),
    ])
    return templates
