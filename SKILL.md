---
name: rhino-arch-modeling
version: 1.3.0
display_name: Rhino 建筑曲面建模（快连 + 黑线自然成图）
display_name_en: Rhino Architectural Modeling — Fast Connect & Black-Line Output
description: Use whenever the task involves Rhino on this machine — building or iterating any 3D model (architecture, pavilion, landscape structure), editing a .3dm file, changing display/colors/materials, rendering or exporting views. Triggers include: Rhino, Rhino 8, 建模, 改模型, 3dm, 树院, 驿站, 亭子, 黑模/白模/素模, 出图/渲染. Provides a battle-tested connector (RSProxy / DISPATCH_METHOD), a 46-entry verified pitfall index, parametric-surface modeling craft, and the 云在亭 (Cloud Pavilion) reference template. Default output is the BLACK & WHITE presentation model — black wireframe lines, black shaded faces with white edges, pure-white render — via bw_style() / bw_style_mat() unless the user asks otherwise.
description_zh: **任何涉及 Rhino 的建模/改模型/出图任务一律先加载本技能**（触发词：Rhino、建模、3dm、树院、驿站、亭子、黑模/白模/素模、出图、渲染）。本机 Rhino 8 建筑曲面建模全流程：5 分钟接通 COM、参数曲面建模、构造分层，附 46 条实测踩坑速查与云在亭完整参数模板。**默认交付"黑白素模"**（2026-11-03 用户定稿）：线框黑线、着色黑面白边、渲染纯白——`bw_style()` / `bw_style_mat()` 一键到位；只有用户明说才做别的样式。
---

# Rhino 建筑曲面建模（快连 + 自然成图）

> **通用版（可分享）**：路径全部改成 `~/.workbuddy/...` 自动定位，不再写死用户名。
> 使用前提：① 本机已装 Rhino 7/8；② 运行脚本的 Python 已装 `pywin32`。
> 安装位置：`%USERPROFILE%\.workbuddy\skills\rhino-arch-modeling\`


## 什么时候用这个技能

- 用 Rhino 8 建/改**建筑形体**（壳体、曲面屋面、杆件束、格构），脚本驱动
- 需要**快速连上**本机 Rhino，不想再重走"折腾三轮 COM"
- 要按图纸还原一栋真实建筑，需要"比例尺 → 参数 → 构件密度"的完整方法
- 出图验收（着色模式自然色 / 剪影 / 白模）

**不用于**：纯 API 查签名（用 `rhinorouter`）、非本机 Rhino、SU/Blender。

---

## 30 秒上手

```bash
PY="$HOME/.workbuddy/binaries/python/envs/default/Scripts/python.exe"   # 换成你自己的 python（需 pywin32）
SK="$HOME/.workbuddy/skills/rhino-arch-modeling/scripts"

"$PY" "$SK/rhino_conn.py"        # ① 连通 + 窗口归位 + 体检
"$PY" "$SK/probe_state.py"       # ② 只读：文档 / 图层 / 视口 / 包围盒
```

```python
import os
import sys
sys.path.insert(0, os.path.expanduser(r"~/.workbuddy/skills/rhino-arch-modeling/scripts"))
from rhino_conn import (connect, ensure_window, describe, save_as,
                        bw_style, restore_layers, shot_views, window_ready, packed,
                        set_materials, audit_materials, render_bg, reset_materials)

dispatch, rs, ver = connect()     # 有实例复用，没有则拉起（18×6s）
ensure_window()                   # ★ 出图前必做：不做，出图全是线框
print(describe(rs))               # 先看清，再动手

