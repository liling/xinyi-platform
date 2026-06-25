# 左侧边栏产品切换器实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 xinyi-platform 共享 UI 的左侧边栏顶部增加一个产品切换器，让用户能一键跳转到其他已注册的业务产品首页。

**Architecture:** 复用已有的 `products` 数据流（由 `service_discovery.build_product_list()` 注入模板），在 `sidebar.html` 中渲染当前产品和下拉列表；新增专用 CSS 保持深色侧栏风格；从 `topbar.html` 用户菜单中移除重复的产品切换入口。

**Tech Stack:** Python 3.12, FastAPI, Jinja2, HTML/CSS, pytest

## Global Constraints

- 所有改动在 `xinyi-platform` 仓库内完成。
- 不新增后端接口或数据库字段；复用现有 `products` 数据。
- 产品切换器对所有登录用户可见（不再限制 admin / platform 服务）。
- 移动端侧栏布局需正常适配。
- 无 JS 降级：切换器只显示当前产品名，不展开下拉。

---

## File Structure

| File | Responsibility |
|------|----------------|
| `xinyi_platform/ui_common/templates/ui/sidebar.html` | 渲染左侧边栏；新增产品切换器 HTML 和内联 JS |
| `xinyi_platform/ui_common/static/ui.css` | 新增 `.product-switcher*` 样式 |
| `xinyi_platform/ui_common/templates/ui/topbar.html` | 移除用户菜单里重复的产品切换链接 |
| `tests/test_ui_integration.py` | 验证 sidebar / topbar 渲染行为 |
| `tests/test_ui_install.py` | 验证 UI 静态资源存在（已有，视情况更新断言） |

---

### Task 1: 在 sidebar.html 中渲染产品切换器

**Files:**
- Modify: `xinyi_platform/ui_common/templates/ui/sidebar.html`
- Test: `tests/test_ui_integration.py`

**Interfaces:**
- Consumes: Jinja 上下文 `products`（来自 `ui_jinja_globals`），每个元素包含 `id`, `label`, `subtitle`, `url`, `kind`, `is_current`。
- Produces: HTML 元素 `.product-switcher`，供 Task 2 的 CSS 和浏览器 JS 选择器使用。

- [ ] **Step 1: Write the failing test**

在 `tests/test_ui_integration.py` 末尾添加：

```python
def test_sidebar_renders_product_switcher():
    from jinja2 import ChoiceLoader, Environment, FileSystemLoader
    from xinyi_platform.ui_common.install import _TEMPLATE_DIR as UI_TEMPLATE_DIR

    env = Environment(loader=ChoiceLoader([
        FileSystemLoader(UI_TEMPLATE_DIR),
    ]))
    template = env.get_template("ui/sidebar.html")

    html = template.render(
        request=type("R", (), {"url": type("U", (), {"path": "/xinyi/account"})()})(),
        current_user={"username": "alice", "role": "member"},
        brand="平台",
        service_prefix="/xinyi",
        products=[
            {
                "id": "platform",
                "label": "平台账户中心",
                "subtitle": "用户 · 审计 · 登录历史",
                "url": "http://xinyi.test/xinyi/account",
                "kind": "platform",
                "is_current": True,
            },
            {
                "id": "hindsight-manager",
                "label": "Hindsight Manager",
                "subtitle": "RAG 记忆库",
                "url": "http://hm.test/hindsight/dashboard",
                "kind": "business",
                "is_current": False,
            },
        ],
    )
    assert 'class="product-switcher"' in html
    assert "平台账户中心" in html
    assert "Hindsight Manager" in html
    assert "http://hm.test/hindsight/dashboard" in html
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_ui_integration.py::test_sidebar_renders_product_switcher -v
```

Expected: FAIL with `AssertionError` because `.product-switcher` is not present.

- [ ] **Step 3: Write minimal implementation**

修改 `xinyi_platform/ui_common/templates/ui/sidebar.html`，完整内容如下：

