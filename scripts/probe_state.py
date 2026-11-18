# -*- coding: utf-8 -*-
"""probe_state.py —— 只读体检。动手前跑一遍，不改任何东西。

用法：
    python probe_state.py            # 报告当前文档
    python probe_state.py --layers   # 附带每层对象数与图层色
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from rhino_conn import (connect, describe, probe, unpack,        # noqa: E402
                        window_ready, model_bbox)


def main():
    want_layers = "--layers" in sys.argv
    dispatch, rs, ver = connect()
    print("Rhino %s" % ver)
    print("-" * 60)
    print(describe(rs))

    # 出图前置条件：主窗口到底在不在屏幕上（不在 = 出图必空，且跟模型无关）
    ok, detail = window_ready()
    print("-" * 60)
    print("window_ready = %s   %s" % (ok, detail))
    if not ok:
        print("   !! CreatePreviewImage 现在只会出空白图。先 ensure_window()，")
        print("      或让用户关掉启动画面/插件报错框。**不要因此改模型。**")

    bb = model_bbox(rs)
    if bb:
        cx, cy, cz = ((bb[0] + bb[3]) / 2, (bb[1] + bb[4]) / 2, (bb[2] + bb[5]) / 2)
        print("bbox中心   = (%.2f, %.2f, %.2f)   <- 相机目标必须是这里，不是 (0,0,0)"
              % (cx, cy, cz))

    if want_layers:
        print("-" * 60)
        allobjs = list(rs.AllObjects() or [])
        try:
            print("%-26s %5s  %-16s %s" % ("layer", "obj", "color(RGB)", "visible"))
            for L in (rs.LayerNames() or []):
                try:
                    n = len(rs.ObjectsByLayer(L) or [])
                except Exception:
                    n = -1
                try:
                    c = unpack(rs.LayerColor(L))
                except Exception:
                    c = ("ERR",)
                try:
                    vis = rs.LayerVisible(L)
                except Exception:
                    vis = "?"
                print("%-26s %5s  %-16s %s" % (L, n, c, vis))
            print("total objects = %d" % len(allobjs))
        except Exception as e:
            print("layer dump failed: %s" % e)

    # 只读提醒
    i = probe(rs)
    if i.get("modified"):
        print()
        print("!! DocumentModified = True —— 用户有未保存改动。")
        print("   不要自动 Open / SaveAs / 覆盖存盘，先问用户。")


if __name__ == "__main__":
    main()
