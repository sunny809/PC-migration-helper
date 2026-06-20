"""ReportGenerator — generates migration reports (manifest.json + report.html).

Takes a MigrationResult and produces:
  - manifest.json: machine-readable file manifest
  - report.html:  human-readable visual report (self-contained, zero external deps)

Two usage modes:
  1. Preview: after scan completes, user can review what was found
  2. Final:   after migration completes, includes verification results
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Optional

from src.models.migration_result import MigrationResult
from src.utils.human_size import format_size
from src.utils.logger import setup_logging

logger = setup_logging()


class ReportGenerator:
    """Generates migration reports in JSON and HTML formats.

    Usage:
        generator = ReportGenerator()
        generator.generate(result, output_dir)
        # -> output_dir/manifest.json
        # -> output_dir/report.html
    """

    def generate(self, result: MigrationResult, output_dir: str,
                 prefix: str = "pc_migration") -> tuple[str, str]:
        """Generate both manifest.json and report.html.

        Args:
            result: MigrationResult to serialize.
            output_dir: Directory to write files into.
            prefix: Filename prefix (default "pc_migration").

        Returns:
            Tuple of (json_path, html_path).
        """
        os.makedirs(output_dir, exist_ok=True)

        # Determine filename suffix from timestamp
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        suffix = "preview" if result.is_preview else "final"

        json_path = os.path.join(output_dir, f"{prefix}_{suffix}_{ts}.json")
        html_path = os.path.join(output_dir, f"{prefix}_{suffix}_{ts}.html")

        # Write JSON
        result.to_json(json_path)
        logger.info(f"Generated manifest: {json_path}")

        # Write HTML
        html = self._generate_html(result)
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html)
        logger.info(f"Generated report:   {html_path}")

        return json_path, html_path

    def _generate_html(self, result: MigrationResult) -> str:
        """Generate a self-contained HTML report.

        Args:
            result: MigrationResult to render.

        Returns:
            Complete HTML string with inline CSS.
        """
        mode_label = "扫描预览 / Scan Preview" if result.is_preview else "迁移报告 / Migration Report"
        verify_color = "green" if result.verify_failed == 0 else "red"
        verify_icon = "✓" if result.verify_failed == 0 else "✗"

        # Category bars
        cat_bars_html = self._render_category_bars(result)

        # File tree
        file_tree_html = self._render_file_tree(result)

        # Stats
        total_size_str = format_size(result.total_size)

        return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{mode_label} — {result.source_pc}</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif; background: #f5f5f5; color: #333; padding: 24px; }}
.container {{ max-width: min(90%, 1200px); margin: 0 auto; }}
.header {{ background: linear-gradient(135deg, #2196F3, #1976D2); color: white; border-radius: 12px; padding: 32px; margin-bottom: 24px; }}
.header h1 {{ font-size: 24px; margin-bottom: 8px; }}
.header .meta {{ font-size: 14px; opacity: 0.9; }}
.header .meta span {{ display: inline-block; margin-right: 24px; }}
.cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 16px; margin-bottom: 24px; }}
.card {{ background: white; border-radius: 10px; padding: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); }}
.card .value {{ font-size: 28px; font-weight: bold; color: #2196F3; }}
.card .label {{ font-size: 13px; color: #888; margin-top: 4px; }}
.card.verify-pass .value {{ color: #4CAF50; }}
.card.verify-fail .value {{ color: #f44336; }}
.section {{ background: white; border-radius: 10px; padding: 24px; margin-bottom: 24px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); }}
.section h2 {{ font-size: 18px; margin-bottom: 16px; color: #333; border-bottom: 2px solid #f0f0f0; padding-bottom: 12px; }}
.bar {{ display: flex; align-items: center; margin-bottom: 8px; }}
.bar .label {{ width: 140px; font-size: 13px; color: #555; flex-shrink: 0; }}
.bar .track {{ flex: 1; height: 20px; background: #f0f0f0; border-radius: 4px; overflow: hidden; }}
.bar .fill {{ height: 100%; border-radius: 4px; }}
.bar .stat {{ width: 180px; text-align: right; font-size: 12px; color: #666; flex-shrink: 0; }}
.tree {{ font-size: 13px; }}
.tree details {{ margin-left: 16px; }}
.tree summary {{ cursor: pointer; padding: 4px 0; color: #333; }}
.tree summary:hover {{ color: #2196F3; }}
.tree .file {{ display: flex; align-items: center; padding: 3px 0 3px 16px; }}
.tree .file:hover {{ background: #f8f9fa; border-radius: 4px; }}
.tree .file .name {{ flex: 1; }}
.tree .file .size {{ color: #888; width: 80px; text-align: right; font-size: 12px; }}
.tree .file .hash {{ color: #bbb; font-family: monospace; font-size: 11px; margin-left: 12px; }}
.tree .file .status {{ width: 20px; text-align: center; font-size: 14px; }}
.status-ok {{ color: #4CAF50; }}
.status-failed {{ color: #f44336; }}
.errors {{ background: #fff3f3; border: 1px solid #ffcdd2; border-radius: 8px; padding: 16px; margin-top: 16px; }}
.errors h3 {{ color: #f44336; font-size: 14px; margin-bottom: 8px; }}
.errors ul {{ margin: 0; padding-left: 20px; font-size: 12px; color: #666; }}
.footer {{ text-align: center; font-size: 12px; color: #aaa; margin-top: 32px; padding: 16px; }}
@media print {{ body {{ padding: 0; background: white; }} .header {{ border-radius: 0; }} .card {{ box-shadow: none; border: 1px solid #ddd; }} .section {{ box-shadow: none; border: 1px solid #ddd; page-break-inside: avoid; }} }}
</style>
</head>
<body>
<div class="container">
<div class="header">
<h1>{mode_label}</h1>
<div class="meta">
<span>🖥 {result.source_pc}</span>
<span>🕐 {result.created}</span>
<span>📦 {result.format.upper()}</span>
<span>🔐 {result.verify_algorithm or "N/A"}</span>
</div>
</div>

<div class="cards">
<div class="card"><div class="value">{result.total_files:,}</div><div class="label">文件总数 / Total Files</div></div>
<div class="card"><div class="value">{total_size_str}</div><div class="label">总大小 / Total Size</div></div>
<div class="card"><div class="value">{len(result.categories)}</div><div class="label">文件分类 / Categories</div></div>
<div class="card {'verify-pass' if result.verify_failed == 0 else 'verify-fail'}"><div class="value">{verify_icon} {result.verify_summary}</div><div class="label">校验结果 / Verification</div></div>
</div>

<div class="section">
<h2>📊 分类统计 / Category Statistics</h2>
{cat_bars_html}
</div>

<div class="section">
<h2>📁 文件清单 / File List</h2>
<p style="font-size:12px;color:#888;margin-bottom:12px;">点击展开目录 / Click to expand folders</p>
{file_tree_html}
</div>

{"<div class='errors'><h3>⚠️ 错误 / Errors</h3><ul>" + "".join(f"<li>{e}</li>" for e in result.errors[:100]) + "</ul></div>" if result.errors else ""}

<div class="footer">
PC迁移助手 v{result.app_version} — 由开源工具 PC Migration Helper 生成
</div>
</div>
</body>
</html>"""

    def _render_category_bars(self, result: MigrationResult) -> str:
        """Render the category statistics bar chart section."""
        if not result.categories:
            return "<p style='color:#888;'>无数据 / No data</p>"

        max_size = max(c["size"] for c in result.categories.values())
        total = result.total_size or 1

        # Category color mapping (mirrors size_stats_widget.py)
        cat_colors = {
            "documents": "#2196F3",
            "photos": "#4CAF50",
            "videos": "#FF9800",
            "music": "#9C27B0",
            "archives": "#795548",
            "browser_data": "#E91E63",
            "other": "#9E9E9E",
        }

        # Category display names
        cat_display = {
            "documents": "文档 / Documents",
            "photos": "照片 / Photos",
            "videos": "视频 / Videos",
            "music": "音乐 / Music",
            "archives": "压缩包 / Archives",
            "browser_data": "浏览器 / Browser Data",
            "other": "其他 / Other",
        }

        bars = []
        for cat_key in sorted(result.categories.keys()):
            info = result.categories[cat_key]
            pct = info["size"] / total * 100
            width_pct = info["size"] / max_size * 100 if max_size > 0 else 0
            color = cat_colors.get(cat_key, "#9E9E9E")
            display = cat_display.get(cat_key, cat_key)
            size_str = format_size(info["size"])

            bars.append(f"""<div class="bar">
<div class="label">{display}</div>
<div class="track"><div class="fill" style="width:{width_pct:.1f}%;background:{color};"></div></div>
<div class="stat">{info['count']:,} 文件 / {size_str} ({pct:.1f}%)</div>
</div>""")

        return "\n".join(bars)

    def _render_file_tree(self, result: MigrationResult) -> str:
        """Render the file list as an expandable directory tree."""
        if not result.files:
            return "<p style='color:#888;'>无文件 / No files</p>"

        # Build tree structure from flat file paths
        tree: dict = {}
        for f in result.files:
            parts = f.path.split("/")
            node = tree
            for part in parts:
                if part not in node:
                    node[part] = {}
                node = node[part]
            # Store file info at the leaf
            node["__file__"] = f

        return self._render_node(tree, "")

    def _render_node(self, node: dict, path_prefix: str) -> str:
        """Recursively render a directory tree node."""
        items = []
        # Separate directories and files
        dirs = {k: v for k, v in node.items() if not k.startswith("__") and isinstance(v, dict) and "__file__" not in v}
        files = {k: v for k, v in node.items() if isinstance(v, dict) and "__file__" in v}

        # Render directories first (sorted)
        for name in sorted(dirs.keys()):
            sub = dirs[name]
            sub_path = f"{path_prefix}{name}/"
            children = self._render_node(sub, sub_path)
            if children.strip():
                items.append(f"""<details>
<summary>📁 {name}/</summary>
{children}
</details>""")
            else:
                items.append(f"<div style='padding:2px 0 2px 32px;color:#999;font-size:12px;'>📁 {name}/</div>")

        # Render files (sorted)
        for name in sorted(files.keys()):
            f = files[name]["__file__"]
            size_str = format_size(f.size)
            status_icon = "✓" if f.status == "ok" else "✗"
            status_cls = "status-ok" if f.status == "ok" else "status-failed"
            hash_display = f.hash[:16] + "…" if len(f.hash) > 20 else f.hash

            items.append(f"""<div class="file">
<span class="status {status_cls}">{status_icon}</span>
<span class="name">📄 {name}</span>
<span class="size">{size_str}</span>
<span class="hash">{hash_display}</span>
</div>""")

        return "\n".join(items)