```html
<nav class="sidebar">
    <div class="sidebar-header">
        <div class="sidebar-brand">
            <img src="{{ service_prefix }}/_ui/static/logo.svg" alt="{{ brand }}" class="sidebar-logo">
            <h3>{{ brand }}</h3>
        </div>
        <p class="user-info">{{ current_user.username }}</p>

        {% set current_product = products | selectattr('is_current', 'equalto', true) | first %}
        <div class="product-switcher">
            <button type="button" class="product-switcher-btn" aria-haspopup="true" aria-expanded="false">
                <span class="product-switcher-current">{{ current_product.label if current_product else brand }}</span>
                <svg class="product-switcher-chevron" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg>
            </button>
            <div class="product-switcher-dropdown hidden">
                {% for p in products %}
                    {% if p.is_current %}
                    <span class="product-switcher-item product-switcher-item-current">
                        <span class="product-switcher-name">{{ p.label }}</span>
                        <span class="product-switcher-subtitle">{{ p.subtitle }}</span>
                    </span>
                    {% else %}
                    <a href="{{ p.url }}" class="product-switcher-item">
                        <span class="product-switcher-name">{{ p.label }}</span>
                        <span class="product-switcher-subtitle">{{ p.subtitle }}</span>
                    </a>
                    {% endif %}
                {% endfor %}
            </div>
        </div>
    </div>
    <div class="sidebar-nav">
        {% set _path = request.url.path %}
        {% for section in nav_menu %}
            {% if not section.get('require_admin') or current_user.get('role') == 'admin' %}
            <div class="nav-section-title">{{ section.label }}</div>
            {% for item in section['items'] %}
            {% set _isActive = _path == item.href or _path.startswith(item.href + '/') %}
            <a href="{{ item.href }}" class="nav-item{% if _isActive %} active{% endif %}">{{ item.label }}</a>
            {% endfor %}
            {% endif %}
        {% endfor %}
    </div>
</nav>

<script>
(function () {
  const switcher = document.querySelector('.product-switcher');
  if (!switcher) return;
  const btn = switcher.querySelector('.product-switcher-btn');
  const dropdown = switcher.querySelector('.product-switcher-dropdown');
  if (!btn || !dropdown) return;

  function toggle(show) {
    const isHidden = dropdown.classList.contains('hidden');
    const shouldShow = show === undefined ? isHidden : show;
    dropdown.classList.toggle('hidden', !shouldShow);
    btn.setAttribute('aria-expanded', String(shouldShow));
  }

  btn.addEventListener('click', function (e) {
    e.stopPropagation();
    toggle();
  });

  document.addEventListener('click', function () {
    toggle(false);
  });

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') toggle(false);
  });
})();
</script>
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_ui_integration.py::test_sidebar_renders_product_switcher -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add xinyi_platform/ui_common/templates/ui/sidebar.html tests/test_ui_integration.py
git commit -m "feat(ui): render product switcher in sidebar"
```

---

### Task 2: 添加产品切换器样式

**Files:**
- Modify: `xinyi_platform/ui_common/static/ui.css`
- Test: `tests/test_ui_integration.py`

**Interfaces:**
- Consumes: HTML class names from Task 1: `.product-switcher`, `.product-switcher-btn`, `.product-switcher-current`, `.product-switcher-chevron`, `.product-switcher-dropdown`, `.product-switcher-item`, `.product-switcher-item-current`, `.product-switcher-name`, `.product-switcher-subtitle`.
- Produces: CSS rules that style the switcher to match the dark sidebar.

- [ ] **Step 1: Write the failing test**

在 `tests/test_ui_integration.py` 末尾添加：

```python
def test_ui_css_includes_product_switcher_styles():
    from pathlib import Path
    css_path = Path(__file__).resolve().parent.parent / "xinyi_platform" / "ui_common" / "static" / "ui.css"
    css = css_path.read_text(encoding="utf-8")
    assert ".product-switcher" in css
    assert ".product-switcher-btn" in css
    assert ".product-switcher-dropdown" in css
    assert ".product-switcher-item-current" in css
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_ui_integration.py::test_ui_css_includes_product_switcher_styles -v
```

