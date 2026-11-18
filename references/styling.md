# 显示效果：黑白素模（默认）/ 剪影 / 白模黑线 / 自然色

> **★ 2026-11-03 用户定稿：默认交付 = 黑白素模（§1.5）**——
> 线框黑线 · 着色黑面白边 · 渲染纯白（云在亭 v25 的观感）。`bw_style(rs)` 一键到位。
> 只有用户明说才做别的样式。以下各节保留，供换挡时查阅。

---

## 0. 先弄清"改哪一层"（唯一必须记住的表）

| 通道 | 怎么设 | 谁读它 |
|---|---|---|
| 显示颜色（对象色 / 图层色） | `ObjectColor(o, packed)` / `LayerColor(L, packed)` | **线框 + 着色**（两者永远一起变） |
| 对象材质 diffuse | `ObjectMaterialSource(o,1)` + `MaterialColor(mi, packed)` | **渲染**（只渲染） |

推论：
- 「只改线框不改着色」= **做不到**（同一个通道）
- 「只改渲染不改线框/着色」= 改材质，别碰显示色
- 「线框+着色黑、渲染白」= 显示色设黑 + 材质设白（本项目 v25 的最终定稿）
  - 简化做法（`bw_style()` 用的）：对象色 ByObject=黑 + **图层色改白**。
    对象色源已是 ByObject，图层色动不了线框/着色；渲染 ByLayer 漫反射取图层色 → 白。

**索引**：0 线框 / 1 着色 / 2 渲染。越界**静默无效**。
**视口显示模式是文档属性**，随 `.3dm` 存盘 → 打开即所见。这是文件级的正当做法。

---

## 1.5 默认：黑白素模（★ 2026-11-03 起建完就做，别等用户说）

```python
from rhino_conn import bw_style, restore_layers
saved = bw_style(rs)                    # 对象色→黑，图层色→白；返回原图层色
saved = bw_style(rs, exclude_layers=("场地-地平面",))  # 地面等想留原色就排除
restore_layers(rs, saved)               # 一键还原图层色（对象色仍需 restore_bylayer）
```

| 模式 | 看到什么 | 为什么 |
|---|---|---|
| 线框 | 黑线 | 对象显示色 = 黑 |
| 着色 | 黑面 + 白网格边 | 面跟对象色；边线是着色模式的浅色结构线 |
| 渲染 | 纯白素模 | ByLayer 漫反射取图层色（白） |

验收口诀：**线框黑、着色黑面、渲染白**——`ink_stats.py` 里线框 dark 占比高、
渲染 bright 占比高即对（v25 实测：线框 avg≈27 / dark 85%，渲染 avg≈207 / bright 41%）。

---

## 1.6 黑白素模·图层黑变体（★ 2026-11-03 用户追加："图层颜色为什么是全白？要黑的"）

bw_style 的"图层白"只管渲染通道，但代价是**图层面板里所有色块一片白**，
用户看面板会以为样式没做。要图层面板也是黑的，用 `bw_style_mat(rs)`：

```python
from rhino_conn import bw_style_mat
bw_style_mat(rs, exclude_layers=("00-场地",))   # exclude 图层挂浅灰材质，渲染里地坪仍有层次
```

机制（对照 §0 的两层表）：
| 通道 | bw_style（图层白） | bw_style_mat（图层黑） |
|---|---|---|
| 线框 / 着色 | 对象色 ByObject=黑 | 同左（材质不影响这两层） |
| 渲染 | ByLayer 漫反射←图层白 | **对象材质 diffuse←共享白材质** |
| 图层面板 | 全白（用户不满） | 全黑 ✓ |

- 瘦身关键：**全模型只建两把材质**（建筑白 / 场地浅灰），其余对象
  `ObjectMaterialIndex(o, mi)` 指过去。逐对象 `AddMaterialToObject` 会让文件涨 3.5 MB。
- 渲染验收数值与 bw_style 完全一致（实测 avg≈206 / bright≈53%，图层黑不会漏进渲染）；
  若渲染图突然变黑 = 材质没挂上，检查 `ObjectMaterialSource(o,1)` 是否漏写。
- 实战脚本见 `_build/v5_all.py`（驿站项目 2026-11-03）。

---

## 1. 默认：线框黑线 + 材料色留在图层（★ 建完就做，别等用户说）

**用户要的"自然建模结果"= 线框能看清的黑线稿，不是把材料色当线色。**

