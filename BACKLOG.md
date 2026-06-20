# PC迁移助手 — 项目 Backlog

> 活文档。按优先级排序，随项目演化持续更新。
>
> 决策原则：
> - **第一性原理**：拆解到不可约简的用户需求，从最简路径开始
> - **奥卡姆剃刀**：不增加超出当前问题范围的复杂度
> - **用户驱动**：家庭用户优先 → IT 爱好者/开发者

---

## 当前版本：v0.3

### 已交付

| 能力 | 文件 | 状态 |
|------|------|------|
| 全盘扫描 + 6 分类 | `disk_scanner.py`, `file_classifier.py` | ✅ |
| 系统路径/扩展名排除 | `default_rules.yaml` | ✅ |
| 权限错误处理 | `disk_scanner.py` | ✅ |
| 预扫描进度估计 | `disk_scanner.py` | ✅ |
| 搜索过滤 (ProxyModel) | `file_tree_filter.py` | ✅ |
| 文件打开/定位 | `file_tree_view.py` | ✅ |
| 迁移后校验 (xxHash/SHA-256) | `checksum.py`, `copier.py` | ✅ |
| 暂停/恢复迁移 | `migration_worker.py` | ✅ |
| 驱动器自动刷新 (3s轮询) | `target_page.py` | ✅ |
| FAT32 文件大小警告 | `win_utils.py`, `target_page.py` | ✅ |
| 浏览器书签检测 (6种) | `browser_detector.py` | ✅ |
| 双界面 (中/英) | 全局 | ✅ |
| 4步向导 UI | `main_window.py` + 4 pages | ✅ |
| GitHub Actions CI | `.github/workflows/build.yml` | ✅ |
| 迁移报告 (JSON + HTML) | `report_generator.py`, `migration_result.py` | ✅ |
| Treemap 容量热图 | `treemap_widget.py` | ✅ |
| theme.qss 现代化重写 | `theme.qss` | ✅ |
| README 英文版 | `README.md` | ✅ |
| 224 个测试 | `tests/` | ✅ |

---

## Sprint 0：迁移报告 ✅ 已完成

**目标**：备份后能知道"到底备份了哪些文件"。

### 设计

备份产出物：

```
U盘/
├── pc_migration_20260619.7z   ← 文件备份
├── manifest.json               ← 机器可读的完整清单
└── report.html                 ← 浏览器可读的可视化报告
```

**manifest.json** 结构：

```json
{
  "created": "2026-06-19T10:30:00",
  "source_pc": "DESKTOP-ABC123",
  "app_version": "0.3.0",
  "format": "7z",
  "verify_algorithm": "xxh64",
  "total_files": 15420,
  "total_size": 85899345920,
  "categories": {
    "documents":  { "count": 3200, "size": 2147483648 },
    "photos":     { "count": 8500, "size": 42949672960 },
    "videos":     { "count": 120,  "size": 21474836480 },
    "music":      { "count": 2400, "size": 17179869184 },
    "archives":   { "count": 150,  "size": 1073741824 },
    "browser_data": { "count": 6,  "size": 102400 },
    "other":      { "count": 1024, "size": 1073741824 }
  },
  "verify_results": {
    "passed": 15420,
    "failed": 0,
    "skipped": 0
  },
  "files": [
    {
      "path": "Documents/工作报告.docx",
      "size": 245760,
      "modified": 1718765400,
      "hash": "xxh64:a1b2c3d4e5f6a7b8",
      "category": "documents"
    }
  ],
  "errors": []
}
```

**report.html** 包含：
- 备份概览卡片（时间、PC名、格式、总文件数、总大小）
- 分类统计 + 彩色条形图
- 验证结果（全部通过 / 有失败）
- 按目录树浏览的完整文件列表（默认折叠，可展开）
- 浏览器 Ctrl+F 可直接搜索文件
- 零外部依赖（纯内联 CSS）

**生成时机**（用户决策）：
1. **扫描完成后** — 生成预览报告，用户可查看"扫到了哪些文件"，如有遗漏可手工调整策略后重新扫描
2. **迁移完成后** — 生成最终报告，包含校验结果，存入目标目录

### 任务

