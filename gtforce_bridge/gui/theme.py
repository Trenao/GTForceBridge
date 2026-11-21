"""Tema escuro único da GUI: paleta + estilos ttk. Todas as cores vêm daqui."""
from __future__ import annotations

BG = "#0a0f17"        # fundo da janela
SIDEBAR = "#0d1420"
CARD = "#141d2b"      # fundo dos cartões (os módulos das abas usam este valor)
CARD_HI = "#1a2538"
FIELD = "#0c1420"
BORDER = "#22304a"
TEXT = "#e8edf5"
MUTED = "#8d9bb0"
ACCENT = "#f47721"
ACCENT_HI = "#ff914d"
OK = "#34d399"
BAD = "#f87171"
INFO = "#38bdf8"
TRACK = "#263449"

FONT = "Segoe UI"
MONO = "Consolas"


def pick_fonts(root):
    """Usa Segoe UI/Consolas no Windows; em outros sistemas cai para uma fonte instalada."""
    global FONT, MONO
    try:
        from tkinter import font as tkfont
        fams = set(tkfont.families(root))
    except Exception:
        return
    for cand in ("Segoe UI", "Inter", "SF Pro Text", "Helvetica Neue", "DejaVu Sans", "Arial"):
        if cand in fams:
            FONT = cand; break
    for cand in ("Consolas", "Cascadia Mono", "Menlo", "DejaVu Sans Mono", "Courier New"):
        if cand in fams:
            MONO = cand; break


def apply_theme(root, ttk):
    pick_fonts(root)
    st = ttk.Style(root)
    try:
        st.theme_use("clam")
    except Exception:
        pass
    root.configure(bg=BG)
    root.option_add("*TCombobox*Listbox.background", FIELD)
    root.option_add("*TCombobox*Listbox.foreground", TEXT)
    root.option_add("*TCombobox*Listbox.selectBackground", ACCENT)
    root.option_add("*TCombobox*Listbox.selectForeground", "#111827")
    root.option_add("*TCombobox*Listbox.font", (FONT, 10))
    root.option_add("*Menu.background", CARD)
    root.option_add("*Menu.foreground", TEXT)
    root.option_add("*Menu.activeBackground", ACCENT)
    root.option_add("*Menu.activeForeground", "#111827")
    root.option_add("*Menu.borderWidth", 0)

    st.configure(".", background=BG, foreground=TEXT, font=(FONT, 10), bordercolor=BORDER,
                 lightcolor=BORDER, darkcolor=BORDER, troughcolor=TRACK, focuscolor=BG,
                 selectbackground=ACCENT, selectforeground="#111827")
    # molduras
    st.configure("TFrame", background=BG)
    st.configure("Card.TFrame", background=CARD)
    st.configure("Side.TFrame", background=SIDEBAR)
    st.configure("Top.TFrame", background=SIDEBAR)
    # rótulos
    st.configure("TLabel", background=BG, foreground=TEXT, font=(FONT, 10))
    st.configure("Muted.TLabel", background=BG, foreground=MUTED, font=(FONT, 9))
    st.configure("Warn.TLabel", background=BG, foreground="#ffb350", font=(FONT, 9, "bold"))
    st.configure("Title.TLabel", background=BG, foreground="#f5f7fb", font=(FONT, 22, "bold"))
    st.configure("Section.TLabel", background=CARD, foreground="#f5f7fb", font=(FONT, 12, "bold"))
    st.configure("Eyebrow.TLabel", background=CARD, foreground=MUTED, font=(FONT, 8, "bold"))
    st.configure("Top.TLabel", background=SIDEBAR, foreground=TEXT, font=(FONT, 11, "bold"))
    st.configure("TopMuted.TLabel", background=SIDEBAR, foreground=MUTED, font=(FONT, 9))
    # botões
    st.configure("TButton", background=TRACK, foreground=TEXT, padding=(12, 7), font=(FONT, 9, "bold"),
                 borderwidth=0, relief="flat")
    st.map("TButton", background=[("disabled", "#18212f"), ("active", "#344761")],
           foreground=[("disabled", "#5b6779")])
    st.configure("Accent.TButton", background=ACCENT, foreground="#111827", padding=(16, 8),
                 font=(FONT, 9, "bold"), borderwidth=0)
    st.map("Accent.TButton", background=[("disabled", "#3a2a20"), ("active", ACCENT_HI)],
           foreground=[("disabled", "#7a6350")])
    # campos
    for w in ("TEntry", "TSpinbox"):
        st.configure(w, fieldbackground=FIELD, foreground=TEXT, insertcolor=TEXT, bordercolor=BORDER,
                     padding=5, arrowcolor=MUTED)
    st.configure("TCombobox", fieldbackground=FIELD, background=TRACK, foreground=TEXT, arrowcolor=TEXT,
                 bordercolor=BORDER, padding=5, selectbackground=FIELD, selectforeground=TEXT)
    st.map("TCombobox", fieldbackground=[("readonly", FIELD)], foreground=[("readonly", TEXT)],
           background=[("active", "#344761")], bordercolor=[("focus", ACCENT)])
    # opções
    for w in ("TCheckbutton", "TRadiobutton"):
        st.configure(w, background=CARD, foreground=TEXT, indicatorcolor=FIELD, indicatorbackground=FIELD,
                     font=(FONT, 10))
        st.map(w, background=[("active", CARD)], indicatorcolor=[("selected", ACCENT)],
               indicatorbackground=[("selected", ACCENT)])
    st.configure("Side.TCheckbutton", background=SIDEBAR, foreground=MUTED, font=(FONT, 9))
    st.map("Side.TCheckbutton", background=[("active", SIDEBAR)], foreground=[("active", TEXT)],
           indicatorcolor=[("selected", ACCENT)], indicatorbackground=[("selected", ACCENT)])
    # barras
    st.configure("Horizontal.TScale", background=TRACK, troughcolor=TRACK, bordercolor=TRACK,
                 lightcolor=ACCENT, darkcolor=ACCENT, sliderlength=16)
    st.configure("Horizontal.TProgressbar", troughcolor=TRACK, background=ACCENT, bordercolor=TRACK,
                 lightcolor=ACCENT, darkcolor=ACCENT, thickness=10)
    for o in ("Vertical", "Horizontal"):
        st.configure(f"{o}.TScrollbar", background=TRACK, troughcolor=FIELD, bordercolor=FIELD,
                     arrowcolor=MUTED, lightcolor=TRACK, darkcolor=TRACK, gripcount=0)
        st.map(f"{o}.TScrollbar", background=[("active", "#3b4d69")])
    st.configure("TLabelframe", background=BG, bordercolor=BORDER)
    st.configure("TLabelframe.Label", background=BG, foreground=MUTED, font=(FONT, 9, "bold"))
    st.configure("TSeparator", background=BORDER)
