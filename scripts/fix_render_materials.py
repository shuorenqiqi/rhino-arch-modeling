# -*- coding: utf-8 -*-
"""fix_render_materials.py —— 白模在【渲染】模式下"全透明 / 看不见"时的一键修。

什么时候跑它
    切到 Render 模式，模型像玻璃一样透，或者干脆消失。
    先 `audit_materials()` 看一眼：只要**整批对象**透明度都 > 0，就是这个病（P44 / P45）。

两个病因
    ① 有人给玻璃设了 MaterialTransparency，`AddMaterialToObject` 却把值写进了
       被多个对象共享的材质槽 → 整栋楼一起吃上透明度。
    ② 就算不透明，纯白材质 + 纯白渲染背景 = 白对白，同样"看不见"。

用法
    PY="$HOME/.workbuddy/binaries/python/envs/default/Scripts/python.exe"   # 换成你自己的 python（需 pywin32）
    "$PY" fix_render_materials.py                          # 用默认配色
    "$PY" fix_render_materials.py --glass 06 玻璃 --site 09 场地

修完必须回读：脚本末尾会打印每类对象实际吃到的 color / transparency，
以及 audit_materials() 的残留（正常为 0）。**不看回读就等于没修。**
"""
import os
import sys
import time

sys.path.insert(0, os.path.expanduser(r"~/.workbuddy/skills/rhino-arch-modeling/scripts"))
from rhino_conn import (connect, audit_materials, reset_materials, packed,
                        unpack, render_bg)


def main():
    site = ["场地"]
    args = sys.argv[1:]
    if "--site" in args:
        site = [args[args.index("--site") + 1]]

    d, rs, v = connect()
    t0 = time.time()
    objs = list(rs.AllObjects() or [])
    if not objs:
        print("文档里没有对象 —— 先确认连对了实例（P03b）")
        return

    bad = audit_materials(rs)
    print("[audit] 有透明度的材质槽 %d 个，涉及对象 %d 个"
          % (len(bad), sum(len(x) for x in bad.values())))

    left = reset_materials(rs, site_layers=site)
    print("[fix] %.1fs  残留透明材质槽 %d" % (time.time() - t0, len(left)))

    # 回读抽样（★ 不回读等于没修）
    for key in ("屋面", "玻璃", "场地"):
        o = next((x for x in objs if key in rs.ObjectLayer(x)), None)
        if o:
            mi = rs.ObjectMaterialIndex(o)
            print("  %-4s src=%s color=%s transp=%s layer=%s"
                  % (key, rs.ObjectMaterialSource(o), unpack(rs.MaterialColor(mi)),
                     rs.MaterialTransparency(mi), rs.ObjectLayer(o)))
    print("  渲染背景 =", unpack(rs.RenderColor(1)))


if __name__ == "__main__":
    main()