| ID | 任务 | 文件 | 估时 |
|----|------|------|------|
| REPORT-1 | `MigrationResult` 数据模型 | `src/models/migration_result.py` | ✅ 完成 |
| REPORT-2 | `manifest.json` 序列化 | `migration_result.py` | ✅ 完成 |
| REPORT-3 | `report.html` 生成器（输入 ScanResult 或 MigrationResult） | `src/utils/report_generator.py` | ✅ 完成 |
| REPORT-4 | 扫描完成后生成预览报告 — 集成到 ScanPage | `scan_page.py`, `scan_worker.py` | ✅ 完成 |
| REPORT-5 | 迁移完成后生成最终报告 — 集成到 MigrationWorker | `migration_worker.py` | ✅ 完成 |
| REPORT-6 | 测试 | `tests/test_migration_result.py`, `tests/test_report_generator.py` | ✅ 完成 |
| REPORT-7 | Windows 端到端测试（真实备份跑一次） | — | ⏳ 待用户重装时验证 |
| | **合计** | | **5天** |

### 验收标准

- [x] `manifest.json` 在备份完成后出现在目标目录（预览在 reports/，最终在目标目录）
- [x] `report.html` 在浏览器中打开显示正确的统计和文件列表
- [x] 每个文件记录 path / size / hash / category
- [x] 验证结果汇总列在报告顶部
- [x] 报告在无网络环境下可正常打开（零外部 CDN，纯内联 CSS）
- [x] 报告可通过浏览器打印为 A4 纸（已含 @media print 样式）

---

## Backlog

按优先级分组，同一组内按交付价值/成本比从高到低排列。

---

### 🔴 P1 — 核心品牌力（开源前必须完成）

#### Epic F：工程与平台

**动机**：开源项目的门面。没有好的 README 就没有人点进来，没有 CI 就没有人信任。

| ID | 任务 | 说明 | 优先级 | 估时 |
|----|------|------|--------|------|
| ENGiN-1 | **README 英文版** + 截图 + 徽章 | GitHub 项目品牌，第一印象 | 🔴 P1 | ✅ 完成 |
| ENGiN-3 | **Changelog / 发布流程** | 版本管理，发版自动化 | 🟡 P2 | 0.5天 |
| ENGiN-2 | **贡献指南 CONTRIBUTING.md** | 开源协作基础 | 🟡 P2 | 1天 |
| ENGiN-4 | **PyPI 发布**（可选） | `pip install pc-migrate` | 🟢 P4 | 1天 |

#### Epic A：UI 现代化

**动机**：家庭用户对工具的第一印象是"它专不专业"而不是"它功能多不多"。当前界面功能完整但视觉基础（默认 Qt 样式、硬编码颜色、纯文字列表）。目标是让界面看起来像 2020s 的桌面软件，而不是 2000s。

**设计原则**：所有样式集中在 `theme.qss`、专业化干净风格（参考 VS Code / SourceTree）、功能优先、装饰适度。

| ID | 任务 | 为什么做 / 不做 | 优先级 | 估时 |
|----|------|---------------|--------|------|
| UI-13 | **Treemap 容量热图** — 方块图替代条形图，显示目录大小权重 | click 方块联动文件树筛选 | 🔴 P1 | ✅ 完成 |
| UI-2 | **theme.qss 现代化重写** — 统一色板、干净卡片、合理间距 | 已使用 #2563EB 统一色板 | 🔴 P1 | ✅ 完成 |
| UI-7 | **分类颜色系统统一** — 颜色定义从 Python 移到 theme.qss | 🟡 当前 `size_stats_widget.py` 等硬编码颜色，改主题要改代码 | 🟡 P2 | 0.5天 |
| UI-4 | **驱动器卡片重设计** — 图标(USB/HDD/网络) + 容量条 | 🟡 当前是普通 QCheckBox 列表，选择目标时不够直观 | 🟡 P2 | 2天 |
| UI-1 | **应用图标** — .ico 文件 + 窗口图标 + 任务栏 | 🟡 默认 Qt 图标显业余，但用户更关心功能是否好用 | 🟡 P2 | 1天 |
| UI-3 | **步骤指示器图标** — 完成 ✓ / 当前数字 / 未来 ○ | 🟢 纯数字 + 文字能用，区分度低但不影响理解 | 🟢 P3 | 1天 |
| UI-8 | **字体系统** — Segoe UI (Win) / PingFang (中) 回退链 | 🟢 Qt 默认字体可用，Win10+ 自带 Segoe UI | 🟢 P3 | 1天 |
| UI-6 | **进度条动画** — 扫描/迁移时走动动画 | 🟢 静态跳变能用，动画是纯装饰 | 🟢 P3 | 1天 |
| UI-9 | **窗口状态持久化** — 记住大小、位置、上次页面 | 🟢 每次打开都默认大小，小 QoL 改进 | 🟢 P3 | 1天 |
| UI-12 | **键盘快捷键** — Tab 顺序、Enter 确认、Esc 取消 | ⚪ 家庭用户不依赖快捷键，IT 用户可以后续 PR | ⚪ P4 | 1天 |
| | | **合计（仅 P1/P2）** | | **~8.5天** |
| | | **合计（含 P3/P4）** | | **~13.5天** |

