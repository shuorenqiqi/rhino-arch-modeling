# -*- coding: utf-8 -*-
"""rhino_conn.py —— 本机 Rhino 8 COM 连接器（经实战验证，可直接 import）

为什么不能直接用 `rhinorouter.get_rhino()`：
    它优先走"回退路径 0"，返回**裸 PyIDispatch**。pywin32 默认用
    METHOD|PROPERTYGET 组合标志调用，而 Rhino 8 (.NET COM) 拒绝这个组合 ——
    结果是**带参数的方法静默返回 None**（AddPoint 返回 None、AllObjects 仍是 0），
    看起来像"执行成功"，其实什么都没建。

唯一可靠姿势：
    Dispatch -> GetScriptObject -> 裸 dispatch 包装成 RSProxy（强制 DISPATCH_METHOD）
    + 缓存 dispid（第二次调用不再走 GetIDsOfNames，快一个数量级）

用法：
    from rhino_conn import connect, ensure_window, probe, save_as, shot
    dispatch, rs, ver = connect()          # 已有实例则复用，没有则拉起
    n = len(rs.AllObjects() or [])
"""
import os
import sys
import time

RHINO_EXE_CANDIDATES = [
    r"D:\Program Files\Rhino 8\System\Rhino.exe",
    r"C:\Program Files\Rhino 8\System\Rhino.exe",
    r"D:\Program Files\Rhino 7\System\Rhino.exe",
]
RHINOROUTER_DIR = os.path.expanduser(r"~/.workbuddy/skills/rhinorouter")  # 可选依赖，不存在会跳过

# 显示模式索引（本机实测：越界索引静默无效，不会报错）
MODE_WIRE, MODE_SHADED, MODE_RENDER = 0, 1, 2


# ---------------------------------------------------------------- 颜色打包
def packed(r, g, b):
    """RhinoScript 颜色参数只吃【打包整数】。传 [r,g,b] 列表会报
    `Type mismatch in parameter. Integer required.`"""
    return int(r) + int(g) * 256 + int(b) * 65536


def unpack(c):
    c = int(c)
    return (c & 0xFF, (c >> 8) & 0xFF, (c >> 16) & 0xFF)


BLACK = packed(0, 0, 0)
WHITE = packed(255, 255, 255)


# ---------------------------------------------------------------- 代理
class RSProxy:
    """RhinoScript 晚绑定代理：缓存 dispid，强制纯 DISPATCH_METHOD。

    RSProxy.__getattr__ 里 **绝对不能** 用 getattr(ole, name) ——
    那会退回 pywin32 的动态绑定路径（METHOD|PROPERTYGET），全线失败。
    """

    def __init__(self, ole):
        object.__setattr__(self, "_ole", ole)
        object.__setattr__(self, "_ids", {})

    def _id(self, name):
        ids = object.__getattribute__(self, "_ids")
        if name not in ids:
            try:
                ids[name] = object.__getattribute__(self, "_ole").GetIDsOfNames(0, name)
            except Exception as e:
                raise AttributeError("RhinoScript 无此成员: %s (%s)" % (name, e))
        return ids[name]

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        ole = object.__getattribute__(self, "_ole")
        dispid = self._id(name)

        def caller(*args):
            import pythoncom
            return ole.Invoke(dispid, 0, pythoncom.DISPATCH_METHOD, True, *args)

        object.__setattr__(self, name, caller)
        return caller

    def __repr__(self):
        return "<RSProxy>"


def _dispatch(progids):
    import win32com.client.dynamic as wcdyn
    last = None
    for progid in progids:
        try:
            d = wcdyn.Dispatch(progid)
            if d is not None:
                return d, None
        except Exception as e:
            last = "%s -> %s" % (progid, e)
    return None, last


def _script_of(dispatch):
    import pythoncom
    ole = dispatch._oleobj_
    dispid = ole.GetIDsOfNames(0, "GetScriptObject")
    return ole.Invoke(dispid, 0, pythoncom.DISPATCH_METHOD, True)


def _alive_proc():
    try:
        import psutil
    except Exception:
        return []
    out = []
    for p in psutil.process_iter(["pid", "name"]):
        if (p.info.get("name") or "").lower() == "rhino.exe":
            try:
                out.append((p.info["pid"], p.cmdline()))
            except Exception:
                out.append((p.info["pid"], None))
    return out


