"""F5.9 Patient App and F5.10 Caregiver App screen flows (mid-fidelity wireframes).

Run from the repository root:
    uv run --no-project --with matplotlib python fyp1FinalReport/ThesisFigs/src/fig_screens.py

Every label is copied from the Flutter code:
Patient App: views/onboarding_dialog.dart (Your name, Caregiver name, Relationship,
Caregiver phone number, Save and continue), views/patient_home.dart (_ServerBadge,
_ObjectButton tiles from trackedObjects(), hint "Try: Where is my mug?", lookupObject,
_recall), views/answer_drawer.dart (onClose, CandidateCard), models/memory_answer.dart
(ResolutionMode labels Found it / Best guess / I'm not sure — which one? / I'm not sure;
TimeCue chips Back to now / This morning / Yesterday), services/api_service.dart
(notFoundMessage, "Can't reach Aegis memory…"), views/call_view.dart (Call <name> now,
Send Message, Change caregiver or number, Back to home), theme/app_theme.dart
(touchTarget 44).
Caregiver App: views/caregiver_home.dart (_tabs Home/Track/Interior/Status, History
button, hint "Ask about the patient's things…"), views/home_tab.dart (CaregiverHomeTab,
_TileButton), views/caregiver_tabs.dart (SearchHistoryTab with Most Recent / Most
Frequent filters, TrackingTab timeline() + Interactions, InteriorTab rooms() +
renameRoom, StatusTab captureStatus()), views/enroll_dialog.dart (Name, e.g. Reading
glasses; object and usual room dropdowns; Save item; instanceIdFor → enrollItem),
views/answer_drawer.dart ("<mode> · ranker: full").
"""

import matplotlib.patches as mp

from boxdraw import Canvas, INK, LINE, MUTED

FRAME, SCREEN = "#2B2F36", "#FBF7F0"
OCHRE, ESPRESSO, PURPLE = "#C98A2B", "#4A3426", "#7B4BA8"
PW, PH = 1.32, 2.55


def phone(c, x, y, title, dark=False):
    c.ax.add_patch(mp.FancyBboxPatch((x, y), PW, PH, boxstyle="round,pad=0,rounding_size=0.14",
                                     facecolor=FRAME, edgecolor=FRAME, lw=1, zorder=2))
    c.ax.add_patch(mp.FancyBboxPatch((x + 0.07, y + 0.12), PW - 0.14, PH - 0.3,
                                     boxstyle="round,pad=0,rounding_size=0.06",
                                     facecolor="#2A211B" if dark else SCREEN, edgecolor="none", zorder=3))
    c.ax.text(x + PW / 2, y + PH + 0.1, title, ha="center", va="bottom", fontsize=7.2,
              fontweight="bold", color=INK)
    return x + 0.12, y + 0.17, PW - 0.24, PH - 0.4  # inner content box


def el(c, x, y, w, h, text, fill="#FFFFFF", edge="#B9B2A6", fs=5.4, color=INK, bold=False, r=0.04):
    c.ax.add_patch(mp.FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0,rounding_size={r}",
                                     facecolor=fill, edgecolor=edge, lw=0.7, zorder=4))
    if text:
        c.ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs, color=color,
                  fontweight="bold" if bold else "normal", zorder=5, linespacing=1.05)


def txt(c, x, y, text, fs=5.4, color=INK, ha="left", bold=False):
    c.ax.text(x, y, text, ha=ha, va="center", fontsize=fs, color=color, zorder=5,
              fontweight="bold" if bold else "normal", linespacing=1.05)


def callout(c, x, y, n):
    c.ax.add_patch(mp.Circle((x, y), 0.075, facecolor="#D9822B", edgecolor="white", lw=0.6, zorder=8))
    c.ax.text(x, y, str(n), ha="center", va="center", fontsize=5.6, color="white", fontweight="bold", zorder=9)


def link(c, p, q, label, at, ha="center", rad=0.0, dashed=False):
    c.ax.annotate("", xy=q, xytext=p, zorder=7,
                  arrowprops=dict(arrowstyle="-|>", color=LINE, lw=1.0, shrinkA=0, shrinkB=0,
                                  linestyle=(0, (4, 2.5)) if dashed else "-",
                                  connectionstyle=f"arc3,rad={rad}"))
    c.ax.text(*at, label, ha=ha, va="center", fontsize=6.0, color=INK, zorder=8, linespacing=1.12,
              bbox=dict(facecolor="white", edgecolor="none", pad=0.4))