```python
from rhino_conn import black_lines, MODE_WIRE

# 一行搞定：对象显示色压黑（线框+着色=黑线），图层色保留材料自然色
n = black_lines(rs)          # 等价于逐个 ObjectColorSource(o,1)+ObjectColor(o,BLACK)
print("black_lines ->", n)

# 视口停在线框（建模视角）；出效果图时再切着色/渲染
for v in rs.ViewNames():
    rs.ViewDisplayMode(v, MODE_WIRE)
```

三个模式因此变成：

| 模式 | 读什么 | 看到什么 |
|---|---|---|
| 线框 | 对象显示色（黑） | **黑线稿** ✓ 用户要的 |
| 着色 | 对象显示色（黑） | 黑面（可接受，他建模不看这个） |
| 渲染 | 对象材质（图层材料色/材质） | 材料自然色 ✓ 出效果图用 |

**回退**：`from rhino_conn import restore_bylayer; restore_bylayer(rs)` —— 全部改回 ByLayer，立刻恢复材料色线稿。

### ⚠️ 反面教材（2026-11-03，用户原话"我要的是黑线为什么你再调用skill出来的是白线"）

早先把"材料自然色"直接写进了**图层色**：白墙 `(241,239,235)`、白屋面 `(250,248,243)`、
浅场地 `(245,245,242)`。**线框模式画的正是图层色** → 灰底上的白线，整张图像素几乎无变化，
出图量化直接 `NO INK`，用户以为模型根本没建出来。

**判断口诀：凡是"这颜色是给眼睛看线用的"，就不能用材料色；材料色只能进材质。**


---

## 2. 线框 + 着色 = 黑，渲染 = 白（本项目最终定稿）

用户原话："着色和线框模式下显示黑色，渲染模式纯白素模"。

```python
from rhino_conn import BLACK, WHITE, MODE_WIRE, MODE_SHADED, MODE_RENDER

GROUND = "场地-地平面"
allobjs = list(rs.AllObjects() or [])
ground  = set(rs.ObjectsByLayer(GROUND) or [])
build   = [o for o in allobjs if o not in ground]      # 地面保持浅灰，别涂黑

# ① 线框 + 着色 -> 黑：改显示颜色
for L in rs.LayerNames():
    if L != GROUND:
        rs.LayerColor(L, BLACK)
for o in build:
    rs.ObjectColor(o, BLACK)

# ② 渲染 -> 白：改对象材质
#    ⚠️ 别手写 AddMaterialToObject + MaterialTransparency（P44：共享槽会被毒化成全楼透明）
from rhino_conn import set_materials, audit_materials, render_bg
set_materials(rs, [(build, (252, 252, 250))], )   # 自动回读复核
assert not audit_materials(rs), "还有对象带透明度 —— 渲染模式会整批变透明（P44）"
render_bg(rs)                                     # 灰底，否则白对白看不见（P45）

# ③ 视口定稿（打开即所见）
for v in rs.ViewNames():
    rs.ViewDisplayMode(v, MODE_SHADED)     # 打开就停在着色，看到的是黑面
```

**代价**：逐对象建材质会让文件涨约 3.5 MB（608 个对象各一把）。
想瘦身就改成"一把共享材质，所有对象指过去"：
```python
probe = build[0]
mi = rs.AddMaterialToObject(probe)
rs.MaterialColor(mi, WHITE)
for o in build:
    rs.ObjectMaterialSource(o, 1)
    rs.ObjectMaterialIndex(o, mi)          # 注意：这是"指向"，不是"新建"
```
⚠️ 共享材质能让文件瘦身，但**共享槽位上绝不能设透明度** —— 一设就是全楼透明（P44）。
⚠️ 另外：`rs.ObjectMaterialIndex(o, mi)` 的"指向"在 Rhino 8 上**未必真的写进去**
（实测逐对象仍保留自己的槽位）。所以这条只能当"尽量瘦身"用，
**判据永远是回读**：`rs.ObjectMaterialIndex(o)` 逐个读回来核对。

**观感陷阱（会让人以为没做对）**：
- 着色模式会在黑面上画**浅色结构线/边缘线** → 不是纯色块。要"一条线都没有"得关
  `ShowEdges`，**那是全局设置（P23），别做**。