def spawn(timeout=180):
    """独立进程拉起 Rhino（DETACHED + 新进程组），等主窗口出现。"""
    import subprocess
    exe = next((p for p in RHINO_EXE_CANDIDATES if os.path.exists(p)), None)
    if not exe:
        raise RuntimeError("找不到 Rhino.exe，候选路径都不存在：%s" % RHINO_EXE_CANDIDATES)
    flags = 0x00000008 | 0x00000200
    p = subprocess.Popen([exe], creationflags=flags, close_fds=True)
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _alive_proc():
            return p.pid
        time.sleep(1.0)
    raise TimeoutError("Rhino 启动超时（%ds），检查是否卡在授权对话框" % timeout)


def connect(auto_spawn=True, retry=18, wait=6.0, verbose=True):
    """返回 (dispatch, rs, version)。失败抛 RuntimeError。

    retry×wait 的默认值 18×6=108s —— 覆盖"冷启动 Rhino 到 COM 就绪"的实测时长。
    """
    import pythoncom
    pythoncom.CoInitialize()

    if not _alive_proc():
        if not auto_spawn:
            raise RuntimeError("没有运行中的 Rhino 进程")
        if verbose:
            print("[conn] 无 Rhino 进程，拉起 %s" % RHINO_EXE_CANDIDATES[0])
        spawn()

    if RHINOROUTER_DIR not in sys.path:
        sys.path.insert(0, RHINOROUTER_DIR)
    try:
        from rhinorouter import connector as conn
        conn.clear_gen_py_cache()      # 清掉可能残缺的 gen_py，避免 EnsureModule 报错
    except Exception:
        pass

    dispatch = None
    last = None
    for attempt in range(retry):
        if dispatch is None:
            for ver in (8, 7, 6):
                dispatch, last = _dispatch([
                    "Rhino.Interface.%d" % ver, "Rhino.Application.%d" % ver,
                ])
                if dispatch:
                    break
            if dispatch is None:
                dispatch, last = _dispatch(["Rhino.Application", "Rhino.Interface"])
        if dispatch is None:
            if verbose:
                print("[conn] %d/%d Dispatch 失败: %s" % (attempt + 1, retry, last))
            time.sleep(wait)
            continue
        try:
            rs = RSProxy(_script_of(dispatch))
            ver = rs.Version()
            # 真活探测：Version 能返回还不够，必须有一个带参方法也能通
            _ = rs.DocumentName()
            if verbose:
                print("[conn] OK  attempt=%d  version=%s  doc=%r" % (attempt + 1, ver, _))
            return dispatch, rs, ver
        except Exception as e:
            last = repr(e)
            if verbose:
                print("[conn] %d/%d ScriptObject 未就绪: %s" % (attempt + 1, retry, last))
            time.sleep(wait)
    raise RuntimeError("RhinoScript 接口始终未就绪（%d 次）: %s" % (retry, last))


# ---------------------------------------------------------------- 窗口守护
def ensure_window(pid=None, sleep=4, size=(1560, 980), pos=(120, 80)):
    """把 Rhino 主窗口拉回屏幕内。

    ⚠️ 不做这一步，自动化拉起的实例主窗口常在 (-21333,-21333)，
    视口不走 GPU 着色管线 -> CreatePreviewImage 出图**全退化成线框**。
    这是本项目卡了十几轮的头号假故障。
    """
    try:
        import win32gui, win32con, win32process, psutil
    except Exception as e:
        print("[window] 缺依赖: %s" % e)
        return []
    pids = [pid] if pid else [
        p.info["pid"] for p in psutil.process_iter(["pid", "name"])
        if (p.info.get("name") or "").lower().startswith("rhino")
    ]
    found = []

    def cb(hwnd, res):
        try:
            _, wpid = win32process.GetWindowThreadProcessId(hwnd)
            if wpid in pids and "Rhinoceros" in win32gui.GetWindowText(hwnd):
                res.append(hwnd)
        except Exception:
            pass

    win32gui.EnumWindows(cb, found)
    for hwnd in found:
        for fn in (
            lambda: win32gui.ShowWindow(hwnd, win32con.SW_RESTORE),
            lambda: win32gui.SetWindowPos(hwnd, 0, pos[0], pos[1], size[0], size[1],
                                          win32con.SWP_SHOWWINDOW | win32con.SWP_NOZORDER),
            lambda: win32gui.BringWindowToTop(hwnd),
        ):
            try:
                fn()
            except Exception:
                pass
    if found:
        try:
            import win32com.client as wc
            wc.Dispatch("WScript.Shell").AppActivate(int(pids[0]))
        except Exception:
            pass
        time.sleep(sleep)
    return found