saved = bw_style(rs)              # ★ 默认交付：线框黑线 + 着色黑面 + 渲染纯白
render_bg(rs)                     # ★ 白模必须配灰底，否则渲染模式"看不见"（P45）
assert not audit_materials(rs)    # ★ 还有对象带透明度 = 渲染会整批透明（P44）
shot_views(rs, outdir, "v1")      # ★ 四视图一把出，自带取景 + 空图自检
```

**为什么不是 `rhinorouter.get_rhino()`**：它优先返回**裸 PyIDispatch**，
pywin32 默认用 `METHOD|PROPERTYGET`，Rhino 8 拒绝这个组合 →
**带参方法全部静默返回 None**（AddPoint 返回 None、AllObjects 还是 0，看着像成功）。
必须用 `RSProxy`（纯 `DISPATCH_METHOD` + 缓存 dispid）。详见 `references/pitfalls.md` P01/P02。

---

## 十条铁律

1. **默认黑白素模（2026-11-03 用户定稿，替代旧"自然色"默认）。**
   用户原话："以后所有的建模都是这样子的"（附云在亭 v25 三张截图）：
   **线框 = 黑线 · 着色 = 黑面白边 · 渲染 = 纯白素模**。
   → 一键用 `bw_style(rs)`：对象显示色压黑（线框+着色黑）+ 图层色改白（渲染纯白），
     返回原图层色 dict 交给 `restore_layers()` 可还原。
   ⚠️ 仍然绝对不要把材料白写进图层色还指望线框跟着变——对象色必须是 ByObject=黑，
   图层色只影响渲染通道（两层分工见 `styling.md` §1/§5）。
   ⚠️ bw_style 的图层白会让**图层面板一片白**；用户接受不了（2026-11-03 追加定稿
   "图层要黑的"）就改用 `bw_style_mat(rs)`：图层全黑 + 两把共享材质接管渲染
   （建筑白/场地浅灰），渲染观感不变（见 `styling.md` §1.6）。
   用户明说要做别的样式（自然色 / 纯黑剪影 / 彩色）才换挡，见 `references/styling.md`。
2. **先量图纸，再建模。** 用图内**比例尺刻度**做像素量测（四段互校），
   绝不用"假设总高"反推 —— 那是循环论证，本项目因此整体小了 1.47 倍。
3. **动手前只读体检。** `probe()`：文档名 / `DocumentModified` / 对象数 / 视口模式 /
   包围盒 / 主窗口是否在屏幕上。`DocumentModified == True` 就**停**，问用户。
   **本机常同时开两个 Rhino 实例**（一个正活 + 一个空的"未命名"）——
   改之前用 `assert_doc(rs, "文件名关键词")` 核对，别改到另一个去。
4. **形状只有一个源。** 一个 `surf(th, t, offset)`，所有面层和构件从它取点。
   改形状只改文件头部常量区。**永不散落在各函数里。**
5. **面层偏移沿法向，不加 Z。** 陡坡上 Z 偏移的法向分量趋近 0 → 瓦垄被埋、檐口露白边。
6. **杆件要连续。** 屋面梁与柱肋同一条曲线、同数量（32/32）。断头就是"两层感"。
7. **只建图纸上能指认的构件。** 想在落地处"补个支墩让它站得住"属于改设计。
8. **不动全局显示模式。** `ViewDisplayModeProperty` 是用户级配置、跨文档持久，
   曾把线框模式 `ShowEdges` 关掉 → 线框全空（0.00% 像素）、以后每个文件都中招。
9. **出图四件套**：`ensure_window()` + 显式 `ViewDisplayMode` + `_-SetView` 复位视口
   + **`frame_all()` 框到包围盒**。直接用 `shot_views()`，别手写循环。
   **出图全空时先查"窗口/相机"，不要改模型**（P38：主窗口被启动画面挡住 +
   相机还停在 `(0,0,0)`，四张图全空，模型完全没问题）。
   正交（平行投影）宁可单独脚本跑，不要混进透视流程（P25）。
10. **🚫 不碰授权/网络/hosts。** 本机 hosts 里屏蔽 McNeel 的行是用户授权通道的前提。
    Rhino 打不开 → **只读诊断 + 如实汇报**，处置权交用户。（真实事故，见 P34）

---

## 标准流程

```
① 读资料      图纸 PDF / 实景照 / 分析图 → 抠出：比例尺、剖面母线形状、构造层顺序
② 认形体      一句话说清它是"什么"（例：歪掉的斗笠，不是云）
③ 只读体检    rhino_conn.connect() + probe_state.py
④ 参数建模    常量区 → surf() → 分层建构件（建对象前 rs.CurrentLayer）
⑤ 出图验收    black_lines() → shot_views() 四视图 → ink_stats 量化 → 对表
             （bbox / 母线残差 / 剪影宽度）；全空先查窗口与相机，别改模型