- 渲染模式下纯白模型**必须配灰底**（`render_bg()`），否则白对白、看着像"全透明"（P45）。
- 线框模式会把稠密几何（几百条格网）**糊成实心黑**，看着像剪影，不是 bug。

---

## 3. 只做线框剪影（体块图）

```python
for L in rs.LayerNames():
    if L != GROUND:
        rs.LayerColor(L, BLACK)
for v in rs.ViewNames():
    rs.ViewDisplayMode(v, MODE_WIRE)
```
⚠️ 线框模式只画线。如果模型全是 NURBS 曲面、**没有独立曲线对象**，
线框就靠"曲面结构线/边缘线"画出来；一旦有人关掉 `ShowEdges`，线框会**全空**（P23 事故）。

---

## 4. 量化验收（三张图各测一次）

```python
def ink_stats(path):
    from PIL import Image
    im = Image.open(path).convert("RGB"); im.thumbnail((360, 360))
    bg = im.getpixel((1, 1))
    px = [q for q in im.getdata()
          if abs(q[0]-bg[0]) + abs(q[1]-bg[1]) + abs(q[2]-bg[2]) > 30]
    if not px: return "NO INK  bg=%s" % (bg,)
    n = len(px)
    avg = tuple(sum(q[i] for q in px)/n for i in range(3))
    dark   = sum(1 for q in px if sum(q)/3 < 60) / n
    bright = sum(1 for q in px if sum(q)/3 > 215) / n
    return "ink=%5d avg=(%3.0f,%3.0f,%3.0f) dark=%4.1f%% bright=%4.1f%% bg=%s" % (
        n, avg[0], avg[1], avg[2], 100*dark, 100*bright, bg)
```

判定阈值（本项目实测）：
- 线框纯黑：`avg ≈ (27,28,28)`，`dark > 80%`
- 渲染纯白：`avg ≈ (207,207,207)`，`bright > 40%`
- 线框全空：`NO INK` 或 `ink` 极小 + bg 占比 100% → 查 P23

⚠️ **背景色取角落像素前先确认那个角落没有地面**。本项目曾因角落落在深灰地坪上，
把地面当模型像素，得出"着色改不动"的错误结论，白走一轮。


---

## 5. 白模黑线（黑线 + 白面 + 纯白渲染）

这是建筑出图最常见的一档，和"黑模"（全黑剪影）**不是一回事**，别混。

| 通道 | 要的东西 | 怎么设 |
|---|---|---|
| 线框模式 | **黑线** | 对象显示色 = 黑 **或** 白，取决于边线颜色设置（见下） |
| 着色模式 | **白面 + 黑边** | 面跟对象色（白）；**边线必须是"单色黑"** |
| 渲染模式 | 纯白素模 | 图层色 = 白（ByLayer 默认漫反射取图层色），或对象材质白 |

### ★ 核心坑：白面必然白线（2026-11-03 实测）

Rhino 着色模式的**边线颜色默认"使用对象颜色"**。
把对象显示色改成白 → 面白了，**边线也变白** → 白底白面白线，整张图糊成一片，看着像"模型没建出来"。
（出图实测：ink 12259 但 avg 全在 200 以上，dark≈0，肉眼几乎看不到轮廓。）

**这不是模型问题，是显示模式设置问题。** 改对象颜色永远解决不了。

正解只有一条：**把着色模式的边线颜色改成"单色黑"**
> 选项 → 视图 → 显示模式 → 着色 → 边线设置 → 颜色：由「使用对象颜色」改为「黑色」

⚠️ 这是**用户级全局设置**（改一次，所有文件的着色模式都变），
所以：
1. **不要脚本代改**。`-_RunPythonScript` 调 RhinoCommon 的 `DisplayModeDescription`
   在本机会弹「Rhinoceros 8 Exception Occured」并把 Rhino 卡住（实测）。
2. **不要改 `ViewDisplayModeProperty`**（见 P22）。
3. 交给用户点这几下，或先征得同意再动；动完要重启 Rhino 才生效。

### 临时替代：极地模式（Arctic）

模式列表里叫「极地模式」（索引 5）。白面 + 极浅边线 + 白底，
不改任何设置就能出"素模感"，但**线是浅灰不是黑**，做正式图不够。

### 判定口诀

- 面白线白 → 边线颜色还在"使用对象颜色"，去改显示模式。
- 面白线黑 → 成了。
- 面黑线白 → 那是黑模（v25 那种），对象色被压黑了。