<!-- 装饰性 UI 任务已砍掉，见下方"已砍掉的特性" -->

---

### 🟡 P2 — 核心差异化

#### Epic B：应用数据检测

**动机**：用户重装后最容易遗漏 AppData 里的数据。用 `BrowserDetector` 同样的架构检测 SSH 密钥、微信记录、PST 邮件等。对你的优先级是中等（聊天记录可后续再补），但开源后是吸引贡献者的好切入点。

| ID | 任务 | 说明 | 估时 |
|----|------|------|------|
| APP-1 | `AppDataDetector` 模块骨架 | 检测器注册模式 | 1天 |
| APP-2 | SSH 密钥检测 | `%USERPROFILE%\.ssh\*` | 0.5天 |
| APP-3 | 微信聊天记录检测 | `%USERPROFILE%\Documents\WeChat Files\*` | 0.5天 |
| APP-9 | 集成到 `DiskScanner` | `scan(include_app_data=True)` | 0.5天 |
| APP-11 | 测试 | 覆盖所有检测器 + 集成 | 2天 |
| APP-4 | GPG 密钥检测 | `%USERPROFILE%\.gnupg\*` | 0.5天 |
| APP-5 | QQ 聊天记录检测 | `%USERPROFILE%\Documents\QQ\*` | 0.5天 |
| APP-6 | Outlook PST 检测 | `%APPDATA%\Microsoft\Outlook\*.pst` | 1天 |
| APP-7 | VS Code 配置检测 | `%APPDATA%\Code\User\settings.json` | 0.5天 |
| APP-8 | Steam 游戏存档检测 | Steam library + Saved Games | 1天 |
| APP-10 | 扫描完成弹窗提示"发现应用数据" | 确认是否纳入迁移 | 1天 |
| | **合计** | | **~9天** |

#### Epic D：迁移能力增强

| ID | 任务 | 说明 | 优先级 | 估时 |
|----|------|------|--------|------|
| MIG-1 | **分卷压缩** — 7z/ZIP 按指定大小分卷 | FAT32 4GB 限制解决方案 | 🟡 P2 | 3天 |
| MIG-2 | **断点续传** — 目标已存在文件按时间+大小跳过 | 中断后重跑不浪费时间 | 🟡 P2 | 2天 |
| MIG-3 | **`.migrate-plan` 配置保存** — 选择记录可再次加载 | 不用每次重新勾选 | 🟢 P3 | 2天 |
| MIG-5 | **迁移前后对比报告** — 源 vs 目标差异 | 确认完整性 | 🟢 P3 | 3天 |
| MIG-4 | **加密压缩 AES-256** — 密码保护的 7z | 隐私文件保护 | 🟢 P3 | 3天 |
| | | **合计** | | **~13天** |

#### Epic C：还原模式

**动机**：完整迁移闭环。当前只做了"旧电脑→U盘"，没有"U盘→新电脑"。对你个人不急（ZIP 解压即可），排在 P2 供社区贡献。