# ---------------------------------------------------------------- 只读体检
def probe(rs):
    """只读汇总：文档 / 修改标记 / 对象数 / 图层 / 视口 / 包围盒。"""
    info = {}
    for k, fn in (
        ("doc", lambda: rs.DocumentName()),
        ("modified", lambda: rs.DocumentModified()),
        ("objects", lambda: len(rs.AllObjects() or [])),
        ("layers", lambda: list(rs.LayerNames() or [])),
        ("views", lambda: list(rs.ViewNames() or [])),
    ):
        try:
            info[k] = fn()
        except Exception as e:
            info[k] = "ERR %s" % e
    try:
        info["modes"] = {v: rs.ViewDisplayMode(v) for v in (info.get("views") or [])}
    except Exception as e:
        info["modes"] = "ERR %s" % e
    try:
        objs = list(rs.AllObjects() or [])
        bb = rs.BoundingBox(objs) or []
        if not bb:                          # 批量失败就逐对象兜底
            pts = []
            for oid in objs:
                pts.extend(rs.BoundingBox([oid]) or [])
            bb = pts
        xs = [p[0] for p in bb]; ys = [p[1] for p in bb]; zs = [p[2] for p in bb]
        info["bbox"] = (round(min(xs), 2), round(max(xs), 2),
                        round(min(ys), 2), round(max(ys), 2),
                        round(min(zs), 2), round(max(zs), 2))
        info["span"] = (round(max(xs) - min(xs), 2), round(max(ys) - min(ys), 2),
                        round(max(zs) - min(zs), 2))
    except Exception as e:
        info["bbox"] = "ERR %s" % e
    return info


