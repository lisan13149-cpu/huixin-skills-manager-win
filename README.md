# 汇芯技能管家 · Windows 本地版

把 WorkBuddy、Claude Code、Codex、Gemini、Grok Bot、Agents 六个地方的技能，收进一个中文界面：
按用途分类、中文名搜索、看说明、复制调用名、打开文件位置。

原版是 macOS 的 SwiftUI 菜单栏应用，Windows 跑不了。这一版是重写的本地 Web 工具：
**Python 标准库 + 浏览器界面，零第三方依赖，不联网，不上传任何技能正文。**

## 一、怎么启动

双击 **`启动汇芯技能管家.bat`**。

- 会出现一个黑色命令行窗口，同时自动打开浏览器。
- 关掉命令行窗口就停止服务；浏览器可以一直开着。
- 整个文件夹可以随意移动（U 盘、桌面、D 盘都行），`%~dp0` 会自动找路径。

需要本机有 Python 3.8+。没有的话，启动脚本会明确提示，不会静默失败。

命令行方式（可选）：

```bat
python server.py
python server.py --port 9000          :: 换端口
python server.py --no-browser         :: 不自动开浏览器
```

## 二、界面里有什么

**左侧来源**：WorkBuddy / Claude Code / Codex / Gemini / Grok Bot / Agents 共享 / 项目。
没装的那个来源不会出现，不会显示一堆 0。

**按用途**：自动分 9 类——公众号与内容、视频制作、设计与配图、选题与调研、知识与沉淀、
商业与决策、企业与交付、办公与协作、开发与工具。规则是本地关键词打分，不调用模型。
分错了就在卡片右侧 **⋯ → 调整归类**，也可以「恢复自动归类」。

**我的分类**：侧栏「我的分类 ＋」新建，一个技能可以进多个分类。
分类只记在 `data/state.json`，**不动技能文件**。

**卡片**：中文名、原始调用名、说明摘要、分类标签、来源标签。
点卡片打开右侧详情：完整 SKILL.md（markdown 渲染）、复制调用名、复制路径、
在资源管理器里定位、用默认程序打开、收藏、加入分类。

**搜索**：中文名、原始名、文件夹名、说明、路径都能搜。按 `/` 直接聚焦搜索框。

**自动刷新**：每 8 秒检查一次目录变化，新增或删除技能会自动更新；也可以手动点「刷新」。

窄窗口下侧栏会收成两个下拉框，手机上也能看。

## 三、扫哪些目录

| 来源 | 默认路径 |
|---|---|
| WorkBuddy | `%USERPROFILE%\.workbuddy\skills` |
| Claude Code | `%USERPROFILE%\.claude\skills` |
| Codex | `%USERPROFILE%\.codex\skills` |
| Gemini | `%USERPROFILE%\.gemini\skills`、`%USERPROFILE%\.gemini\config\skills` |
| Grok Bot | `%USERPROFILE%\.grokbot\skills` |
| Agents 共享 | `%USERPROFILE%\.agents\skills` |
| 项目 | `state.json` 里 `projects` 列出的目录，扫其下 `.workbuddy/skills`、`.claude/skills`、`.agents/skills` 等 |

自动跳过 `node_modules`、`.git`、`build`、`dist`、`_backup_*`。
备份目录可以在「设置 → 显示备份技能」里打开。

## 四、边界（重要）

- **只读扫描**。不删除、不重命名、不改写任何 `SKILL.md`，也没有"删除技能"按钮。
- **不联网**。除了本机 `127.0.0.1`，没有任何外发请求。
- **写接口有令牌**。分类、收藏这类写操作要带启动时生成的 token，防止别的网页偷偷改你的数据。
- **数据在哪**：`data/state.json`。删掉它等于恢复出厂设置，技能文件不受影响。
- 详情里展示的是技能自己的 SKILL.md 全文，里面的命令不会被执行。

## 五、常见问题

**双击后提示 Python 3 was not found**
装一个 Python 3（勾选 Add to PATH），再双击。

**页面提示"没有访问令牌"**
用启动窗口里那行带 `?t=...` 的完整地址打开，不要手敲 `127.0.0.1:8765`。
令牌存在 sessionStorage 里，同一个标签页刷新不会丢。

**地址栏端口不是 8765**
8765 被占用时会自动往后找，以窗口里打印的地址为准。

**新增技能没出现**
点右上「刷新」。或者等 8 秒，工具会自动检测目录变化。

**中文名不对**
`server.py` 里的 `KNOWN_NAMES` 可以加映射，格式 `"folder-name": "中文名"`，保存后重启。
没映射的技能会从 description 第一句提炼，英文说明则显示英文摘要。

**想给它一个桌面图标**
右键 `启动汇芯技能管家.bat` → 发送到 → 桌面快捷方式。
想彻底脱离 Python，可以打包成 exe（需先 `pip install pyinstaller`）：

```bat
pyinstaller -F -w --add-data "web;web" server.py
```

## 六、和 macOS 原版的差异

| 能力 | 原版 | 这一版 |
|---|---|---|
| 平台 | macOS 14+ / Xcode 构建 | Windows 10/11，Python 3 |
| 中文展示名 | 内置映射 | 内置映射 + 说明提炼 |
| 工作流分类 | 本地规则 | 本地规则（9 类） |
| 自定义分类 / 收藏 | 有 | 有 |
| 打开文件位置 | Finder | 资源管理器 `/select` |
| 删除技能到废纸篓 | 有 | **不做**（避免误删） |
| 使用次数统计 | 仅 Codex | 不做（数据源不可靠就不编） |
| 菜单栏常驻 / ⌥⇧S | 有 | 无（浏览器标签页） |

## 七、文件结构

```
huixin-skills-manager-win/
├── 启动汇芯技能管家.bat   # 双击启动（内容纯 ASCII，避免 GBK 乱码）
├── server.py              # 扫描、解析、分类、HTTP 服务
├── web/
│   ├── index.html
│   ├── app.css
│   ├── app.js
│   └── favicon.svg
└── data/state.json        # 分类、收藏、设置（自动生成）
```

MIT，随意改。技能文件与中文映射的版权归各自作者。
