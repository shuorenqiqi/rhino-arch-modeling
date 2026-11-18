# 连接与诊断（把"折腾三轮"压成一次）

---

## 一、三条命令接通

```bash
PY="$HOME/.workbuddy/binaries/python/envs/default/Scripts/python.exe"   # 换成你自己的 python（需 pywin32）
SK="$HOME/.workbuddy/skills/rhino-arch-modeling/scripts"

"$PY" "$SK/rhino_conn.py"          # 连通 + 窗口归位 + 体检报告
"$PY" "$SK/probe_state.py"         # 只读：文档/图层/视口/包围盒
"$PY" "$SK/ink_stats.py" out.png   # 出图后量化验收
```

代码里：

```python
import os
import sys
sys.path.insert(0, os.path.expanduser(r"~/.workbuddy/skills/rhino-arch-modeling/scripts"))
from rhino_conn import connect, ensure_window, describe, save_as, shot, packed

dispatch, rs, ver = connect()      # 有实例复用，没有则拉起（18 次 × 6 s）
ensure_window()                    # ★ 出图前必做，否则全是线框
print(describe(rs))                # 先看，再动手
```

**为什么这样能"快"**：
1. `RSProxy` 强制 `DISPATCH_METHOD` + **缓存 dispid** —— 第二次调用同一方法不再走
   `GetIDsOfNames`，批量建模时省掉几万次 COM 往返。
2. 一次 `connect()` 内完成"拉起 → 等窗口 → 附着 → 真活探测"，不用分三步手试。
3. 真活探测用 `DocumentName()`（带参方法）而不是 `Version()`（属性）——
   `Version()` 能返回但带参方法全返回 None，正是 P01 的假成功。

---

## 二、失败时的决策树（按这个顺序，别跳）

> **第 0 步永远是**：`tasklist | findstr /i rhino` —— 数一下有几个 `Rhino.exe`。
> **两个以上**就先解决它：`Dispatch` 只给其中一个，可能不是用户那个正活（P03b）。
> 用 `assert_doc(rs, "文件名关键词")` 核对，连错就停。

```
connect() 抛 RuntimeError
│
├─ ⓪ 有几个 rhino.exe？
│   ├─ ≥2 → 用 assert_doc 核对文档名；不对就请用户关掉多余实例
│   └─ 1 → ①
│
├─ ① psutil 查 rhino.exe
│   ├─ 没有 → 启动失败。spawn() 单独试；仍失败 → 看事件日志（勿改任何东西）
│   └─ 有 → ②
│
├─ ② EnumWindows 按 pid 列顶层窗口，看它停在哪
│   ├─ 主窗口 Afx:...:Rhinoceros 全【隐藏】
│   │   + 唯一可见窗口标题含「授权」
│   │   → 停在授权对话框。**汇报，不动手。**（用户可能没有官方账号）
│   ├─ 唯一可见窗口是「插件程序载入失败」小框
│   │   → 旧插件 vs 新 Rhino（P40）。点「是」跳过；别删用户装的东西
│   ├─ 唯一可见窗口是个 289×164 的「Rhinoceros 8」启动画面
│   │   （截图里常写着 Retrieving License Info）
│   │   → 还在启动/等授权。**此状态下出图必空**（P38），先别出
│   ├─ 主窗口在 (-21333,-21333) → 窗口在屏幕外 → ensure_window()
│   └─ 有正常主窗口 → ③
│
├─ ③ Dispatch 失败？
│   ├─ 是 → Rhino 还没注册 COM（冷启动需要 30–90 s）→ 加长 retry
│   └─ 否 → ④
│
└─ ④ GetScriptObject 成功但方法返回 None
        → P01：你拿到的是裸 dispatch，不是 RSProxy
```

**枚举窗口的最小实现**：

```python
import win32gui, win32process
def windows_of(pid):
    out = []
    def cb(hwnd, _):
        _, wpid = win32process.GetWindowThreadProcessId(hwnd)
        if wpid == pid:
            out.append((hwnd,
                        win32gui.IsWindowVisible(hwnd),
                        win32gui.GetClassName(hwnd),
                        win32gui.GetWindowText(hwnd),
                        win32gui.GetWindowRect(hwnd)))
        return True
    win32gui.EnumWindows(cb, None)
    return out
```

判读规则：
- `Afx:...:Rhinoceros` + 全部 `visible=False` → 主界面还没进
- `HwndWrapper[DefaultDomain;;...]` + 标题含「授权」→ 授权对话框
- `rect[0] == -21333` → 屏幕外

---

## 三、冷启动时序（别抢跑）

```
双击/拉起 → 主窗口标题出现（含 " - "） → 再等 10~13 s → COM 才真正可用
```
早 attach 的典型结果是 `Dispatch 成功、GetScriptObject 成功、然后所有方法返回 None`
或直接 `RPC 服务器不可用`。

`connect()` 默认 `retry=18, wait=6`，即最多等 108 s，覆盖这个空窗。