def describe(rs):
    i = probe(rs)
    lines = [
        "doc       = %r" % i.get("doc"),
        "modified  = %s   <- True 时不要自动保存，会覆盖用户未存的活" % i.get("modified"),
        "objects   = %s" % i.get("objects"),
        "layers    = %d  %s" % (len(i.get("layers") or []), i.get("layers")),
        "views     = %s" % i.get("views"),
        "modes     = %s   (0 线框 / 1 着色 / 2 渲染)" % i.get("modes"),
        "bbox      = %s" % (i.get("bbox"),),
        "span(m)   = %s" % (i.get("span"),),
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------- 保存
def save_as(rs, folder, stem, ext=".3dm"):
    """`-_SaveAs` 只能吃**裸文件名** —— 传带引号的绝对路径在 COM 下会失败。

    正确姿势：先 WorkingFolder，再裸文件名。
    ⚠️ 文档有未保存改动时 `-_Open` / `-_Close` 会弹「保存改变为 …?」模态框，
       把 COM 卡死好几分钟。**这类命令一律先过 assert_clean()。**
       （`-_SaveAs` 本身不弹框，但它会把"未命名"文档变成一个真文件，
        所以仍要确认用户想存到哪。）
    """
    rs.WorkingFolder(folder)
    t0 = time.time()
    rs.Command("-_SaveAs %s" % stem)
    time.sleep(1.5)
    path = os.path.join(folder, stem + ext)
    return path, os.path.exists(path), time.time() - t0


def assert_clean(rs, action="该操作"):
    """任何会碰"打开/关闭/新建"的命令前必须先过这一关。

    文档 dirty 时这些命令会弹「保存改变为 未命名?」，
    Rhino 在等用户点击，而 Python 卡在 rs.Command 的 COM 等待里 ——
    实测卡死 7 分钟，只能 rescue() 发 ESC 才解得开。
    """
    try:
        dirty = bool(rs.DocumentModified())
    except Exception:
        dirty = False
    if dirty:
        raise RuntimeError(
            "%s 会弹保存框并卡死 COM：文档有未保存改动（%r）。"
            "先问用户存不存，或改用 save_as() 另存后再说。" % (action, rs.DocumentName())
        )
    return True


def assert_doc(rs, expect):
    """核对"我连的是不是用户那个文档"。

    ⚠️ 本机常见**同时开两个 Rhino 实例**（一个是正活、一个是空的"未命名"）。
    `Dispatch` 只会给其中一个，连错了照样能愉快地改，改完用户说"我的模型没变"。
    动手前把文件名关键词传进来：
        assert_doc(rs, "清华园驿站")
    """
    name = rs.DocumentName() or ""
    if expect and str(expect).lower() not in name.lower():
        raise RuntimeError(
            "附着的文档是 %r，不含关键词 %r —— 多实例时连错了。\n"
            "  处置: 让用户关掉多余实例，或确认要改的是哪一个；**不要盲改**。" % (name, expect))
    return name


# ---------------------------------------------------------------- 黑线（默认交付）
def black_lines(rs, keep_layers=(), color=None):
    """★ 默认交付动作：线框要能看清的黑线。

    只改【对象显示色】→ 线框 + 着色都变黑；
    **图层色原样保留材料自然色** → 渲染靠材质/图层色仍是材料色，信息不丢。

    反面教材见 P39：把材料白写进图层色 = 灰底白线，整张图像素几乎不变。
    返回改了几个对象。
    """
    color = BLACK if color is None else color
    keep = set(keep_layers or [])
    n = 0
    for o in list(rs.AllObjects() or []):
        try:
            if keep and rs.ObjectLayer(o) in keep:
                continue
            rs.ObjectColorSource(o, 1)      # 1 = By Object
            rs.ObjectColor(o, color)        # 纯黑 = 打包整数 0
            n += 1
        except Exception:
            pass
    return n


def restore_bylayer(rs):
    """一键退回：对象色改回 ByLayer，立刻恢复材料色线稿。"""
    n = 0
    for o in list(rs.AllObjects() or []):
        try:
            rs.ObjectColorSource(o, 0)
            n += 1
        except Exception:
            pass
    return n


# ---------------------------------------------------------------- 黑白素模（2026-11-03 起的默认交付）
def bw_style(rs, exclude_layers=()):
    """★ 默认交付样式（用户 2026-11-03 定稿，替代旧"自然色"默认）：

    线框 = 黑线 · 着色 = 黑面白边 · 渲染 = 纯白素模（云在亭 v25 的观感）。

    做法：
      ① 对象显示色压黑 → 线框画黑线、着色画黑面（着色模式的白网格边自动保留）；
      ② 图层色改白 → 渲染模式 ByLayer 漫反射取图层色 → 纯白。
         （对象色已是 ByObject=黑，不受图层色影响，两层互不干扰。）

    exclude_layers: 不要动的图层名列表（如地面、场地，想保留原色就传进来）。
    返回 {图层名: 原颜色打包整数}，交给 restore_layers() 可一键还原图层色。
    """
    exclude = set(exclude_layers or [])
    saved = {}
    for lname in (rs.LayerNames() or []):
        try:
            if lname in exclude:
                continue
            li = rs.LayerID(lname)
            saved[lname] = rs.LayerColor(lname)
            rs.LayerColor(lname, WHITE)
        except Exception:
            pass
    black_lines(rs, keep_layers=exclude)
    return saved


def restore_layers(rs, saved):
    """还原 bw_style() 改掉的图层色（传它返回的 dict）。"""
    for lname, c in (saved or {}).items():
        try:
            rs.LayerColor(lname, c)
        except Exception:
            pass


def bw_style_mat(rs, exclude_layers=(), ground_gray=(245, 245, 242)):
    """★ 黑白素模·图层黑变体（2026-11-03 用户追加定稿）：

    用户看图层面板时要求"图层色要是黑的"——bw_style 的"图层白"在面板里一片白，
    观感上像没做。本函数把图层色也压黑，渲染通道改由【对象材质】接管：

      ① 对象显示色压黑（同 bw_style）→ 线框黑线、着色黑面；
      ② 图层色全部压黑（含 exclude 的图层）→ 图层面板即所见，全黑；
      ③ 对象挂【两把共享材质】接管渲染：建筑白 / 场地浅灰（瘦身：全模型只建两把，
         其余对象 ObjectMaterialIndex 指过去，别逐对象 AddMaterialToObject）。
         exclude 图层挂 ground_gray 材质 → 渲染图里地坪仍有层次，不与建筑混成一片。

    渲染验收数值与 bw_style 完全一致（avg≈206 / bright≈53%）；
    着色/线框不受材质影响（它们只读对象显示色）。
    """
    exclude = set(exclude_layers or [])
    objs = list(rs.AllObjects() or [])
    ground = []
    build = []
    for o in objs:
        lay = rs.ObjectLayer(o)
        (ground if lay in exclude else build).append(o)

    # 图层全部压黑（不排除任何图层——面板观感优先）
    for lname in (rs.LayerNames() or []):
        try:
            rs.LayerColor(lname, BLACK)
        except Exception:
            pass

    # 两把共享材质
    mi_w = rs.AddMaterialToObject(build[0]) if build else None
    if mi_w is not None and mi_w >= 0:
        rs.MaterialColor(mi_w, packed(255, 255, 255))
        rs.MaterialShine(mi_w, 0.0)
        rs.MaterialTransparency(mi_w, 0.0)
    mi_g = None
    if ground:
        mi_g = rs.AddMaterialToObject(ground[0])
        rs.MaterialColor(mi_g, packed(*ground_gray))
        rs.MaterialShine(mi_g, 0.0)
        rs.MaterialTransparency(mi_g, 0.0)
    for o in build:
        rs.ObjectMaterialSource(o, 1)
        if mi_w is not None and mi_w >= 0:
            rs.ObjectMaterialIndex(o, mi_w)
    for o in ground:
        rs.ObjectMaterialSource(o, 1)
        if mi_g is not None and mi_g >= 0:
            rs.ObjectMaterialIndex(o, mi_g)
    return {"white": mi_w, "ground": mi_g}


# ---------------------------------------------------------------- 相机 / 取景
def model_bbox(rs, objs=None):
    """返回 (minx,miny,minz,maxx,maxy,maxz)；空模型返回 None。

    批量 BoundingBox 会失败（返回空），必须逐对象兜底 —— 实测丢过整帧画面。
    """
    objs = list(objs if objs is not None else (rs.AllObjects() or []))
    if not objs:
        return None
    bb = rs.BoundingBox(objs) or []
    if not bb:
        pts = []
        for oid in objs:
            pts.extend(rs.BoundingBox([oid]) or [])
        bb = pts
    if not bb:
        return None
    xs = [p[0] for p in bb]; ys = [p[1] for p in bb]; zs = [p[2] for p in bb]
    return (min(xs), min(ys), min(zs), max(xs), max(ys), max(zs))


def zoom_bbox(rs, view, corners):
    """corners: 8 个角点 -> to_nested_variant_r8 后喂 ZoomBoundingBox。

    ⚠️ 不能假设 `rhinorouter` 已在 sys.path —— 那是 `connect()` 里才插的。
    单独调用 frame_all()（比如只读探测脚本）时这里要自己补路径，
    补不上就退回直接传列表（部分版本能接受），别让取景整条挂掉。
    """
    rs.CurrentView(view)
    pts = corners
    try:
        if RHINOROUTER_DIR not in sys.path:
            sys.path.insert(0, RHINOROUTER_DIR)
        from rhinorouter import to_nested_variant_r8
        pts = to_nested_variant_r8(corners)
    except Exception as e:
        print("[zoom] to_nested_variant_r8 不可用，退回原始列表: %s" % e)
    rs.ZoomBoundingBox(pts)


def frame_all(rs, view, bbox=None, pad=1.12):
    """把视口框到**模型真实包围盒**上。

    ⚠️ 不调这个，视口还停在 (0,0,0) —— 模型中心在 x=7.7 时，
    四张图会**全是空白**（P38 真实事故）。cam/tgt 硬编码只能在模型位置确定时用。
    """
    bb = bbox or model_bbox(rs)
    if not bb:
        return False
    x0, y0, z0, x1, y1, z1 = bb
    corners = [[x, y, z] for x in (x0, x1) for y in (y0, y1) for z in (z0, z1)]
    rs.CurrentView(view)
    zoom_bbox(rs, view, corners)
    if pad and abs(pad - 1.0) > 1e-6:
        try:
            rs.Command("_-Zoom _OutFactor %.3f _Enter" % pad)
        except Exception:
            pass
    return True


VIEW_SETUP = {
    "Perspective": "_-SetView _World _Perspective",
    "Top": "_-SetView _World _Top",
    "Front": "_-SetView _World _Front",
    "Right": "_-SetView _World _Right",
    "Back": "_-SetView _World _Back",
    "Left": "_-SetView _World _Left",
    "Bottom": "_-SetView _World _Bottom",
}


# ---------------------------------------------------------------- 窗口可见性
def rhino_windows(pid=None):
    """列 Rhino 顶层窗口：[(hwnd, visible, class, title, rect), ...]"""
    try:
        import win32gui, win32process, psutil
    except Exception:
        return []
    pids = [pid] if pid else [
        p.info["pid"] for p in psutil.process_iter(["pid", "name"])
        if (p.info.get("name") or "").lower().startswith("rhino")
    ]
    out = []

    def cb(hwnd, _):
        try:
            _, wpid = win32process.GetWindowThreadProcessId(hwnd)
            if wpid in pids:
                out.append((hwnd, bool(win32gui.IsWindowVisible(hwnd)),
                            win32gui.GetClassName(hwnd),
                            win32gui.GetWindowText(hwnd),
                            win32gui.GetWindowRect(hwnd)))
        except Exception:
            pass
        return True

    win32gui.EnumWindows(cb, None)
    return out


def window_ready(min_width=500):
    """主窗口是否真的在屏幕上（可被截图 / 走着色管线）。

    返回 (ok, detail)。ok=False 时 CreatePreviewImage 出的是**空白图**，
    不是模型问题 —— 别去改几何。

    detail 只给**人话结论**（不 dump 几十个内部子窗口）：
    屏幕外 / 隐藏 / 过小 / 压根没有主窗口。
    """
    wins = rhino_windows()
    labeled = [w for w in wins if "Rhinoceros" in (w[3] or "")]
    good = [w for w in labeled
            if w[1] and w[4][0] > -10000 and (w[4][2] - w[4][0]) >= min_width]
    if good:
        hwnd, _v, _c, title, rect = good[0]
        return True, "hwnd=%s title=%r rect=%s" % (hwnd, title, rect)
    if labeled:
        hwnd, vis, _cls, title, rect = labeled[0]
        if rect[0] <= -10000:
            return False, "主窗口在屏幕外 rect=%s title=%r —— 调 ensure_window()" % (rect, title)
        if not vis:
            return False, "主窗口被隐藏 title=%r —— 可能还在启动/等授权" % (title,)
        return False, "主窗口太小 rect=%s title=%r" % (rect, title)
    if wins:
        return False, "没有标题含 Rhinoceros 的主窗口（只有 %d 个子窗口）—— 多半还在启动/授权/插件报错框" % len(wins)
    return False, "进程里没有 Rhino 窗口"


def _ink_count(path, thresh=24):
    """【仅作诊断参考，不要拿它当"空图"判据】

    背景取四角众数，比"取单个角"稳（旧坑：角落压在深色地面 → 把地面算成模型）。
    但 **Rhino 视口本身是渐变底**，一张完全空的截图也能被算出上万个"墨点"
    （2026-11-03 实测：空图 18907、有内容 6704）。所以判空不能靠它。
    """
    try:
        from PIL import Image
        im = Image.open(path).convert("RGB")
        im.thumbnail((300, 300))
        w, h = im.size
        cs = [im.getpixel(p) for p in ((1, 1), (w - 2, 1), (1, h - 2), (w - 2, h - 2))]
        bg = max(set(cs), key=cs.count)
        n = 0
        for q in im.getdata():
            if abs(q[0] - bg[0]) + abs(q[1] - bg[1]) + abs(q[2] - bg[2]) > thresh:
                n += 1
        return n, bg
    except Exception:
        return None, None


# ---------------------------------------------------------------- 出图
def shot(rs, path, view="Perspective", size=(1400, 950), mode=None,
         cam=None, tgt=None, frame=True, pad=1.12, strict=True):
    """出图。唯一可用接口是 CreatePreviewImage（_ViewCaptureToFile 产出空白）。

    参数顺序【文件名在前】。size 是 [w, h]。

    出图变空的两个原因，**都跟模型无关**，这里分别堵死：
      ① 主窗口不可见（被启动画面/授权框/插件报错框挡住）→ 离屏渲染出空白
         → strict 时 `window_ready()` 不通过就 **抛错**（这是可以确定性判定的）
      ② 相机没落在模型上（还停在原点）→ 由 `frame=True` 自动框包围盒消除
    不猜"像素数是否为空"——视口渐变底会让这种判法误报，见 _ink_count 的注释。
    """
    if mode is not None:
        rs.ViewDisplayMode(view, mode)
        time.sleep(0.6)
    rs.CurrentView(view)
    if cam and tgt:
        rs.ViewCameraTarget(view, list(cam), list(tgt))
    elif frame:
        try:
            frame_all(rs, view, pad=pad)
        except Exception as e:
            print("[shot] frame 失败（继续，但可能取景不对）: %s" % e)

    if strict:
        try:
            n_obj = len(rs.AllObjects() or [])
        except Exception:
            n_obj = -1
        if n_obj == 0:
            raise RuntimeError("文档里没有对象（0 个）——出图必然是空的，先确认文档开对了没。")
        ok, detail = window_ready()
        if not ok:
            ensure_window()
            ok, detail = window_ready()
            if not ok:
                raise RuntimeError(
                    "出图前主窗口不可见 —— CreatePreviewImage 只会产出空白图。\n"
                    "  现状: %s\n"
                    "  处置: 关掉启动画面/插件报错框（插件框点「是」；"
                    "授权框别动，交回用户），或让用户把 Rhino 主界面显示出来。\n"
                    "  **不要去改模型。**" % detail)

    if size:
        rs.CreatePreviewImage(path, view, list(size))
    time.sleep(0.4)
    exists = os.path.exists(path)
    if exists:
        n, bg = _ink_count(path)
        print("[shot] %-34s ink=%s bg=%s (仅供诊断)" % (os.path.basename(path), n, bg))
    return path, exists


def shot_views(rs, outdir, prefix, views=("Perspective", "Top", "Front", "Right"),
               mode=MODE_WIRE, size=(1500, 1100), pad=1.12, strict=True):
    """四/多视图一把出完：自动复位视口 → 框包围盒 → 出图 → 空图自检。

    这是"交付预览图"的唯一推荐入口；不要再手写 for 循环（会漏掉 SetView 复位）。
    """
    os.makedirs(outdir, exist_ok=True)
    ensure_window()
    bb = model_bbox(rs)
    if bb:
        print("[shot_views] bbox = (%.2f,%.2f,%.2f)-(%.2f,%.2f,%.2f)  span=%.2f x %.2f x %.2f"
              % (bb + (bb[3] - bb[0], bb[4] - bb[1], bb[5] - bb[2])))
    out = []
    for v in views:
        cmd = VIEW_SETUP.get(v)
        if cmd:
            rs.CurrentView(v)
            try:
                rs.Command(cmd)
            except Exception as e:
                print("[shot_views] SetView %s 失败: %s" % (v, e))
            time.sleep(0.4)
        p = os.path.join(outdir, "%s_%s.png" % (prefix, v.lower()))
        shot(rs, p, view=v, size=size, mode=mode, frame=True, pad=pad, strict=strict)
        n, bg = _ink_count(p)
        print("[shot_views] %-12s -> %s  ink=%s bg=%s (诊断值)" % (v, os.path.basename(p), n, bg))
        out.append(p)
    return out


# ---------------------------------------------------------------- 材质（渲染通道）
def render_bg(rs, rgb=(186, 188, 190)):
    """把【渲染背景色】改成中性灰，返回原色。

    白模必须配灰底 —— 纯白材质 + 纯白背景，在 Render 模式里就是"看不见"，
    而且用户 100% 会描述成"模型是透明的"。这是文档级设置（Rhino Render 背景），
    **不是**显示模式属性，不碰 P23。
    """
    prev = rs.RenderColor(1)
    rs.RenderColor(1, packed(*rgb))
    return prev


def audit_materials(rs, objs=None):
    """列出透明度 > 0 的对象，按材质索引归组。返回 {mi: [layer, ...]}。

    渲染模式"整栋楼透明"的唯一元凶就是材质透明度（P44）——
    `MaterialTransparency` 写到被多个对象共享的材质槽时，会一次性放倒整批对象。
    """
    objs = list(objs if objs is not None else (rs.AllObjects() or []))
    bad = {}
    for o in objs:
        try:
            mi = rs.ObjectMaterialIndex(o)
            t = rs.MaterialTransparency(mi)
        except Exception:
            continue
        if t is not None and t > 1e-6:
            bad.setdefault(mi, []).append(rs.ObjectLayer(o))
    return bad


def set_materials(rs, groups, shine=0.0, verbose=True):
    """groups = [(objs, (r,g,b)[, transparency]), ...]，逐对象写材质并【回读复核】。

    用法（白模三把材质）：
        set_materials(rs, [(build, (252,252,250)),
                           (glass, (196,202,200)),
                           (site,  (198,198,194))])
        render_bg(rs)                      # 灰底，否则白对白看不见

    ★ 为什么必须回读：MaterialTransparency 一旦落到共享材质槽，整批对象一起透明
      （P44，2026-11-04 真实事故：1266 个对象全变 82% 透明）。
      返回 issues 数，非 0 说明有对象没吃到设定值。
    """
    issues = 0
    for g in groups:
        objs, rgb = list(g[0]), g[1]
        tr = g[2] if len(g) > 2 else 0.0
        for o in objs:
            try:
                rs.ObjectMaterialSource(o, 1)          # 1 = By Object
                mi = rs.ObjectMaterialIndex(o)
                if not (isinstance(mi, int) and mi >= 0):
                    mi = rs.AddMaterialToObject(o)
                rs.MaterialColor(mi, packed(*rgb))
                rs.MaterialShine(mi, shine)
                rs.MaterialTransparency(mi, tr)
                got = rs.MaterialTransparency(rs.ObjectMaterialIndex(o))
                if got is None or abs(got - tr) > 1e-6:
                    issues += 1
            except Exception:
                issues += 1
    if verbose:
        print("[material] 复核未通过=%d" % issues)
    return issues


def reset_materials(rs, site_layers=("场地",), build_rgb=(252, 252, 250),
                    site_rgb=(198, 198, 194), bg=(186, 188, 190), verbose=True):
    """一键修"渲染模式全透明/看不见"：全模型一把白材质 + 场地走图层色 + 背景改灰。

    ★ 为什么不按组给物体材质上不同颜色：Rhino 8 里 `ObjectMaterialIndex` 的槽位
      **会被多个对象共用**（P44 的根因），分组染色最后往往是"后处理的组赢"，
      回读会发现屋面吃了玻璃的颜色。要分组配色只能用**图层色**（ByLayer）。
      素模其实不需要那点色差，一把白 + 灰底 + 阴影就够读。

    site_layers 传图层名关键词（场地地坪）。返回 audit_materials() 的残留（应为空）。
    """
    objs = list(rs.AllObjects() or [])
    site_keys = tuple(site_layers or ())

    def is_site(o):
        lay = rs.ObjectLayer(o)
        return any(k in lay for k in site_keys)

    build = [o for o in objs if not is_site(o)]
    site = [o for o in objs if is_site(o)]

    issues = set_materials(rs, [(build, build_rgb)], verbose=False)

    # 场地：图层色染灰 + 材质走 ByLayer —— 图层色是唯一可靠的分组手段
    for lay in set(rs.ObjectLayer(o) for o in site):
        try:
            rs.LayerColor(lay, packed(*site_rgb))
        except Exception:
            pass
    for o in site:
        try:
            rs.ObjectMaterialSource(o, 0)          # 0 = ByLayer
        except Exception:
            pass

    render_bg(rs, bg)
    left = audit_materials(rs)
    if verbose:
        print("[reset] objects=%d  build=%d site=%d  issues=%d  仍透明=%d"
              % (len(objs), len(build), len(site), issues, len(left)))
    return left


# ---------------------------------------------------------------- 救援
def rescue(seconds=2):
    """COM 卡在模态框（保存框 / 授权框 / 命令行等输入）时的解卡。

    SendKeys 到 Rhino 窗口发 ESC。仅用于**自己的脚本把 Rhino 卡住**的场景。
    不要在用户正在手动操作 Rhino 时调用。
    """
    try:
        import win32com.client as wc
        sh = wc.Dispatch("WScript.Shell")
        for _ in range(3):
            sh.AppActivate("Rhinoceros")
            time.sleep(0.4)
            sh.SendKeys("{ESC}")
            time.sleep(0.6)
        return True
    except Exception as e:
        print("[rescue] 失败: %s" % e)
        return False


if __name__ == "__main__":
    d, rs, v = connect()
    ensure_window()
    print(describe(rs))
