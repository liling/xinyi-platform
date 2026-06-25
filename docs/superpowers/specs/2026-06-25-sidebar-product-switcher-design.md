# 左侧边栏产品切换器设计

## 背景与目标

xinyi-platform 生态目前有多个管理后台产品：

- Hindsight Manager
- DocuPipe Manager
- Platform Control Center (xinyi)
- 未来可能增加：Agent Center、Ontology Manager

这些产品共享 `xinyi-platform/ui_common` 提供的左侧边栏（`ui/app_shell.html` + `ui/sidebar.html`）。

当前产品切换入口藏在右上角用户菜单里，只有 admin 用户在 Platform Control Center 时才能看到所有业务产品链接，普通用户和各业务产品内不易发现。

**目标**：在左侧边栏顶部增加一个显眼的「当前产品」切换器，让用户随时知道自己所在的产品，并一键跳转到其他产品首页。

## 现状

- `ui_common/templates/ui/sidebar.html` 渲染左侧边栏：brand logo、用户名、`nav_menu` 分组导航。
- `ui_common/templates/ui/topbar.html` 右上角用户菜单里已使用 `products` 列表做产品切换，但入口深且受权限限制。
- `ui_common/service_discovery.py::build_product_list()` 会在每个服务启动时构建产品列表：
  - 平台账户中心（固定第一项）
  - 所有已注册且 `status == ACTIVE`、`base_url` 不为空的 `business_clients`
  - 每个产品带 `is_current` 标记
- `ui_common/install.py::ui_jinja_globals()` 将 `products` 注入所有模板。
- 各业务服务（如 hindsight-manager）启动时已调用 `build_product_list()` 并刷新 `app.state.ui["products"]`。

## 设计方案：方案 A（侧栏顶部「当前产品」下拉切换器）

在 `sidebar.html` 的 `.sidebar-header` 内部、brand 区域下方新增一个产品切换器。

### UI 结构

```html
<div class="sidebar-header">
  <div class="sidebar-brand"> ... </div>
  <p class="user-info">{{ current_user.username }}</p>

  <!-- 新增 -->
  <div class="product-switcher">
    <button type="button" class="product-switcher-btn" aria-haspopup="true" aria-expanded="false">
      <span class="product-switcher-current">{{ current_product.label }}</span>
      <svg class="product-switcher-chevron" ...>...</svg>
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
```

- `current_product` 在模板中通过 `{% set current_product = products | selectattr('is_current', 'equalto', true) | first %}` 取得；若取不到则回退显示 `brand`。
- 下拉列表复用 `build_product_list()` 返回的顺序。
- 当前项只读展示，非当前项为链接。

### 交互逻辑

在 `sidebar.html` 底部内联一段 JS：

- 点击 `.product-switcher-btn` 切换下拉 `hidden` 类，并更新 `aria-expanded`。
- 点击下拉外部、按 `Esc`、或点击产品链接后关闭下拉。
- 无 JS 降级时，按钮不会展开下拉，用户仍可通过 topbar 用户菜单切换。

### 样式

在 `ui_common/static/ui.css` 新增：

- `.product-switcher`：与深色侧栏风格一致。
- `.product-switcher-btn`：宽度撑满，显示产品名 + chevron，hover 高亮。
- `.product-switcher-dropdown`：绝对定位，深色背景 + 阴影，覆盖在侧栏内容上方。
- `.product-switcher-item`：链接/只读项统一样式，hover 背景 `--sidebar-hover`。
- `.product-switcher-item-current`：当前项加左边框或品牌主色背景。
- 响应式：移动端侧栏变为顶部栏时，下拉宽度适配。

颜色继续使用现有 CSS 变量：`--sidebar-bg`、`--sidebar-hover`、`--sidebar-text`、`--primary`。

### 数据与权限

- 复用现有 `products` 数据流，不新增后端接口。
- **可见性**：所有登录用户均可在侧栏看到切换器。
- 未来如需按角色灰显某些产品，可在 `build_product_list()` 产物中增加 `visible` / `disabled` 字段，模板根据该字段渲染。

### 顶部菜单清理

`topbar.html` 用户菜单中旧的产品切换逻辑（`{% for p in products if p.kind == 'business' %}` 等）与侧栏重复，应移除或简化为仅保留「个人中心」「退出登录」。

## 改动范围

**xinyi-platform 仓库：**

1. `xinyi_platform/ui_common/templates/ui/sidebar.html` — 新增产品切换器 HTML + JS。
2. `xinyi_platform/ui_common/static/ui.css` — 新增 `.product-switcher*` 样式。
3. `xinyi_platform/ui_common/templates/ui/topbar.html` — 移除用户菜单里旧的产品切换链接。

**无需改动（已具备支持）：**

- `xinyi_platform/ui_common/install.py`：已注入 `products`。
- `xinyi_platform/ui_common/service_discovery.py`：已提供 `build_product_list()`。
- 各业务服务（hindsight-manager、docupipe-manager 等）：启动时已经构建 `products`；升级 `xinyi-platform` 依赖即可生效。

## 成功标准

- 在 Hindsight Manager、DocuPipe Manager、Platform Control Center 的任意后台页面，左侧边栏顶部均显示当前产品名。
- 点击切换器后展开所有已注册产品的下拉列表。
- 选择其他产品后，浏览器跳转至该产品首页；由于 SSO，用户无需重新登录。
- 当前产品在下拉中高亮但不可点击。
- 移动端侧栏适配正常。
- topbar 用户菜单不再重复显示产品切换入口。

## 未解决的问题

- 产品数量较多（>6）时，下拉是否需要支持搜索或滚动？当前设计使用固定高度滚动容器即可。
- 是否需要为每个产品配置独立图标/颜色？当前 `BusinessClient` 已有 `logo_url` 字段，但设计初版可先不展示图标，后续再迭代。