# ============================================================ F5.9 Patient App
c = Canvas(6.0, 6.2, font=7)
# onboarding
ix, iy, iw, ih = phone(c, 0.05, 3.3, "Onboarding dialog", dark=True)
el(c, ix, iy + 0.25, iw, ih - 0.35, "", fill="#3A2E25", edge=OCHRE)
for i, lab in enumerate(["Your name", "Caregiver name", "Relationship", "Caregiver phone number"]):
    el(c, ix + 0.06, iy + ih - 0.55 - i * 0.33, iw - 0.12, 0.24, lab, fill="#2A211B", edge=OCHRE,
       color="#E9D9BF", fs=5.2)
el(c, ix + 0.06, iy + 0.35, iw - 0.12, 0.22, "Save and continue", fill=OCHRE, edge=OCHRE,
   color="white", bold=True)
txt(c, ix + iw / 2, iy + ih - 0.13, "PreferencesService", fs=5.0, color="#E9D9BF", ha="center")

# home
hx, hy, hw, hh = phone(c, 2.3, 3.3, "Patient Home", dark=True)
el(c, hx, hy + hh - 0.22, 0.55, 0.18, "● live", fill="#1E3B2C", edge="#2E8B57", color="#BDE5C8", fs=5.0)
el(c, hx + 0.6, hy + hh - 0.22, hw - 0.6, 0.18, "server ▾", fill="#3A2E25", edge=OCHRE, color="#E9D9BF", fs=5.0)
for r in range(2):
    for k in range(3):
        el(c, hx + k * 0.36, hy + hh - 0.62 - r * 0.38, 0.32, 0.32, ["mug", "keys", "phone", "wallet", "glasses", "?"][r * 3 + k],
           fill="#3A2E25", edge=OCHRE, color="#E9D9BF", fs=4.8)
c.ax.add_patch(mp.Circle((hx + hw / 2, hy + 0.78), 0.2, facecolor=OCHRE, edgecolor="#F0C987", lw=1.2, zorder=5))
c.ax.add_patch(mp.Circle((hx + hw / 2, hy + 0.78), 0.27, fill=False, edgecolor="#F0C987", lw=0.6, zorder=5))
txt(c, hx + hw / 2, hy + 0.78, "mic", fs=5.2, color="white", ha="center", bold=True)
el(c, hx, hy + 0.3, hw, 0.18, "Try: Where is my mug?", fill="#3A2E25", edge="#6B5A48", color="#B9A88F", fs=4.9)
el(c, hx, hy + 0.04, hw, 0.2, "Call", fill="#1E3B2C", edge="#2E8B57", color="#BDE5C8", bold=True)
callout(c, hx + hw + 0.02, hy + hh - 0.45, 1)
callout(c, hx - 0.02, hy + hh + 0.02, 2)
txt(c, hx + hw / 2, hy + hh - 1.05, "_ObjectButton tiles", fs=4.7, color="#B9A88F", ha="center")

# answer drawer
dx, dy, dw, dh = phone(c, 4.6, 3.3, "Answer Drawer")
el(c, dx, dy + dh - 0.2, dw, 0.18, "Where is my mug?", fill="#FFFFFF", edge="#D9CFC0", bold=True, fs=5.2)
el(c, dx, dy + dh - 0.42, 0.7, 0.16, "Found it", fill="#DFF0E3", edge="#2E8B57", fs=5.0)
txt(c, dx + 0.75, dy + dh - 0.34, "badge", fs=4.6, color=MUTED)
for i, lab in enumerate(["Back to now", "This morning", "Yesterday"]):
    el(c, dx + i * 0.36, dy + dh - 0.64, 0.34, 0.15, lab, fill="#FBEBD3", edge=OCHRE, fs=3.9)
txt(c, dx, dy + dh - 0.9, "summary sentence", fs=4.9, color=MUTED)
txt(c, dx + dw / 2, dy + dh - 0.75, "tap: recall(text, cue)", fs=4.4, color=MUTED, ha="center")
for i in range(3):
    el(c, dx, dy + dh - 1.25 - i * 0.26, dw, 0.23, "", fill="#FFFFFF", edge="#D9CFC0")
    el(c, dx + 0.03, dy + dh - 1.225 - i * 0.26, 0.3, 0.18, "crop", fill="#E8E1D6", edge="#D9CFC0", fs=4.4)
    txt(c, dx + 0.38, dy + dh - 1.135 - i * 0.26, "CandidateCard", fs=4.6)
txt(c, dx + dw / 2, dy + 0.22, "or: Not found. Object not in history\nor: Can't reach Aegis memory…",
    fs=4.3, color="#C0392B", ha="center")
callout(c, dx + dw + 0.02, dy + 0.35, 4)

