// Ridgelines drawing, prototype of the plugin JS (docs/brief.md, Template requirements).
// Decodes the entry's 8-bit heightmap and draws west to east lines as inline SVG
// inside the drawing container. Every colour comes from TRMNLPaint and every
// size goes through TRMNLPaint.px(). Draws nothing if the container measures zero.
(function () {
  // Look parameters. gap is the line spacing before px() scaling: at 6.1 the
  // TRMNL OG full landscape drawing (780 x 411) holds 64 lines, the chosen look.
  // An entry's width_km spans REF_GAPS line gaps, the OG full drawing's width,
  // so every view and device keeps the same map scale and shows more or less
  // terrain instead of a shrunken or stretched map.
  var LOOK = { gap: 6.1, ripple: 4, floor: null, tick: 2, labelGap: 0.5 };
  var REF_GAPS = 128;

  function decode(entry) {
    var s = atob(entry.heights), n = entry.grid, a = new Uint8Array(n * n);
    for (var i = 0; i < a.length; i++) a[i] = s.charCodeAt(i);
    return a;
  }

  // Bilinear height (0..255) at km offsets from the crop centre (x east, y north).
  function heightAt(entry, a, x, y) {
    var n = entry.grid, side = entry.crop.side_km;
    var c = (x / side + 0.5) * (n - 1), r = (0.5 - y / side) * (n - 1);
    if (c < 0 || r < 0 || c > n - 1 || r > n - 1) return null;
    var c0 = Math.min(Math.floor(c), n - 2), r0 = Math.min(Math.floor(r), n - 2);
    var fc = c - c0, fr = r - r0, i = r0 * n + c0;
    return (a[i] * (1 - fc) + a[i + 1] * fc) * (1 - fr) + (a[i + n] * (1 - fc) + a[i + n + 1] * fc) * fr;
  }

  function svgEl(tag, attrs) {
    var e = document.createElementNS("http://www.w3.org/2000/svg", tag);
    for (var k in attrs) e.setAttribute(k, attrs[k]);
    return e;
  }

  function draw(box, entry, opts) {
    opts = Object.assign({}, LOOK, opts || {});
    while (box.firstChild) box.removeChild(box.firstChild);
    var w = box.clientWidth, h = box.clientHeight;
    var report = { drawn: false, w: w, h: h };
    if (!w || !h) return report;                          // collapsed container: caption alone

    var el = { el: box };
    var ink = TRMNLPaint.textColor("default", el);
    var paper = TRMNLPaint.semantic("canvas", el).color;
    var gap = TRMNLPaint.px(opts.gap, el), amp = opts.ripple * gap;
    var depth = parseFloat(TRMNLPaint.cssVar("--framework-bit-depth", el)) || 1;
    var a = decode(entry);
    var floor = opts.floor == null ? entry.floor : opts.floor;
    if (opts.floorPct != null) {                          // tuning only: percentile of the stored square
      var sorted = Array.prototype.slice.call(a).sort(function (p, q) { return p - q; });
      floor = sorted[Math.min(sorted.length - 1, Math.floor(opts.floorPct / 100 * sorted.length))];
    }
    var top255 = opts.norm === "crop" ? 255 : entry.top;   // ripple can overshoot above top
    var kmPerPx = entry.crop.width_km / (REF_GAPS * TRMNLPaint.px(LOOK.gap, el)) * (opts.zoom || 1);

    var lines = Math.max(2, Math.floor((h - amp) / gap) + 1);
    var used = amp + (lines - 1) * gap, top = (h - used) / 2;

    // Window in km. Centred on the crop, shifted just enough to keep the high
    // point inside with a margin, and clamped to the stored square.
    var half = entry.crop.side_km / 2, hw = w / 2 * kmPerPx, hh = h / 2 * kmPerPx;
    var pk = entry.peak_km, margin = 6 * gap * kmPerPx;
    function shift(c, p, hs) {
      if (p - c > hs - margin) c = p - (hs - margin);
      if (c - p > hs - margin) c = p + (hs - margin);
      return Math.max(-half + hs, Math.min(half - hs, c));
    }
    var cx = shift(0, pk[0], hw), cy = shift(0, pk[1], hh);

    // The info box (bottom left, setting) covers part of the drawing. If the
    // summit falls under it, move the map the shorter way: summit above the
    // box, or right of it. The box keeps its framework position.
    var info = box.parentNode && box.parentNode.querySelector("[data-ridgelines-box]");
    if (info && info.offsetWidth) {
      var bx = info.offsetLeft + info.offsetWidth, by = info.offsetTop, room = 4 * gap;
      var ppx = w / 2 + (pk[0] - cx) / kmPerPx, ppy = h / 2 - (pk[1] - cy) / kmPerPx;
      if (ppx < bx + room && ppy > by - room) {
        var up = ppy - (by - room), right = bx + room - ppx;
        if (up <= right) cy = Math.max(-half + hh, Math.min(half - hh, cy - up * kmPerPx));
        else cx = Math.max(-half + hw, Math.min(half - hw, cx - right * kmPerPx));
        report.movedForBox = up <= right ? "up" : "right";
      }
      report.box = [info.offsetLeft, info.offsetTop, info.offsetWidth, info.offsetHeight];
    }
    report.outside = hw > half || hh > half;              // window wider than the stored square

    var svg = svgEl("svg", { width: w, height: h, viewBox: "0 0 " + w + " " + h });
    if (depth <= 1) svg.setAttribute("shape-rendering", "crispEdges");
    var stroke = TRMNLPaint.px(1, el), step = Math.max(1, TRMNLPaint.px(2, el));
    // Sample every line first, so the ripple scale can follow the crop's top
    // (norm "crop", default) or the visible window's top (norm "window").
    var rows = [], xs = [], hiSeen = 0;
    for (var px = 0; px <= w + 0.01; px += step) xs.push(px);
    for (var i = 0; i < lines; i++) {
      var base = top + amp + i * gap, yk = cy + (h / 2 - base) * kmPerPx, vals = [];
      for (var j = 0; j < xs.length; j++) {
        var v = heightAt(entry, a, cx + (xs[j] - w / 2) * kmPerPx, yk);
        vals.push(v == null ? 0 : v);
        if (v > hiSeen) hiSeen = v;
      }
      rows.push({ base: base, yk: yk, vals: vals });
    }
    if (opts.norm === "window") top255 = Math.max(hiSeen, floor + 1);

    var peakPt = null, best = Infinity;
    rows.forEach(function (row) {
      var pts = [];
      for (var j = 0; j < xs.length; j++) {
        var t = Math.max(0, (row.vals[j] - floor) / (top255 - floor)), y = row.base - t * amp;
        pts.push(xs[j].toFixed(1) + "," + y.toFixed(1));
        var xk = cx + (xs[j] - w / 2) * kmPerPx, d = Math.abs(xk - pk[0]) + Math.abs(row.yk - pk[1]) * 3;
        if (d < best && Math.abs(row.yk - pk[1]) < gap * kmPerPx) { best = d; peakPt = [xs[j], y]; }
      }
      svg.appendChild(svgEl("polygon", { points: pts.join(" ") + " " + w + "," + h + " 0," + h, fill: paper, stroke: "none" }));
      svg.appendChild(svgEl("polyline", { points: pts.join(" "), fill: "none", stroke: ink, "stroke-width": stroke, "stroke-linejoin": "round" }));
    });
    report.lines = lines;

    if (opts.label !== false && peakPt && opts.peakName) {
      var type = TRMNLPaint.type("label", el);
      var fs = parseFloat(type.fontSize), tick = opts.tick * gap;
      var x = peakPt[0], y = peakPt[1];
      var tickLine = svgEl("line", { x1: x, y1: y - gap * 0.5, x2: x, y2: y - gap * 0.5 - tick, stroke: ink, "stroke-width": stroke });
      svg.appendChild(tickLine);
      var text = svgEl("text", { x: x, y: y - gap * 0.5 - tick - gap * opts.labelGap, "text-anchor": "middle", fill: ink,
        "font-family": type.fontFamily, "font-size": type.fontSize, "font-weight": type.fontWeight });
      text.textContent = opts.peakName;
      svg.appendChild(text);
      box.appendChild(svg);
      var bb = text.getBBox(), pad = gap * 0.5;
      if (bb.y < 0) {                                     // summit near the top edge: hang the label below it
        tickLine.setAttribute("y1", y + gap * 0.5);
        tickLine.setAttribute("y2", y + gap * 0.5 + tick);
        text.setAttribute("y", y + gap * 0.5 + tick + gap * opts.labelGap + (y - bb.y - gap * 0.5 - tick - gap * opts.labelGap));
        bb = text.getBBox();
        report.labelBelow = true;
      }
      var dx = Math.max(pad - bb.x, Math.min(0, w - pad - (bb.x + bb.width)));
      if (dx) { text.setAttribute("x", x + dx); bb = text.getBBox(); }
      // Last resort when the map could not move far enough: slide the label clear of the box.
      if (report.box) {
        var b = report.box;
        if (bb.x < b[0] + b[2] + pad && bb.y + bb.height > b[1] - pad && bb.y < b[1] + b[3]) {
          text.setAttribute("x", parseFloat(text.getAttribute("x")) + (b[0] + b[2] + 2 * pad - bb.x));
          bb = text.getBBox();
          report.labelSlid = true;
        }
      }
      var back = svgEl("rect", { x: bb.x - pad, y: bb.y, width: bb.width + 2 * pad, height: bb.height, fill: paper });
      svg.insertBefore(back, text);
      report.label = { x: bb.x, y: bb.y, w: bb.width, h: bb.height, font: type.fontFamily + " " + fs + "px" };
    } else {
      box.appendChild(svg);
    }
    report.drawn = true; report.gap = gap; report.kmPerPx = kmPerPx; report.window = [cx, cy, hw, hh];
    return report;
  }

  window.Ridgelines = { draw: draw, LOOK: LOOK };
})();