⑥ 交付        另存新版本号（不覆盖用户认可的那版）；旧版送回收站，不永久删
```

每一步的细节：

| 阶段 | 看哪份 |
|---|---|
| 连接 / 诊断 / 卡死救援 / 环境事实 | `references/connection.md` |
| 图纸量测 / 参数曲面 / 构件密度 / 精细度自查 | `references/modeling-craft.md` |
| 症状 → 根因 → 修法（42 条） | `references/pitfalls.md` |
| 云在亭完整参数与版本史 | `references/yunzaiting.md` |
| 自然色 / 黑模 / 白模 / 出图量化 | `references/styling.md` |

---

## 踩坑速查（高频 12 条，全表见 pitfalls.md）

| 症状 | 根因 | 修法 |
|---|---|---|
| 方法返回 None，文档是空的 | 裸 dispatch + METHOD\|PROPERTYGET | 用 RSProxy |
| **线框是白线，看不见模型** | **材料白被写进图层色**（线框画图层色） | `black_lines(rs)`：对象色压黑，图层色留材料色 |
| **预览图全空 / NO INK** | 主窗口被启动画面挡住 + 相机在 `(0,0,0)` | 查 `window_ready()`；`shot_views()` 自动 frame |
| 出图全是线框 | 自动化窗口在 (-21333,-21333) | `ensure_window()` |
| 线框模式全空（0 像素） | `ViewDisplayModeProperty` 关掉了 ShowEdges | 恢复该模式的那几个键，永不全局改 |
| 杆件只有一半长 | `AddPipe` 的 parameters 是起止参数，不是半径点 | `[dom[0], dom[1]]` |
| 颜色改不动 | 传了 `[r,g,b]` 列表 | 打包整数 `r+g*256+b*65536` |
| 改图层色没生效 | `AddLayer` 对已存在图层是空操作 | 补 `LayerColor(L, c)` |
| 陡坡一片光板 / 檐口白边 | 面层偏移加在 Z 上 | 沿 `surf_n()` 法向偏移 |
| 整圈檐口悬空 | `max(z, 0.40)` 之类的 clamp | 软下限 `0.5(z+√(z²+ε))` |
| 顶部是平盘 / 一调就烟囱 | W99 下限恒等于洞口直径 | 洞口下沉 `RIM_DIP`，不是调坡度 |
| 平视顶部是弧线 | 降坡用了 smoothstep+幂 | 降坡与半径共用同一个 `t**RT_POW` |
| 保存失败 | `-_SaveAs` 传了引号绝对路径 | `WorkingFolder` + 裸文件名 |
| 启动卡在「插件程序载入失败」 | 旧版 D5 LiveSync vs Rhino 8.31 | 点「是」跳过，官网装新版（P40） |
| 弹「保存改变为 未命名?」 | dirty 文档被 Close/Open/New | **绝不代点「否」**，`assert_clean()`（P41） |
| **渲染模式整栋楼透明** | `MaterialTransparency` 写进了被共享的材质槽 | `reset_materials()` / `fix_render_materials.py`（P44） |
| **白模在渲染里看不见（不是透明）** | 纯白材质 + 纯白背景 | `render_bg(rs)` 改中性灰（P45） |
| 脚本卡死几分钟 | `-_Open` 在 dirty 文档上弹保存框 | 先查 `DocumentModified()`；`rescue()` 发 ESC |

---

## 精细度自查（交付前逐条过，答不上就是没核对）

开口尺寸/位置 · 柱径与柱形（喇叭 or 沙漏）· 柱肋数=屋面梁数 · 整圈是否悬空 ·
拱腿是垂直下探还是斜坡 · 顶部是尖脊还是平盘 · 母线是直是弧 · 竹瓦盖到哪 · 玻璃是否连续 ·
有没有断头杆件 · 有没有臆造构件 · 屋脊高与图纸差多少 · 有没有空图层 · 出图有没有被相机污染。

**另加三条"这一轮踩出来的"**：
- 线框**是不是黑线**（不是材料色）？
- 预览图**框住了模型**吗（bbox 中心 ≠ 原点时尤其要看）？
- 有没有留下**未答复的模态框**（插件框 / 保存框）？

**再加一条（2026-11-04）**：**切到 Render 模式看一眼**，并 `audit_materials(rs)`——
渲染通道是唯一"改完当时看不出来、交付时才炸"的地方（P44/P45）。
只信着色模式，等于没验收。

---

## 变更记录

| 版本 | 改了什么 | 起因 |
|---|---|---|
| 1.3.0 | ① 新增 `audit_materials()` / `set_materials()` / `reset_materials()` / `render_bg()`，材质写入一律**回读复核**<br>② 新增 `scripts/fix_render_materials.py` 一键修"渲染模式全透明"<br>③ pitfalls 补 P44（`MaterialTransparency` 污染共享材质槽 → 整栋楼透明）、P45（白模无灰底 = 假透明）<br>④ styling §2 换成安全写法；自查表加"切 Render 复验"一条 | 2026-11-04：竹亭交付后用户切渲染模式发现"全透明"，实测 1266 个对象材质透明度全是 0.82 |
| 1.2.1 | ① 新增 `bw_style_mat()`（图层黑 + 两把共享材质接管渲染），styling.md 补 §1.6 —— 图层面板全白被用户打回<br>② pitfalls 补 P42（`-_Save` 卡死 / 覆盖同名静默跳过 / save_as 返回值对覆盖不可信 → mtime 硬校验）、P43（改文档必须单脚本一口气跑完，跨脚本状态必丢） | 2026-11-03：驿站 v4→v5，用户看图层面板问"为什么全白，要黑的" |
| 1.2.0 | **默认交付改为"黑白素模"**：新增 `bw_style()`（对象色黑 + 图层色白 = 线框黑线/着色黑面/渲染纯白）与 `restore_layers()`；铁律第 1 条、30 秒上手、frontmatter 同步改写 | 2026-11-03：用户发云在亭 v25 三张截图定稿："以后所有的建模都是这样子的" |
| 1.1.0 | ① 默认交付改为 **黑线**：新增 `black_lines()` / `restore_bylayer()`；删掉"图层色=材料自然色"这条错规则<br>② 出图改为 `shot_views()`：自动 `frame_all` + 窗口可见性守卫；新增 `window_ready()` / `model_bbox()`<br>③ 新增 `assert_clean()`，禁止在 dirty 文档上跑 Open/Close/New<br>④ pitfalls 补 P38（全空图）、P39（白线）、P40（插件框）、P41（保存框）、P03b（多实例连错）<br>⑤ 环境事实更正为 Rhino 8.31.26126；新增 `assert_doc()` 防多实例误改 | 2026-11-03：按 skill 建完模型，线框是白线看不见；四张预览图全空；启动被 D5 旧插件卡住；同时开了两个 Rhino |
| 1.0.0 | 首版：连接器 + 37 条坑 + 建模手法 + 云在亭模板 | 2026-11-03 会话复盘 |

---

## 一个必须记住的判断习惯

用户说"**这块这么稀疏结构你自己看看对吗**""**两侧为啥不着地**""**顶面应该在一条直线上**"
—— 这些听上去是审美，**实际全是代码里的具体错误**：`AddPipe` 半根、clamp、幂函数。

所以顺序永远是：**先量化 → 再定位代码 → 最后改参数**。
反过来的结果就是"改了一版，用户说还是不对"。

---

## 相关技能

- `rhinorouter` —— 1245 个官方 API 离线库 + 通用 COM 连接器。
  写不熟的函数先用它查签名：`scripts/get_function_detail.py --search AddPipe`
- 本技能是**工作流与实战层**，两者配合用：查签名找 rhinorouter，干活用这里的 `rhino_conn`。