---

## 四、出图前的四件套（缺一件就出废图）

```python
from rhino_conn import shot_views, window_ready, ensure_window, MODE_WIRE

print(window_ready())                # ① 主窗口真的在屏幕上？
shot_views(rs, outdir, "v1",         # ②③④ 全在里面：
           views=("Perspective","Top","Front","Right"))
#   内部依次：ensure_window → ViewDisplayMode → _-SetView 复位 → frame_all(包围盒)
#             → CreatePreviewImage → 数非背景像素（为 0 直接报错）
```

手写时对应的 ④ 是——**必须按模型包围盒取景**，不能假设模型在原点：
```python
from rhino_conn import frame_all
frame_all(rs, "Perspective", pad=1.12)
```
2026-11-03 事故：相机停在 `(0,0,0)`、模型中心在 `x=7.7` → **四张图全空**，
误以为是模型没建出来（P38）。

平面视口要 `_-SetView _World _Top`；**对 Top 视口执行 `_Perspective` 会把它变成斜视**。
正交图（平行投影）**必须单独脚本**跑，别混进透视流程。

⚠️ **出图全空时的排查顺序**：窗口可见？→ 相机在包围盒上？→ 线色是不是白底白线（P39）
→ 最后才怀疑模型。**顺序反了就会白改一遍几何。**

---

## 五、卡死了怎么救

**症状**：脚本跑了几分钟没输出，Rhino CPU 占用 0.00 s（空闲），Python 卡在 COM 等待。
**根因**：`rs.Command()` 在等用户输入 —— 最典型是 `-_Open` / `-_SaveAs`
在**有未保存改动**的文档上弹了保存框。

```python
from rhino_conn import rescue
rescue()      # AppActivate + 连发 3 次 ESC
```

**预防**（比救援重要）：
```python
from rhino_conn import assert_clean
assert_clean(rs, "打开/关闭文档")      # dirty 就抛错，不弹框
```
`-_Open` / `-_Close` / `-_New` 之前一律先过这一条。

### 「保存改变为 未命名?」自己弹出来了怎么办
**不要代用户点「否」**——那会把未存盘的模型直接丢弃（本项目 61 个对象差点这样没了）。
正确动作：
1. 先判断文档是不是用户的活（`rs.DocumentName()`；空串 = 从没存过）。
2. 需要保命 → `save_as(rs, folder, "未命名_抢救副本")`，先落盘再谈别的。
3. 然后**把弹框交给用户**，或只按 ESC 取消（= 不关闭，继续用）。

`rescue()` 只用于"我自己的脚本把 Rhino 卡住"；用户正在手动操作时**别抢他的键**。

---

## 六、环境事实（本机，别记错）

| 项 | 值 |
|---|---|
| Rhino | `D:\Program Files\Rhino 8\System\Rhino.exe`（**D 盘**，不在 C 盘） |
| 版本 | **8.31.26126.13431**（2026-11-03 实测；10-09 之前是 8.25.25314） |
| Python（必须） | 任意 Python 3.x，**必须装 pywin32**（如 WorkBuddy 托管 Python 或系统 Python） |
| rhinorouter（可选） | `~/.workbuddy/skills/rhinorouter`，没有也能跑（少两个兜底函数） |
| 出图临时目录 | `%TEMP%\yzt_*`（`CreatePreviewImage` 先写这儿，再 copy 到 `_preview`） |

⚠️ **Rhino 升级过**：8.31 上 `D5Conv.rhp`（2025-12 编译的旧 D5 LiveSync）会加载失败并卡启动（P40）。
遇到"启动慢/弹插件框"别当崩溃处理。

`managed` 版 Python 缺 `pythoncom`，用了必报 ModuleNotFoundError。

---

## 七、🚫 红线：不要碰授权与网络

本机 `hosts` 有 3 行把 `api.mcneel.com` 指到本机：

```
127.0.0.1 api.mcneel.com
0.0.0.1   api.mcneel.com
0.0.0.1   api.mcneel.com/license/invalidate
```

**这不是垃圾、不是劫持、不是故障。这是用户非官方授权通道的前提。**

**2026-10-09 事故**：我判断它是"加速器劫持的 DNS"，提权注释掉 → Rhino 立刻要求
重新认证 → 用户没有官方账号 → 直接把能用的 Rhino 弄坏。只能逐字节还原
（1390 B，sha `1cea6f7f…`）。

**纪律（不可协商）**：
1. 不修改 hosts、不改代理、不改注册表授权项、不"帮它恢复联网校验"。
2. Rhino 打不开 → **只做只读诊断 + 如实汇报**，处置权交用户。
3. 判断"某现象是故障"之前，先确认它是不是用户**刻意设置的常态**。
4. 系统级文件默认不可写。**提权能力 ≠ 行动许可。**
5. 遇到"要提权才能做"的操作，单独、原话再问一次"这个可以改吗"，
   不要把"你选哪种修法"当成"可以删"。
