from fastapi import Request


def build_template_context(request: Request) -> dict:
    ui = request.app.state.ui
    return {
        "current_service": ui["current_service"],
        "nav_menu": ui["nav_menu"],
        "brand": ui["brand"],
        "products": ui["products"],
        "platform_url": ui["platform_url"],
        "manager_url": ui.get("manager_url", ""),
        "service_prefix": ui.get("service_prefix", ""),
    }
