"""Read-only page transforms and per-glyph visibility for the optional PDF adapter.

The extraction libraries expose glyphs even when a clipping path or text-render
mode hides them. Track a bounded subset of graphics state; unsupported clipping
and Form content remain unknown. No source bytes are normalized or rewritten.
"""

from __future__ import annotations

import copy
import math
from dataclasses import dataclass

from pdfminer.pdfinterp import PDFPageInterpreter
from pdfminer.pdftypes import resolve1
from pdfminer.psparser import literal_name
from pdfminer.utils import apply_matrix_pt
from pdfplumber.page import Page, PDFPageAggregatorWithMarkedContent


@dataclass(frozen=True)
class Geometry:
    crop: tuple[float, float, float, float]
    rotation: int

    @classmethod
    def from_page(cls, page):
        rotation = resolve1(page.attrs.get("Rotate", 0))
        unit = resolve1(page.attrs.get("UserUnit", 1))
        if not isinstance(rotation, (int, float)) or rotation % 90 or unit != 1:
            raise ValueError("unsupported rotation or user unit")
        media = tuple(float(v) for v in page.mediabox)
        crop = tuple(float(v) for v in page.cropbox)
        if len(media) != 4 or len(crop) != 4 or not all(map(math.isfinite, media + crop)):
            raise ValueError("invalid page box")
        if media[2] <= media[0] or media[3] <= media[1]:
            raise ValueError("invalid media box")
        left, bottom = max(media[0], crop[0]), max(media[1], crop[1])
        right, top = min(media[2], crop[2]), min(media[3], crop[3])
        if not 0 < right - left <= 20000 or not 0 < top - bottom <= 20000:
            raise ValueError("invalid crop box")
        height = media[3] - media[1]
        return cls((left, height - top, right, height - bottom), int(rotation) % 360)

    @property
    def page_box(self):
        a, b, c, d = self.crop
        width, height = c - a, d - b
        return (0, 0, height, width) if self.rotation in (90, 270) else (0, 0, width, height)

    def point(self, x, y, *, inverse=False):
        a, b, c, d = self.crop
        width, height = c - a, d - b
        if not inverse:
            x, y = x - a, y - b
            if self.rotation == 90:
                return height - y, x
            if self.rotation == 180:
                return width - x, height - y
            if self.rotation == 270:
                return y, width - x
            return x, y
        if self.rotation == 90:
            x, y = y, height - x
        elif self.rotation == 180:
            x, y = width - x, height - y
        elif self.rotation == 270:
            x, y = width - y, x
        return x + a, y + b

    def box(self, bounds, *, inverse=False):
        points = [self.point(x, y, inverse=inverse) for x in bounds[::2] for y in bounds[1::2]]
        return (
            min(p[0] for p in points),
            min(p[1] for p in points),
            max(p[0] for p in points),
            max(p[1] for p in points),
        )


class GuardedDevice(PDFPageAggregatorWithMarkedContent):
    guard = (None, True)
    form_depth = 0

    def render_char(self, *args, **kwargs):
        advance = super().render_char(*args, **kwargs)
        char = self.cur_item._objs[-1]
        clip, visible = self.guard
        char.paperdelta_visible = bool(
            visible
            and not self.form_depth
            and clip is not False
            and (
                clip is None
                or (
                    clip[0] - 0.00001 <= char.x0 < char.x1 <= clip[2] + 0.00001
                    and clip[1] - 0.00001 <= char.y0 < char.y1 <= clip[3] + 0.00001
                )
            )
        )
        return advance


