# -*- coding: utf-8 -*-
"""ink_stats.py —— 出图后的量化验收。别靠"看着还行"。

用法：
    python ink_stats.py a.png [b.png ...]
    python ink_stats.py _preview/v25_black_wire.png

判定阈值（本项目实测）：
    线框纯黑   avg≈(27,28,28)   dark > 80%
    渲染纯白   avg≈(207,207,207) bright > 40%
    线框全空   NO INK / ink 极小          -> 查"ShowEdges 被全局关掉"
    整片灰蓝   avg 落在中间且 ink 占比 >90% -> 大概率量到了地面/背景

⚠️ 背景色取角落像素。角落若落在地坪/深色地面上，会把地面算成模型像素，
   得出"颜色改不动"的假结论（本项目踩过两次）。可疑时用 --bg x,y 指定背景点。
"""
import sys


def ink_stats(path, bg_xy=(1, 1), thresh=30, size=360):
    from PIL import Image
    im = Image.open(path).convert("RGB")
    im.thumbnail((size, size))
    bg = im.getpixel(bg_xy)
    raw = im.tobytes()                      # 比 getdata() 快且无弃用警告
    px = []
    for i in range(0, len(raw), 3):
        r, g, b = raw[i], raw[i + 1], raw[i + 2]
        if abs(r - bg[0]) + abs(g - bg[1]) + abs(b - bg[2]) > thresh:
            px.append((r, g, b))
    if not px:
        return {"ink": 0, "text": "NO INK   bg=%s" % (bg,)}
    n = len(px)
    avg = tuple(sum(q[i] for q in px) / float(n) for i in range(3))
    dark = sum(1 for q in px if sum(q) / 3.0 < 60) / float(n)
    bright = sum(1 for q in px if sum(q) / 3.0 > 215) / float(n)
    cover = n / float(im.size[0] * im.size[1])
    text = ("ink=%5d (%4.1f%% of img)  avg=(%3.0f,%3.0f,%3.0f)  "
            "dark=%4.1f%%  bright=%4.1f%%  bg=%s") % (
        n, 100 * cover, avg[0], avg[1], avg[2], 100 * dark, 100 * bright, bg)
    return {"ink": n, "avg": avg, "dark": dark, "bright": bright,
            "cover": cover, "bg": bg, "text": text}


def main():
    args = sys.argv[1:]
    bg = (1, 1)
    if "--bg" in args:
        i = args.index("--bg")
        x, y = args[i + 1].split(",")
        bg = (int(x), int(y))
        del args[i:i + 2]
    if not args:
        print(__doc__)
        return
    for p in args:
        try:
            print("%-40s %s" % (p.split("/")[-1].split("\\")[-1], ink_stats(p, bg)["text"]))
        except Exception as e:
            print("%-40s ERR %s" % (p, e))


if __name__ == "__main__":
    main()