Expected: FAIL because the selectors do not exist in `ui.css`.

- [ ] **Step 3: Write minimal implementation**

在 `xinyi_platform/ui_common/static/ui.css` 中 `.sidebar-header` 样式之后、` .sidebar-nav` 样式之前插入：

```css
/* ── Product Switcher ── */
.product-switcher {
    margin-top: 14px;
    position: relative;
}
.product-switcher-btn {
    width: 100%;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    padding: 8px 12px;
    background: rgba(255,255,255,.06);
    border: 1px solid rgba(255,255,255,.08);
    border-radius: var(--radius-sm);
    color: #fff;
    font-size: 13.5px;
    font-weight: 600;
    cursor: pointer;
    transition: background var(--transition), border-color var(--transition);
}
.product-switcher-btn:hover {
    background: rgba(255,255,255,.1);
    border-color: rgba(255,255,255,.14);
}
.product-switcher-btn[aria-expanded="true"] .product-switcher-chevron {
    transform: rotate(180deg);
}
.product-switcher-chevron {
    flex-shrink: 0;
    transition: transform var(--transition);
}
.product-switcher-dropdown {
    position: absolute;
    top: calc(100% + 6px);
    left: 0;
    right: 0;
    background: #1e293b;
    border: 1px solid rgba(255,255,255,.08);
    border-radius: var(--radius-sm);
    box-shadow: var(--shadow-md);
    padding: 6px;
    z-index: 40;
}
.product-switcher-item {
    display: flex;
    flex-direction: column;
    gap: 2px;
    padding: 8px 10px;
    border-radius: 6px;
    color: var(--sidebar-text);
    text-decoration: none;
    font-size: 13px;
    transition: background var(--transition), color var(--transition);
}
.product-switcher-item:hover {
    background: var(--sidebar-hover);
    color: #fff;
    text-decoration: none;
}
.product-switcher-item-current {
    background: rgba(79,70,229,.18);
    color: #fff;
    cursor: default;
}
.product-switcher-name {
    font-weight: 600;
}
.product-switcher-subtitle {
    font-size: 11.5px;
    color: var(--sidebar-text);
    line-height: 1.35;
}
.product-switcher-item-current .product-switcher-subtitle,
.product-switcher-item:hover .product-switcher-subtitle {
    color: inherit;
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_ui_integration.py::test_ui_css_includes_product_switcher_styles -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add xinyi_platform/ui_common/static/ui.css tests/test_ui_integration.py
git commit -m "feat(ui): add product switcher styles"
```

---

### Task 3: 清理 topbar.html 中重复的产品切换入口

**Files:**
- Modify: `xinyi_platform/ui_common/templates/ui/topbar.html`
- Test: `tests/test_ui_integration.py`

**Interfaces:**
- Consumes: `current_service`, `products`, `platform_url` from Jinja context.
- Produces: Simpler user menu dropdown with only account and logout entries.

- [ ] **Step 1: Write the failing test**

在 `tests/test_ui_integration.py` 末尾添加：

```python
def test_topbar_user_menu_does_not_repeat_product_switcher():
    from jinja2 import ChoiceLoader, Environment, FileSystemLoader
    from xinyi_platform.ui_common.install import _TEMPLATE_DIR as UI_TEMPLATE_DIR

    env = Environment(loader=ChoiceLoader([
        FileSystemLoader(UI_TEMPLATE_DIR),
    ]))
    template = env.get_template("ui/topbar.html")

    html = template.render(
        request=type("R", (), {"url": type("U", (), {"path": "/xinyi/account"})()})(),
        current_user={"username": "alice", "role": "admin"},
        brand="平台",
        service_prefix="/xinyi",
        platform_url="http://xinyi.test",
        current_service="platform",
        products=[
            {
                "id": "hindsight-manager",
                "label": "Hindsight Manager",
                "subtitle": "RAG 记忆库",
                "url": "http://hm.test/hindsight/dashboard",
                "kind": "business",
                "is_current": False,
            },
        ],
    )
    # Old logic rendered each business product as a user-menu-item link.
    assert "Hindsight Manager" not in html
    assert 'href="http://hm.test/hindsight/dashboard"' not in html
    # Account and logout should remain.
    assert "个人中心" in html
    assert "退出登录" in html
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_ui_integration.py::test_topbar_user_menu_does_not_repeat_product_switcher -v
```

