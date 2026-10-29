# test（原型人格洞察 · 每日一测）

基于荣格八功能与 45 种经典人物原型的每日人格测试网页（HTML 问答应用）。

## 语言 / 类型
- 类型：静态网页问答应用（浏览器直接打开）
- 语言：HTML + CSS + JavaScript
- 非 Python 项目

## 目录要点
- `test.html` —— 页面入口（依次加载 style.css / questions.js / app.js）
- `app.js` —— 主逻辑（每日次数限制、计分、结果展示）
- `questions.js` —— 题库（128 题 × 4 选项 + 45 原型，由 gen.js 生成）
- `gen.js` —— Node.js 题库生成脚本（`node gen.js` 重新生成 questions.js）
- `style.css` —— 样式

## 运行方式与依赖
- 运行：用浏览器打开 `test.html` 即可（无需服务器、无需构建）。
- 重新生成题库：`node gen.js`

## 测试状态
- 静态检查通过（未运行；纯前端页面，需浏览器打开验证）。