# call view
kx, ky, kw, kh = phone(c, 2.3, 0.2, "Call View", dark=True)
c.ax.add_patch(mp.Circle((kx + kw / 2, ky + kh - 0.45), 0.25, facecolor="#1E3B2C", edgecolor="#2E8B57", lw=1, zorder=5))
txt(c, kx + kw / 2, ky + kh - 0.45, "<name>", fs=5.0, color="#BDE5C8", ha="center", bold=True)
el(c, kx, ky + 0.95, kw, 0.24, "Call <name> now", fill="#2E8B57", edge="#2E8B57", color="white", bold=True)
el(c, kx, ky + 0.65, kw, 0.24, "Send Message", fill="#3A2E25", edge="#6B5A48", color="#E9D9BF")
el(c, kx, ky + 0.35, kw, 0.24, "Change caregiver or number", fill="#3A2E25", edge="#6B5A48",
   color="#E9D9BF", fs=4.8)
el(c, kx, ky + 0.06, kw, 0.24, "Back to home", fill="#3A2E25", edge="#6B5A48", color="#E9D9BF")
txt(c, kx + kw + 0.1, ky + 1.07, "tel:", fs=5.4, color=MUTED)
txt(c, kx + kw + 0.1, ky + 0.77, "sms: (DeviceCallService)", fs=5.4, color=MUTED)

# transitions
link(c, (1.37, 4.55), (2.3, 4.55), "saved", (1.83, 4.72))
link(c, (3.62, 5.0), (4.6, 5.0), "tile tap:\nlookupObject\n→ GET /query", (4.11, 5.4))
link(c, (3.62, 4.45), (4.6, 4.45), "mic (on-device\nSTT) or text:\nask(text) →\n/query, then /ask",
     (4.11, 4.0))
link(c, (4.6, 3.55), (3.62, 3.55), "onClose", (4.11, 3.4))
link(c, (2.96, 3.3), (2.96, 3.06), "Call", (3.12, 3.18), ha="left")
c.note(5.95, 2.4, "① 44 pt touch targets (PatientTheme.touchTarget)\n"
       "② espresso / ochre theme (PatientTheme)\n③ the app never changes memory (read-only routes)\n"
       "④ no answer is invented offline", ha="right", fs=6.2, color=INK)
c.note(5.95, 1.6, "The drawer has no call button: the only way to\nCall View is the Call button on Patient Home.",
       ha="right", fs=6.0)
c.save("ch5-patient-app-flow")

# ============================================================ F5.10 Caregiver App
c = Canvas(6.0, 6.2, font=7)
# onboarding
ix, iy, iw, ih = phone(c, 0.05, 3.3, "Onboarding dialog")
for i, lab in enumerate(["Patient's name", "Memory server URL\nhttps://…", "Home store id"]):
    el(c, ix + 0.03, iy + ih - 0.42 - i * 0.42, iw - 0.06, 0.3, lab, edge=PURPLE, fs=5.0)
el(c, ix + 0.03, iy + 0.55, iw - 0.06, 0.2, "Use default", edge="#B9B2A6")
el(c, ix + 0.03, iy + 0.28, iw - 0.06, 0.2, "Save and continue", fill=PURPLE, edge=PURPLE, color="white", bold=True)

# home with tabs
hx, hy, hw, hh = phone(c, 2.3, 3.3, "Caregiver Home")
el(c, hx, hy + hh - 0.26, hw - 0.42, 0.24, "Ask about the\npatient's things…", edge=PURPLE, fs=4.2)
el(c, hx + hw - 0.38, hy + hh - 0.26, 0.38, 0.24, "History", fill="#E9DFF2", edge=PURPLE, fs=4.8)
for r in range(2):
    for k in range(3):
        el(c, hx + k * 0.36, hy + hh - 0.6 - r * 0.32, 0.32, 0.28, ["mug", "keys", "phone", "wallet", "glasses", "pills"][r * 3 + k],
           fill="#F3EEF8", edge=PURPLE, fs=4.8)
txt(c, hx + hw / 2, hy + hh - 1.02, "Home tab: _TileButton", fs=4.4, color=MUTED, ha="center")
for i, t in enumerate(["Track: timeline,\nInteractions", "Interior: rooms\n+ Rename room", "Status: health,\ncapture status"]):
    el(c, hx, hy + 0.88 - i * 0.28, hw, 0.25, t, fill="#FFFFFF", edge="#D6CCE3", fs=4.6)