Expected: FAIL because the old product links are still rendered.

- [ ] **Step 3: Write minimal implementation**

将 `xinyi_platform/ui_common/templates/ui/topbar.html` 中用户菜单的产品切换逻辑替换为仅保留账户和退出登录：

```html
<header class="topbar">
    <div class="topbar-brand">
        <img src="{{ service_prefix }}/_ui/static/logo.svg" alt="{{ brand }}" class="topbar-logo">
        <span class="topbar-brand-name">{{ brand }}</span>
    </div>
    <div class="topbar-actions">
        <div class="user-menu">
            <button type="button" class="user-menu-btn" onclick="document.getElementById('user-menu').classList.toggle('hidden')">
                <span class="topbar-username">{{ current_user.username }}</span>
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 12 15 18 9"/></svg>
            </button>
            <div id="user-menu" class="user-menu-dropdown hidden">
                <a class="user-menu-item" href="{{ platform_url }}/account">个人中心</a>
                <hr class="user-menu-divider">
                <form method="post" action="{{ service_prefix }}{% if current_service == 'platform' %}/logout{% else %}/auth/logout{% endif %}" style="margin:0;padding:0">
                    <button type="submit" class="user-menu-item user-menu-logout" style="width:100%;text-align:left;border:none;background:none;cursor:pointer">退出登录</button>
                </form>
            </div>
        </div>
    </div>
</header>
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_ui_integration.py::test_topbar_user_menu_does_not_repeat_product_switcher -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add xinyi_platform/ui_common/templates/ui/topbar.html tests/test_ui_integration.py
git commit -m "refactor(ui): remove duplicate product switcher from topbar user menu"
```

---

### Task 4: 运行全量测试并做端到端验证

**Files:**
- No file changes.
- Verification: browser / TestClient / manual smoke test.

- [ ] **Step 1: Run full test suite**

```bash
uv run pytest
```

Expected: All tests pass.

- [ ] **Step 2: Start xinyi-platform locally**

```bash
uv run uvicorn xinyi_platform.main:app --reload --port 8000
```

- [ ] **Step 3: Verify sidebar product switcher renders**

1. 打开浏览器访问 `http://localhost:8000/xinyi/account` 并登录。
2. 左侧边栏顶部应看到当前产品名（例如「平台账户中心」）。
3. 点击后展开下拉，显示所有已注册产品。
4. 点击其他产品链接，浏览器跳转至该产品首页。

- [ ] **Step 4: Verify a business service (optional but recommended)**

1. 在 `hindsight-manager` 仓库中确保依赖的 `xinyi-platform` 已更新（editable install 会自动生效）。
2. 启动 hindsight-manager：`uv run uvicorn hindsight_manager.main:app --reload --port 8001`
3. 访问 `http://localhost:8001/hindsight/dashboard`。
4. 左侧边栏顶部应显示「Hindsight Manager」，下拉中列出平台账户中心和其他产品。

- [ ] **Step 5: Commit any additional fixes if needed**

If no fixes are needed, no commit is required in this task.

---

## Self-Review

**Spec coverage:**
- 侧栏顶部产品切换器：Task 1
- 深色侧栏样式：Task 2
- 所有登录用户可见：Task 1 中未加权限判断，默认全部渲染
- 顶部菜单去重：Task 3
- 移动端适配：Task 2 CSS 使用相对定位和百分比宽度
- 无 JS 降级：Task 1 中 `hidden` 类默认隐藏下拉，无 JS 时按钮点击不生效

**Placeholder scan:** 所有步骤包含完整代码和命令，无 TBD/TODO。

**Type consistency:** 模板中使用的字段 `id`, `label`, `subtitle`, `url`, `kind`, `is_current` 与 `build_product_list()` 返回结构一致。
