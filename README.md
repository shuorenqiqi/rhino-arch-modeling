# Rhino Arch Modeling — WorkBuddy 连接 Rhino 的建模技能

> **WorkBuddy 连接 Rhino 建模的 skill**：更快连接 Rhino 8 与 WorkBuddy，可自行轻微调整模型精度；
> 建模成果非特殊说明为**黑白素模、不附带材质**（线框黑线 · 着色黑面白边 · 渲染纯白）。

这是一个面向 **Windows + Rhino 8** 的实战型技能包，把「脚本连不上 Rhino」「线框是白线」
「出图全空」「渲染全透明」这类坑全部固化成了可复用的代码与清单。

---

## 它解决什么问题

| 场景 | 能力 |
|---|---|
| 连不上 Rhino / 带参方法静默失败 | `rhino_conn.py` 用 `RSProxy`（纯 DISPATCH_METHOD + 缓存 dispid）稳定连接，5 分钟上手 |
| 线框白线、模型看不见 | `bw_style()` / `bw_style_mat()` 一键黑白素模，线框黑线、着色黑面、渲染纯白 |
| 出图全空 / 跑出线框 | `shot_views()` 自动取景 + 窗口守卫 + 空图自检 |
| 渲染模式整栋楼“透明” | `audit_materials()` / `reset_materials()` + `fix_render_materials.py` 一键修 |
| 改完模型不知道对不对 | `ink_stats.py` 量化验收，不靠肉眼 |
| 换台电脑不会建模 | 图纸量测、参数曲面、构件密度、交付自查清单，附云在亭完整模板 |

**模型精度可自行微调**：所有形体由一个 `surf()` 参数曲面驱动，改形状只动文件头部常量区，
改完重跑即可；出图前有 17 项精细度自查。

---

## 安装

```bash
git clone https://github.com/<your-name>/rhino-arch-modeling.git \
  "%USERPROFILE%\.workbuddy\skills\rhino-arch-modeling"
```

或直接下载 ZIP，解压到：

```
%USERPROFILE%\.workbuddy\skills\rhino-arch-modeling\
```

## 环境要求

- Windows 10/11
- Rhino 7 / Rhino 8（脚本按 8 编写，7 部分可用）
- Python 3.x，**必须安装 `pywin32`**：`pip install pywin32`
- 可选：`rhinorouter`（少两个兜底函数也能跑）

## 30 秒上手

```bash
PY="$HOME/.workbuddy/binaries/python/envs/default/Scripts/python.exe"   # 换成你自己的 python（需 pywin32）
SK="$HOME/.workbuddy/skills/rhino-arch-modeling/scripts"

"$PY" "$SK/rhino_conn.py"        # 连通 + 窗口归位 + 体检
"$PY" "$SK/probe_state.py"       # 只读：文档 / 图层 / 视口 / 包围盒
```

```python
import os, sys
sys.path.insert(0, os.path.expanduser(r"~/.workbuddy/skills/rhino-arch-modeling/scripts"))
from rhino_conn import connect, ensure_window, bw_style, shot_views

dispatch, rs, ver = connect()      # 有实例复用，没有则拉起
ensure_window()                    # 出图前必做
bw_style(rs)                       # 默认交付：黑白素模
shot_views(rs, outdir, "v1")       # 四视图一次出完
```

---

## 目录结构

```
rhino-arch-modeling/
├── SKILL.md                     # 技能主文档：10 条铁律 + 标准流程 + 自查表
├── references/
│   ├── connection.md            # 连接决策树 / 卡死救援 / 环境事实
│   ├── modeling-craft.md        # 图纸量测 / 参数曲面 / 构件密度
│   ├── pitfalls.md              # 45 条实测踩坑（症状 → 根因 → 修法）
│   ├── styling.md               # 黑白素模 / 剪影 / 白模的准确做法
│   └── yunzaiting.md            # 云在亭完整参数与版本史
└── scripts/
    ├── rhino_conn.py            # 连接器 + 样式 + 出图 + 材质修复
    ├── probe_state.py           # 只读体检
    ├── ink_stats.py             # 出图量化验收
    └── fix_render_materials.py  # 渲染“全透明”一键修
```

## 默认成果样式

非特殊说明，交付一律为 **黑白素模、不附带材质**：

| 模式 | 效果 |
|---|---|
| 线框 | 黑线 |
| 着色 | 黑面 + 白色网格边 |
| 渲染 | 纯白素模（不挂材质） |

需要其他样式（自然色 / 纯黑剪影 / 彩色）时，明说即可切换。

## 说明

- 本技能绑定「本机 Rhino + COM 自动化」这条件，坑库中的实测结论请结合自己的 Rhino 版本参考。
- 不涉及任何授权绕过；Rhino 的启动与授权方式由使用者自行负责。