for i, t in enumerate(["Home", "Track", "Interior", "Status"]):
    el(c, hx + i * 0.27, hy + 0.03, 0.26, 0.15, t, fill="#E9DFF2" if i == 0 else "#FFFFFF", edge=PURPLE, fs=4.0)

# answer drawer
dx, dy, dw, dh = phone(c, 4.6, 3.3, "Answer Drawer")
el(c, dx, dy + dh - 0.2, dw, 0.18, "Where are the keys?", bold=True, fs=5.0, edge="#D6CCE3")
el(c, dx, dy + dh - 0.42, dw, 0.16, "ranked · ranker: full", fill="#E9DFF2", edge=PURPLE, fs=4.8)
for i, lab in enumerate(["Back to now", "This morning", "Yesterday"]):
    el(c, dx + i * 0.36, dy + dh - 0.64, 0.34, 0.15, lab, fill="#F3EEF8", edge=PURPLE, fs=3.9)
for i in range(3):
    el(c, dx, dy + dh - 0.98 - i * 0.25, dw, 0.21, "", edge="#D6CCE3")
    el(c, dx + 0.03, dy + dh - 0.96 - i * 0.25, 0.3, 0.17, "crop", fill="#EEE9F3", edge="#D6CCE3", fs=4.4)
    txt(c, dx + 0.38, dy + dh - 0.875 - i * 0.25, "place · score", fs=4.6)
el(c, dx, dy + 0.42, dw, 0.2, "Got it, thank you", fill=PURPLE, edge=PURPLE, color="white", fs=5.0)
el(c, dx, dy + 0.14, dw, 0.2, "Not there? See other places", edge=PURPLE, fs=4.4)

# search history
sx, sy, sw, sh = phone(c, 0.05, 0.2, "Search History")
el(c, sx, sy + sh - 0.22, sw / 2 - 0.02, 0.18, "Most Recent", fill="#E9DFF2", edge=PURPLE, fs=4.6)
el(c, sx + sw / 2 + 0.02, sy + sh - 0.22, sw / 2 - 0.02, 0.18, "Most Frequent", edge=PURPLE, fs=4.4)
for i in range(5):
    el(c, sx, sy + sh - 0.52 - i * 0.3, sw, 0.24, "past question · time", edge="#D6CCE3", fs=4.8)
txt(c, sx + sw / 2, sy + 0.12, "HistoryService (on device)", fs=4.7, color=MUTED, ha="center")

# enroll dialog
ex, ey, ew, eh = phone(c, 2.3, 0.2, "Enroll Dialog")
txt(c, ex + ew / 2, ey + eh - 0.12, "Add personal item", fs=5.6, ha="center", bold=True)
el(c, ex, ey + eh - 0.5, ew, 0.26, "Name, e.g.\nReading glasses", edge=PURPLE, fs=4.8)
el(c, ex, ey + eh - 0.85, ew, 0.26, "object class ▾", edge=PURPLE, fs=4.8)
el(c, ex, ey + eh - 1.2, ew, 0.26, "usual room ▾", edge=PURPLE, fs=4.8)
el(c, ex, ey + 0.3, ew / 2 - 0.03, 0.22, "Cancel", edge="#B9B2A6", fs=5.0)
el(c, ex + ew / 2 + 0.03, ey + 0.3, ew / 2 - 0.03, 0.22, "Save item", fill=PURPLE, edge=PURPLE, color="white", fs=5.0)

link(c, (1.37, 4.55), (2.3, 4.55), "saved", (1.83, 4.72))
link(c, (3.62, 4.95), (4.6, 4.95), "tile, typed or\nspoken question\n→ /query,\nthen /ask", (4.11, 5.4))
link(c, (4.6, 3.75), (3.62, 3.75), "close", (4.1, 3.6))
link(c, (2.3, 3.4), (1.2, 2.75), "History", (1.6, 2.95))
link(c, (2.96, 3.3), (2.96, 3.06), "add item", (3.12, 3.18), ha="left")
c.note(3.75, 2.1, "Track: GET /api/v1/timeline, per-item GET /query\nInterior: GET /api/v1/rooms,\n"
       "  POST /api/v1/rooms/rename\nStatus: GET /health, GET /api/v1/capture/status\n"
       "Enroll: instanceIdFor(item) → enrollItem\n  → POST /api/v1/enroll", fs=6.0, color=INK)
c.ax.text(3.75, 0.75, "Rename and enroll are unauthenticated\nwrites (FR8.1 planned).", fontsize=6.3,
          color="#C0392B", va="center", fontweight="bold",
          bbox=dict(facecolor="#F8D7DA", edgecolor="#C0392B", pad=3))
c.save("ch5-caregiver-app-flow")
