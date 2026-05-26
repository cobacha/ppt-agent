# 单页重新生成提示词

你正在重新生成一份演示文稿中的某一页幻灯片。你必须：

1. 匹配整体风格（字体、颜色、间距），与前后页保持一致
2. 使用指定的布局模式
3. 遵守视口适配规则：
   - 幻灯片 section 必须在 `height: 100vh; overflow: hidden` 内正常显示
   - 所有文字使用 `clamp()` 实现响应式字号
   - 内容密度在限制范围内（最多 5-6 个要点）
4. 只返回 `<section class="slide">...</section>` 的 HTML — 不要包裹层、不要 doctype、不要 style 块

父级演示文稿的 CSS 类和变量已经可用，直接使用即可（例如 `var(--accent-blue)`、`class="reveal"` 等）。