class GuardedInterpreter(PDFPageInterpreter):
    def init_state(self, ctm):
        super().init_state(ctm)
        self.clip, self.pending_clip = None, None
        self.visibility_stack = []
        self.ext_state = {}
        self.path_mixed = False
        self.pending_text_clip = False

    def do_q(self):
        if self.curpath:
            self.path_mixed = True
        if len(self.visibility_stack) >= 1000:
            raise ValueError("graphics stack limit")
        self.visibility_stack.append((self.clip, self.ext_state.copy()))
        super().do_q()

    def do_Q(self):
        if self.curpath:
            self.path_mixed = True
        if not self.visibility_stack:
            raise ValueError("unbalanced graphics state")
        self.clip, self.ext_state = self.visibility_stack.pop()
        super().do_Q()

    def do_cm(self, a, b, c, d, e, f):
        if self.curpath:
            self.path_mixed = True
        super().do_cm(a, b, c, d, e, f)

    def do_W(self):
        path = self.curpath
        if self.path_mixed or [p[0] for p in path] not in (
            ["m", "l", "l", "l", "h"],
            ["m", "l", "l", "l", "l", "h"],
        ):
            self.pending_clip = False
            return
        points = [apply_matrix_pt(self.ctm, p[1:]) for p in path if p[0] != "h"]
        if len(points) == 5:
            if points[-1] != points[0]:
                self.pending_clip = False
                return
            points.pop()
        xs, ys = {round(p[0], 8) for p in points}, {round(p[1], 8) for p in points}
        if (
            len(xs) != 2
            or len(ys) != 2
            or any(
                a[0] != b[0] and a[1] != b[1]
                for a, b in zip(points, points[1:] + points[:1], strict=True)
            )
        ):
            self.pending_clip = False
        else:
            self.pending_clip = (min(xs), min(ys), max(xs), max(ys))

    def do_W_a(self):
        self.do_W()

    def _end_path(self, operation):
        operation()
        if self.pending_clip is not None:
            if self.clip is False or self.pending_clip is False:
                self.clip = False
            elif self.clip is None:
                self.clip = self.pending_clip
            else:
                a, b = self.clip, self.pending_clip
                self.clip = (max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3]))
        self.pending_clip, self.path_mixed = None, False

    def do_n(self):
        self._end_path(super().do_n)

    def do_S(self):
        self._end_path(super().do_S)

    def do_s(self):
        self._end_path(super().do_s)

    def do_f(self):
        self._end_path(super().do_f)

    def do_F(self):
        self.do_f()

    def do_f_a(self):
        self._end_path(super().do_f_a)

    def do_B(self):
        self._end_path(super().do_B)

    def do_B_a(self):
        self._end_path(super().do_B_a)

    def do_b(self):
        self._end_path(super().do_b)

    def do_b_a(self):
        self._end_path(super().do_b_a)

    def do_gs(self, name):
        states = resolve1(self.resources.get("ExtGState", {}))
        state = resolve1(states.get(literal_name(name)))
        if not isinstance(state, dict):
            raise ValueError("unknown graphics state")
        self.ext_state.update({k: resolve1(v) for k, v in state.items()})

    def do_TJ(self, seq):
        self.pending_text_clip |= self.textstate.render in (4, 5, 6, 7)
        state = self.ext_state
        opaque = (
            state.get("ca", 1) == 1
            and state.get("CA", 1) == 1
            and str(state.get("SMask", "None")) in ("None", "/'None'")
            and str(state.get("BM", "Normal")) in ("Normal", "/'Normal'", "/'Compatible'")
            and not any(key in state for key in ("Font", "TR", "TR2", "HT"))
        )
        previous = self.device.guard
        self.device.guard = self.clip, opaque and self.textstate.render == 0
        try:
            super().do_TJ(seq)
        finally:
            self.device.guard = previous

    def do_ET(self):
        super().do_ET()
        if self.pending_text_clip:
            self.clip = False
            self.pending_text_clip = False

    def do_Do(self, identity):
        obj = resolve1(self.xobjmap.get(literal_name(identity)))
        form = obj is not None and str(obj.get("Subtype")) == "/'Form'"
        self.device.form_depth += int(form)
        try:
            super().do_Do(identity)
        finally:
            self.device.form_depth -= int(form)


class GuardedPage(Page):
    @property
    def layout(self):
        if not hasattr(self, "_layout"):
            device = GuardedDevice(
                self.pdf.rsrcmgr, pageno=self.page_number, laparams=self.pdf.laparams
            )
            interpreter = GuardedInterpreter(self.pdf.rsrcmgr, device)
            interpreter.process_page(self.page_obj)
            if interpreter.visibility_stack or interpreter.pending_clip is not None:
                raise ValueError("unfinished graphics state")
            self._layout = device.get_result()
        return self._layout

    def process_object(self, obj):
        result = super().process_object(obj)
        if hasattr(obj, "paperdelta_visible"):
            result["paperdelta_visible"] = obj.paperdelta_visible
        return result


def extraction_page(page):
    """Extract in unrotated space while retaining the original page for previews."""
    obj = copy.copy(page.page_obj)
    obj.attrs = {**obj.attrs, "Rotate": 0}
    obj.rotate = 0
    return GuardedPage(page.pdf, obj, page.page_number, page.initial_doctop)