| ID | 任务 | 说明 | 优先级 | 估时 |
|----|------|------|--------|------|
| RESTORE-1 | `RestoreWorker` — 解压/复制 + 校验 | `src/migration/restore_worker.py` | 🟡 P2 | 2天 |
| RESTORE-2 | `restore` CLI 模式 | `main.py --restore <package>` | 🟡 P2 | 1天 |
| RESTORE-6 | 测试 | | 🟡 P2 | 2天 |
| RESTORE-3 | 预览界面 — 从 manifest.json 读取文件列表 | `restore_page.py` 步骤1 | 🟢 P3 | 1天 |
| RESTORE-4 | 路径选择 — 保持原结构 / 自定义根目录 | `restore_page.py` 步骤2 | 🟢 P3 | 1天 |
| RESTORE-5 | 执行 + 进度 + 完成报告 | `restore_page.py` 步骤3-4 | 🟢 P3 | 2天 |
| | | **合计** | | **~9天** |

---

### 🟢 P3+ — 远期扩展

#### Epic E：网络传输

| ID | 任务 | 说明 | 优先级 | 估时 |
|----|------|------|--------|------|
| NET-1 | **局域网发现** — 新/旧 PC 互相发现 | | 🟢 P3 | 3天 |
| NET-2 | **点对点传输** — TCP 直连文件传输 | USB 替代方案 | 🟢 P3 | 5天 |
| NET-3 | **传输加密** — TLS | | 🟢 P4 | 2天 |
| | | **合计** | | **~10天** |

---

### 已砍掉的特性（不进入 Backlog）

| 特性 | 砍掉理由 |
|------|---------|
| 云盘目标 (OneDrive/百度网盘) | 用户可手动上传到云盘，复杂度/价值比低 |
| 定时自动备份 | 这是迁移工具不是备份工具 |
| 应用迁移（免重装） | 需要 deep Windows 知识，商业软件核心壁垒 |
| UI 空状态插图 | 页面空白不影响功能，纯装饰 |
| UI 页面转场动画 | 瞬间切换完全可用，动画无功能价值 |
| UI 深色模式 | v0.x 不需要，且 Qt 深色模式需要大量适配工作 |

---

## 路线图总览

```
已完成 ─── v0.3 扫描 + 校验 + 浏览器书签 + 迁移报告 + Treemap + 主题 + README
    │
    ├── P1 │ ✅ README │ ✅ Treemap │ ✅ theme.qss │ ← 全部完成
    │
    │
    ├── P2 (~22.5天) ──────── 核心差异化
    │   ├── 应用数据检测 (SSH/微信/PST 等)
    │   ├── 分卷压缩 + 断点续传
    │   ├── UI 细节打磨 (驱动器卡片、图标、颜色)
    │   └── 还原模式 CLI
    │
    ├── P3 (~3天) ─────────── 体验提升
    │   ├── 步骤指示器图标、字体、进度动画
    │   └── 窗口状态持久化
    │
    └── P4+ ──────────────── 社区驱动
        ├── 局域网传输
        ├── 加密压缩
        ├── 键盘快捷键
        └── PyPI 发布
```

## 决策记录

| 日期 | 决策 | 理由 |
|------|------|------|
| 2026-06-19 | **还原模式排到 P2** | 用户个人当前不需要，ZIP 解压即可拿到文件 |
| 2026-06-19 | **CODE 分类暂不实现** | 当前用户不需要，等开源后 IT 用户提 PR |
| 2026-06-19 | **应用数据检测排 P2** | 用户个人优先级中等，开源后社区切入的好方向 |
| 2026-06-19 | **网络传输排 P3** | USB 已完成运输工作，网络是便利性不是必要性 |
| 2026-06-19 | **云盘目标已砍掉** | 复杂度/价值比低，用户可以手动上传到云盘 |
| 2026-06-19 | **定时备份已砍掉** | 这是迁移工具不是备份工具 |
| 2026-06-19 | **App迁移(免重装)已砍掉** | 需要 deep Windows 知识，商业软件核心壁垒 |
| 2026-06-19 | **迁移报告生成时机** | 扫描完成后立即生成预览报告（用户可检查是否有遗漏），迁移完成后生成最终报告 |

---

*最后更新：2026-06-19*
