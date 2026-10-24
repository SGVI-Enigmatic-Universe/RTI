
from dash import Dash, html, dcc, Input, Output, State
import pandas as pd
import plotly.express as px
import re
import os

import shutil
from pathlib import Path
import plotly.graph_objects as go
import math

# =========================================================
# 1. GOOGLE SHEET CONFIGURATION
# =========================================================

# Replace these with the ID and tab GID from your Google Sheet URL.
SHEET_ID = "1IBxMoIrjr4XWwQbXCOmcFfaV-0HcJcK9cZoWLQ7OQ7g"
SHEET_GID = "855397316"

SHEET_CSV_URL = (
    f"https://docs.google.com/spreadsheets/d/{SHEET_ID}"
    f"/export?format=csv&gid={SHEET_GID}"
)

# =========================================================
# 2. DISTRICTS AND HEADER ALIASES
# =========================================================

DISTRICTS = [
    "Ariyalur",
    "Chengalpattu",
    "Chennai",
    "Coimbatore",
    "Cuddalore",
    "Dharmapuri",
    "Dindigul",
    "Erode",
    "Kallakurichi",
    "Kancheepuram",
    "Kanniyakumari",
    "Karur",
    "Krishnagiri",
    "Madurai",
    "Mayiladuthurai",
    "Nagapattinam",
    "Namakkal",
    "Nilgiris",
    "Perambalur",
    "Pudukkottai",
    "Ramanathapuram",
    "Ranipet",
    "Salem",
    "Sivaganga",
    "Tenkasi",
    "Thanjavur",
    "Theni",
    "Thoothukudi",
    "Tiruchirappalli",
    "Tirunelveli",
    "Tirupathur",
    "Tiruppur",
    "Tiruvallur",
    "Tiruvannamalai",
    "Tiruvarur",
    "Vellore",
    "Viluppuram",
    "Virudhunagar",
]

DISTRICT_ALIASES = {
    "chengalpet": "Chengalpattu",
    "kanchipuram": "Kancheepuram",
    "kanyakumari": "Kanniyakumari",
    "sivagangai": "Sivaganga",
    "villupuram": "Viluppuram",
    "viluppuram": "Viluppuram",
    "nilgiri": "Nilgiris",
}

def normalize_name(value):
    return re.sub(r"[^a-z0-9]", "", str(value).lower())


def canonical_district(column_name):
    normalized = normalize_name(column_name)

    for district in DISTRICTS:
        if normalize_name(district) == normalized:
            return district

    return DISTRICT_ALIASES.get(normalized)


# =========================================================
# 3. RTI STATUSES
# =========================================================

STATUS_COLUMNS = [
    "Full Data",
    "Partial Data",
    "Denied Data",
    "Forwarded",
    "No Reply",
]

# Dark-theme colours with intuitive meanings:
# green = full response, amber = partial, red = denied,
# blue = forwarded, slate = no reply.
STATUS_COLORS = {
    "Full Data": "#22C55E",
    "Partial Data": "#FBBF24",
    "Denied Data": "#F83838",
    "Forwarded": "#B258EB",
    "No Reply": "#94A3B8",
}

BG = "#0B1120"
PANEL = "#111C30"
PANEL_ALT = "#162238"
TEXT = "#E5EDF8"
MUTED = "#9AAAC2"
BORDER = "#263750"
ACCENT = "#91FF23"


def normalize_name(value):
    """Normalize a column heading for district matching."""
    text = str(value).strip().lower()
    text = re.sub(r"[_-]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text


def canonical_district(column_name):
    """Return the canonical district name for a matching column heading."""
    normalized = normalize_name(column_name)

    if normalized in DISTRICT_ALIASES:
        return DISTRICT_ALIASES[normalized]

    for district in DISTRICTS:
        if normalize_name(district) == normalized:
            return district

    return None


def normalize_status(value):
    """Map known response statuses; blanks are handled as No Reply separately."""
    if pd.isna(value):
        return None

    text = str(value).strip().lower()
    text = re.sub(r"[_-]+", " ", text)
    text = re.sub(r"\s+", " ", text)

    status_mapping = {
        "full data": "Full Data",
        "partial data": "Partial Data",
        "denied data": "Denied Data",
        "forwarded": "Forwarded",
    }
    return status_mapping.get(text)


# ------------------------------------------------------------
# 3. LOAD AND PROCESS GOOGLE SHEET
# ------------------------------------------------------------
def load_sheet():
    """Load Google Sheet and count status values district by district."""
    raw = pd.read_csv(SHEET_CSV_URL)
    raw.columns = [str(col).strip() for col in raw.columns]

    district_column_map = {}
    for column in raw.columns:
        district = canonical_district(column)
        if district:
            district_column_map[district] = column

    available_districts = [
        district for district in DISTRICTS
        if district in district_column_map
    ]

    missing = [
        district for district in DISTRICTS
        if district not in district_column_map
    ]
    if missing:
        print("District columns not found:", missing)

    if not available_districts:
        raise ValueError(
            "No district columns were detected. Check SHEET_GID and the "
            "district column headings in the selected worksheet tab."
        )

    records = []

    for district in available_districts:
        source_column = district_column_map[district]
        values = raw[source_column]
        normalized = values.map(normalize_status)

        # Count only truly blank cells as No Reply.
        # Unknown nonblank text is not silently treated as a no-reply.
        blank_mask = values.isna() | values.astype(str).str.strip().eq("")

        for status in STATUS_COLUMNS:
            if status == "No Reply":
                count = int(blank_mask.sum())
            else:
                count = int((normalized == status).sum())

            records.append({
                "District": district,
                "Status": status,
                "RTI Count": count,
            })

    result = pd.DataFrame(records)

    metadata_columns = [
        col for col in [
            "RID", "In-charge", "RTI Code", "Data Month",
            "RTI Type", "RTI Period",
        ]
        if col in raw.columns
    ]

    print(f"Loaded {len(raw)} spreadsheet rows.")
    print(f"Detected {len(available_districts)} districts.")
    print("Metadata columns found:", metadata_columns)

    return result, raw, available_districts


# ------------------------------------------------------------
# 4. PREPARE LOGO, FAVICON AND OPTIONAL CSS ASSETS
# ------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
ASSETS_DIR = BASE_DIR / "assets"
ASSETS_DIR.mkdir(exist_ok=True)

ROOT_LOGO = BASE_DIR / "logo.png"
ASSET_LOGO = ASSETS_DIR / "logo.png"

# The user keeps logo.png beside app.py. Copy it to Dash's assets
# directory so Dash can serve it as a favicon and watermark.
if ROOT_LOGO.exists():
    if not ASSET_LOGO.exists() or ROOT_LOGO.stat().st_mtime > ASSET_LOGO.stat().st_mtime:
        shutil.copy2(ROOT_LOGO, ASSET_LOGO)
elif ASSET_LOGO.exists():
    print("Using existing logo:", ASSET_LOGO)
else:
    print(
        "WARNING: logo.png was not found beside app.py or in the assets folder. "
        "The dashboard will run without the logo watermark/favicon."
    )

# CSS makes the watermark sit behind the dashboard and styles Dash dropdowns.
CSS_PATH = ASSETS_DIR / "custom.css"
CSS_PATH.write_text(
    """
    * { box-sizing: border-box; font-family: "Times New Roman", Times, serif !important; }
    html, body {
        margin: 0 !important; padding: 0 !important;
        min-height: 100%; min-width: 1400px !important;
        background: #0B1120 !important; background-color: #0B1120 !important;
        color: #E5EDF8 !important; overflow-x: auto !important;
    }
    #react-entry-point, #react-entry-point > div,
    #_dash-app-content, #_dash-app-content > div,
    ._dash-loading, main, section {
        background: #0B1120 !important; background-color: #0B1120 !important;
        color: #E5EDF8 !important; min-width: 1400px !important;
    }
    /* Fixed 1400px canvas: zooming changes the visible area, not the layout grid. */
    .dashboard-shell {
        width: 1400px !important; min-width: 1400px !important;
        max-width: 1400px !important; margin: 0 !important;
        overflow: visible !important;
    }
    body::before {
        content: ""; position: fixed; inset: 0; z-index: 0; pointer-events: none;
        background-image: url("/assets/logo.png"); background-repeat: no-repeat;
        background-position: center center; background-size: 520px 520px;
        opacity: 0.07;
    }
    #react-entry-point, #_dash-app-content { position: relative; z-index: 1; }
    h1, h2, h3, h4, h5, h6, p, label, span, small { color: inherit; }
    /* Legacy react-select and newer react-select dropdown classes. */
    .Select-control, .Select-menu-outer, .Select-option, .Select-value-label,
    .Select-placeholder, .VirtualizedSelectOption, .VirtualizedSelectFocusedOption,
    .Select__control, .Select__menu, .Select__option, .Select__single-value,
    .Select__placeholder, .Select__input-container, .Select__indicator,
    .Select__multi-value {
        background-color: #162238 !important; color: #E5EDF8 !important;
        border-color: #263750 !important;
    }
    .Select-menu-outer, .Select__menu { border: 1px solid #263750 !important; }
    .Select-option.is-focused, .VirtualizedSelectFocusedOption,
    .Select__option--is-focused { background-color: #263750 !important; color: #FFFFFF !important; }
    .Select__indicator-separator { background-color: #263750 !important; }
    input, textarea, select, button { font-family: "Times New Roman", Times, serif !important; }
    input, textarea, select {
        background-color: #162238 !important; color: #E5EDF8 !important;
        border-color: #263750 !important;
    }
    button:hover { filter: brightness(1.08); }
    .dash-graph, .dash-table-container { background-color: transparent !important; color: #E5EDF8 !important; }
    /* The chart is deliberately fixed-size to match the fixed dashboard canvas. */
    #status-chart, #status-chart .js-plotly-plot,
    #status-chart .plot-container, #status-chart .svg-container {
        max-width: none !important;
    }
    """,
    encoding="utf-8",
)

# Initial load
df, raw_df, AVAILABLE_DISTRICTS = load_sheet()

app = Dash(
    __name__,
    assets_folder=str(ASSETS_DIR),
    assets_url_path="assets",
    title="TN RTI Monitoring and Tracking",
    update_title="Updating TN RTI Dashboard...",
)

# Serve logo.png as the browser tab favicon when available.
app.index_string = """<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <title>{%title%}</title>
        {%favicon%}
        <link rel="icon" type="image/png" href="/assets/logo.png">
        <style>
            html, body, #react-entry-point, #react-entry-point > div,
            #_dash-app-content, #_dash-app-content > div {
                margin: 0 !important;
                min-height: 100vh !important;
                min-width: 1400px !important;
                background: #0B1120 !important;
                background-color: #0B1120 !important;
                color: #E5EDF8 !important;
            }
            body { background: #0B1120 !important; min-width: 1400px !important; overflow-x: auto !important; }
        </style>
        {%css%}
    </head>
    <body>
        {%app_entry%}
        <footer>
            {%config%}
            {%scripts%}
            {%renderer%}
        </footer>
    </body>
</html>"""


def card_style(accent):
    return {
        "backgroundColor": "rgba(17, 28, 48, 0.94)",
        "border": f"1px solid {BORDER}",
        "borderTop": f"4px solid {accent}",
        "padding": "25px 20px",
        "borderRadius": "14px",
        "boxShadow": "0 8px 24px rgba(0,0,0,0.24)",
        "flex": "none",
        "width": "100%",
        "minWidth": "0",
        "height": "150px",
        "minHeight": "150px",
        "maxHeight": "150px",
        "overflow": "hidden",
        "backdropFilter": "blur(4px)",
    }


panel_style = {
    "backgroundColor": "rgba(17, 28, 48, 0.94)",
    "border": f"1px solid {BORDER}",
    "padding": "20px",
    "borderRadius": "16px",
    "boxShadow": "0 8px 28px rgba(0,0,0,0.25)",
    "backdropFilter": "blur(4px)",
}


def district_options(districts):
    return [{"label": "All Districts", "value": "All"}] + [
        {"label": district, "value": district} for district in districts
    ]

def metadata_options(dataframe, column, all_label):
    if column not in dataframe.columns:
        return [{"label": all_label, "value": "All"}]

    values = (
        dataframe[column]
        .dropna()
        .astype(str)
        .str.strip()
    )

    unique_values = list(dict.fromkeys(
        value for value in values if value
    ))

    return (
        [{"label": all_label, "value": "All"}]
        + [{"label": value, "value": value} for value in unique_values]
    )
    
app.layout = html.Div(
    className="dashboard-shell",
    style={
        "fontFamily": '"Times New Roman", Times, serif',
        "backgroundColor": "#0B1120",
        "color": TEXT,
        "width": "1400px",
        "minWidth": "1400px",
        "maxWidth": "1400px",
        "minHeight": "100vh",
        "padding": "24px",
        "margin": "0",
        "boxSizing": "border-box",
        "position": "relative",
        "zIndex": 1,
    },
    children=[
        html.Div(
            style={
                "display": "flex",
                "alignItems": "center",
                "gap": "18px",
                "marginBottom": "8px",
                "flexWrap": "nowrap",
                "minHeight": "120px",
            },
            children=[
                html.Img(
                    src="/assets/logo.png",
                    style={
                        "height": "110px",
                        "width": "110px",
                        "minHeight": "110px",
                        "minWidth": "110px",
                        "objectFit": "cover",
                        "borderRadius": "50%",
                        "clipPath": "circle(50% at 50% 50%)",
                        "backgroundColor": "transparent",
                        "padding": "0",
                        "border": "none",
                        "boxShadow": "none",
                    },
                ) if ASSET_LOGO.exists() else html.Div(),
                html.Div([
                    html.H1(
                        "TN RTI Monitoring and Tracking",
                        style={
                            "color": "#F8FAFC",
                            "fontSize": "38px",
                            "fontWeight": "bold",
                            "letterSpacing": "0.2px",
                            "margin": "0 0 6px 0",
                        },
                    ),
                    html.P(
                        "District-wise POA Act Monitoring and Implementation Tracking System",
                        style={"color": MUTED, "fontSize": "18px", "margin": 0},
                    ),
                ]),
            ],
        ),
        dcc.Location(id="url", refresh=False),
        html.Div(
            style={
                "display": "flex",
                "gap": "12px",
                "marginTop": "18px",
                "marginBottom": "18px",
            },
            children=[
                dcc.Link(
                    "⌂  Overview",
                    href="/overview",
                    style={
                        "padding": "11px 22px",
                        "backgroundColor": "#162238",
                        "border": f"1px solid {BORDER}",
                        "borderRadius": "9px",
                        "color": TEXT,
                        "textDecoration": "none",
                        "fontWeight": "bold",
                        "fontSize": "16px",
                    },
                ),
                dcc.Link(
                    "▤  Factsheet",
                    href="/factsheet",
                    style={
                        "padding": "11px 22px",
                        "backgroundColor": "#162238",
                        "border": f"1px solid {BORDER}",
                        "borderRadius": "9px",
                        "color": TEXT,
                        "textDecoration": "none",
                        "fontWeight": "bold",
                        "fontSize": "16px",
                    },
                ),
            ],
        ),


        html.Hr(style={"borderColor": BORDER, "margin": "24px 0"}),

        html.Div(
            style={
                "display": "grid",
                "gridTemplateColumns": "1fr 1fr 1fr auto",
                "gap": "16px",
                "alignItems": "end",
                "flexWrap": "nowrap",
                "backgroundColor": "rgba(17, 28, 48, 0.92)",
                "border": f"1px solid {BORDER}",
                "padding": "18px",
                "borderRadius": "14px",
                "width": "100%",
                "boxSizing": "border-box",
            },
            children=[
                html.Div(
                    #style={"minWidth": "280px", "flex": "1 1 280px"},
                    children=[
                        html.Label(
                            "District",
                            style={
                                "color": TEXT,
                                "display": "block",
                                "fontWeight": "bold",
                                "marginBottom": "8px",
                                "fontSize": "17px",
                            },
                        ),
                        dcc.Dropdown(
                            id="district-filter",
                            options=district_options(AVAILABLE_DISTRICTS),
                            value="All",
                            clearable=False,
                            searchable=True,
                            style={
                                "color": "#0E2C56",
                                "backgroundColor": PANEL_ALT,
                                "fontSize": "16px",
                            },
                        ),
                    ],
                ),
        
        
        # Month filter
        html.Div(
            #style={"minWidth": "220px", "flex": "1 1 220px"},
            children=[
                html.Label(
                    "Month",
                    style={
                        "color": TEXT,
                        "display": "block",
                        "fontWeight": "bold",
                        "marginBottom": "8px",
                        "fontSize": "17px",
                    },
                ),
                dcc.Dropdown(
                    id="month-filter",
                    options=metadata_options(
                        raw_df, "Data Month", "All Months"
                    ),
                    value="All",
                    clearable=False,
                    searchable=True,
                    style={
                        "color": "#0E2C56",
                        "backgroundColor": PANEL_ALT,
                        "fontSize": "16px",
                    },
                ),
            ],
        ),
        
        # In-charge filter
        html.Div(
            #style={"minWidth": "220px", "flex": "1 1 220px"},
            children=[
                html.Label(
                    "In-charge",
                    style={
                        "color": TEXT,
                        "display": "block",
                        "fontWeight": "bold",
                        "marginBottom": "8px",
                        "fontSize": "17px",
                    },
                ),
                dcc.Dropdown(
                    id="incharge-filter",
                    options=metadata_options(
                        raw_df, "In-charge", "All In-charges"
                    ),
                    value="All",
                    clearable=False,
                    searchable=True,
                    style={
                        "color": "#0E2C56",
                        "backgroundColor": PANEL_ALT,
                        "fontSize": "16px",
                    },
                ),
            ],
        ),
                html.Button(
                    "↻",
                    id="refresh-button",
                    n_clicks=0,
                    style={
                        "padding": "12px 22px",
                        "background": "linear-gradient(135deg, #0284C7, #2563EB)",
                        "color": "#FFFFFF",
                        "border": "1px solid #38BDF8",
                        "borderRadius": "9px",
                        "fontSize": "17px",
                        "fontWeight": "bold",
                        "cursor": "pointer",
                        "boxShadow": "0 4px 14px rgba(37,99,235,0.25)",
                    },
                ),
            ],
        ),

        dcc.Store(id="dashboard-data"),
        html.Div(
            id="refresh-message",
            style={
                "color": MUTED,
                "marginTop": "12px",
                "marginBottom": "4px",
                "fontSize": "15px",
            },
        ),

        html.Div(
            id="summary-cards",
            style={
                "display": "grid",
                "gridTemplateColumns": "repeat(7, minmax(0, 1fr))",
                "alignItems": "stretch",
                "gap": "14px",
                "marginTop": "22px",
                "marginBottom": "24px",
                "width": "100%",
            },
        ),
        html.Div(
            id="overview-page",
            style={"display": "block"},
            children=[
                # complete existing chart panel here,
                # unchanged, including its closing parentheses.
                html.Div(
                    style=panel_style,
                    children=[
                        html.H2(
                            "All Posted RTIs Status district-wise",
                            style={"color": TEXT, "marginTop": 0, "marginLeft": 13.5, "fontSize": "25px"},
                        ),
                        html.P(
                            "Blank district cells and unknown non-blank values are not counted as a known status, instead are counted as 'No Reply'.",
                            style={"color": MUTED, "fontSize": "15px", "marginTop": "-5px", "marginLeft": "13.5px"},
                        ),
                        dcc.Graph(
                            id="status-chart",
                            config={"displaylogo": False, "responsive": False, "scrollZoom": False},
                            style={"height": "650px", "width": "1310px", "maxWidth": "none"},
                        ),
                    ],
                ),
            ],
        ),

        html.Div(
            id="factsheet-page",
            style={"display": "none"},
            children=[
                html.Div(
                    style={
                        **panel_style,
                        "marginBottom": "20px",
                    },
                    children=[
                        html.H2(
                            "RTI Factsheet",
                            style={"color": TEXT, "marginTop": 0},
                        ),
                        html.P(
                            "District-wise response analysis",
                            style={"color": MUTED},
                        ),
                    ],
                ),

                html.Div(
                    style={
                        "display": "grid",
                        "gridTemplateColumns": "1fr 1fr",
                        "gap": "20px",
                    },
                    children=[
                        # Chart 1: Sunburst
                        html.Div(
                            style=panel_style,
                            children=[
                                html.H3("RTI Response Sunburst",
                                        style={"color": TEXT}),
                                dcc.Graph(
                                    id="factsheet-sunburst",
                                    config={"displaylogo": False},
                                    style={"height": "420px"},
                                ),
                            ],
                        ),

                        # Chart 2
                        html.Div(
                            style=panel_style,
                            children=[
                                html.H3("Chart 2",
                                        style={"color": TEXT}),
                                dcc.Graph(
                                    id="factsheet-chart-2",
                                    figure=go.Figure().update_layout(
                                        template="plotly_dark",
                                        paper_bgcolor=PANEL,
                                        plot_bgcolor=PANEL,
                                        annotations=[dict(
                                            text="Coming soon",
                                            x=0.5, y=0.5,
                                            xref="paper", yref="paper",
                                            showarrow=False,
                                            font=dict(color=MUTED, size=18),
                                        )],
                                    ),
                                    config={"displaylogo": False},
                                    style={"height": "420px"},
                                ),
                            ],
                        ),

                        # Chart 3
                        html.Div(
                            style=panel_style,
                            children=[
                                html.H3("Chart 3",
                                        style={"color": TEXT}),
                                dcc.Graph(
                                    id="factsheet-chart-3",
                                    figure=go.Figure().update_layout(
                                        template="plotly_dark",
                                        paper_bgcolor=PANEL,
                                        plot_bgcolor=PANEL,
                                        annotations=[dict(
                                            text="Coming soon",
                                            x=0.5, y=0.5,
                                            xref="paper", yref="paper",
                                            showarrow=False,
                                            font=dict(color=MUTED, size=18),
                                        )],
                                    ),
                                    config={"displaylogo": False},
                                    style={"height": "420px"},
                                ),
                            ],
                        ),

                        # Chart 4
                        html.Div(
                            style=panel_style,
                            children=[
                                html.H3("Chart 4",
                                        style={"color": TEXT}),
                                dcc.Graph(
                                    id="factsheet-chart-4",
                                    figure=go.Figure().update_layout(
                                        template="plotly_dark",
                                        paper_bgcolor=PANEL,
                                        plot_bgcolor=PANEL,
                                        annotations=[dict(
                                            text="Coming soon",
                                            x=0.5, y=0.5,
                                            xref="paper", yref="paper",
                                            showarrow=False,
                                            font=dict(color=MUTED, size=18),
                                        )],
                                    ),
                                    config={"displaylogo": False},
                                    style={"height": "420px"},
                                ),
                            ],
                        ),
                    ],
                ),
            ],
        ),
        # html.Div(
        #     style={
        #         "display": "flex",
        #         "gap": "12px",
        #         "flexWrap": "wrap",
        #         "marginTop": "22px",
        #     },
        #     children=[
        #         html.Div(
        #             [
        #                 html.Span("● ", style={"color": STATUS_COLORS[s], "fontSize": "20px"}),
        #                 html.Span(s, style={"color": TEXT, "fontSize": "16px"}),
        #             ],
        #             style={
        #                 "backgroundColor": "rgba(17,28,48,0.9)",
        #                 "border": f"1px solid {BORDER}",
        #                 "borderRadius": "8px",
        #                 "padding": "9px 13px",
        #             },
        #         )
        #         for s in STATUS_COLUMNS
        #     ],
        # ),

        html.P(
            "Source: POA Tracking App  •  Blank district status are considered as 'No Reply' for the posted RTIs ",
            style={
                "color": MUTED,
                "marginTop": "22px",
                "fontSize": "14px",
                "textAlign": "center",
            },
        ),
    ],
)


# ------------------------------------------------------------
# 5. REFRESH GOOGLE SHEET DATA
# ------------------------------------------------------------

@app.callback(
    Output("overview-page", "style"),
    Output("factsheet-page", "style"),
    Input("url", "pathname"),
)
def navigate_pages(pathname):
    if pathname == "/factsheet":
        return {"display": "none"}, {"display": "block"}

    return {"display": "block"}, {"display": "none"}


@app.callback(
    Output("dashboard-data", "data"),
    Output("refresh-message", "children"),
    Output("district-filter", "options"),
    Output("month-filter", "options"),
    Output("incharge-filter", "options"),
    Input("refresh-button", "n_clicks"),
)
def refresh_sheet(n_clicks):
    global df, raw_df, AVAILABLE_DISTRICTS

    try:
        new_df, new_raw_df, new_districts = load_sheet()

        df = new_df
        raw_df = new_raw_df
        AVAILABLE_DISTRICTS = new_districts

        return (
            {
                "records": new_df.to_dict("records"),
                "raw_records": new_raw_df.fillna("").astype(str).to_dict("records"),
                "districts": new_districts,
            },
            f"✓ Successfully refreshed — {len(new_raw_df):,} spreadsheet rows loaded.",
            district_options(new_districts),
            metadata_options(new_raw_df, "Data Month", "All Months"),
            metadata_options(new_raw_df, "In-charge", "All In-charges"),
        )
    except Exception as exc:
        return (
            {
                "records": df.to_dict("records"),
                "raw_records": raw_df.fillna("").astype(str).to_dict("records"),
                "districts": AVAILABLE_DISTRICTS,
            },
            f"Refresh failed: {exc}",
            district_options(AVAILABLE_DISTRICTS),
             metadata_options(raw_df, "Data Month", "All Months"),
            metadata_options(raw_df, "In-charge", "All In-charges"),
        )


# ------------------------------------------------------------
# 6. UPDATE CHART AND SUMMARY CARDS
# ------------------------------------------------------------
@app.callback(
    Output("status-chart", "figure"),
    Output("summary-cards", "children"),
    Output("factsheet-sunburst", "figure"),
    Input("district-filter", "value"),
    Input("month-filter", "value"),
    Input("incharge-filter", "value"),
    Input("dashboard-data", "data"),
)
def update_dashboard(selected_district, selected_month, selected_incharge, dashboard_data,):
    if dashboard_data and "raw_records" in dashboard_data:
        current_raw = pd.DataFrame(dashboard_data["raw_records"])
        available = dashboard_data.get("districts", AVAILABLE_DISTRICTS)
    else:
        current_df = raw_df.copy()
        available = AVAILABLE_DISTRICTS
    # Filter by Month
    if (
        selected_month not in (None, "All")
        and "Data Month" in current_raw.columns
    ):
        current_raw = current_raw[
            current_raw["Data Month"].astype(str).str.strip()
            == selected_month
        ]

    # Filter by In-charge
    if (
        selected_incharge not in (None, "All")
        and "In-charge" in current_raw.columns
    ):
        current_raw = current_raw[
            current_raw["In-charge"].astype(str).str.strip()
            == selected_incharge
        ]

    # Recalculate status counts using the filtered spreadsheet rows
    district_column_map = {}

    for column in current_raw.columns:
        district = canonical_district(column)
        if district:
            district_column_map[district] = column

    records = []

    for district in available:
        if district not in district_column_map:
            continue

        values = current_raw[district_column_map[district]]
        normalized = values.map(normalize_status)

        blank_mask = (
            values.isna()
            | values.astype(str).str.strip().eq("")
        )

        for status in STATUS_COLUMNS:
            if status == "No Reply":
                count = int(blank_mask.sum())
            else:
                count = int((normalized == status).sum())

            records.append({
                "District": district,
                "Status": status,
                "RTI Count": count,
            })

    current_df = pd.DataFrame(
        records,
        columns=["District", "Status", "RTI Count"],
    )

    if current_df.empty:
        current_df = pd.DataFrame(columns=["District", "Status", "RTI Count"])
    # Continue with your existing district selection logic below







    if selected_district == "All" or selected_district is None:
        districts_to_show = available
        title = "District: Overall"
    elif selected_district in available:
        districts_to_show = [selected_district]
        title = f"District: {selected_district}"
    else:
        districts_to_show = available
        title = "District: Overall"

    filtered = current_df[current_df["District"].isin(districts_to_show)].copy()

    full_index = pd.MultiIndex.from_product(
        [districts_to_show, STATUS_COLUMNS],
        names=["District", "Status"],
    )
    chart_data = (
        filtered.set_index(["District", "Status"])
        .reindex(full_index, fill_value=0)
        .reset_index()
    )
    chart_data["RTI Count"] = (
        pd.to_numeric(chart_data["RTI Count"], errors="coerce").fillna(0)
    )

    fig = px.bar(
        chart_data,
        x="District",
        y="RTI Count",
        color="Status",
        barmode="stack",
        category_orders={
            "District": districts_to_show,
            "Status": STATUS_COLUMNS,
        },
        color_discrete_map=STATUS_COLORS,
        title=title,
        custom_data=["Status"],
    )

    fig.update_traces(
        marker_line_width=0,
        marker_cornerradius=12,
        hovertemplate=(
            "<b>%{x}</b><br>Status: %{fullData.name}"
            "<br>Count: %{y:,}<extra></extra>"
        ),
    )
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="#111C30",
        plot_bgcolor="#111C30",
        font=dict(family="Times New Roman", size=14, color="#E5EDF8"),
        width=1310,
        height=650,
        autosize=False,
        title=dict(
            text=title,
            font=dict(family="Times New Roman", size=20, color=TEXT),
            x=0.01, xanchor="left", y=0.99, yanchor="top",
        ),
        margin=dict(l=65, r=25, t=125, b=125),
        legend_title_text="Response Status",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.13,
            xanchor="left",
            x=0.01,
            font=dict(size=13),
        ),
        xaxis=dict(
            title="District",
            tickangle=-45,
            tickfont=dict(size=12, color=TEXT),
            title_font=dict(size=15, color=TEXT),
            gridcolor="rgba(148,163,184,0.12)",
            linecolor=BORDER,
        ),
        yaxis=dict(
            title="Number of RTI records",
            rangemode="tozero",
            tickfont=dict(size=13, color=TEXT),
            title_font=dict(size=15, color=TEXT),
            gridcolor="rgba(148,163,184,0.16)",
            linecolor=BORDER,
        ),
        hoverlabel=dict(
            bgcolor=PANEL_ALT,
            bordercolor=BORDER,
            font=dict(family="Times New Roman", size=14, color=TEXT),
        ),
    )


    
    totals = (
        chart_data.groupby("Status")["RTI Count"]
        .sum()
        .reindex(STATUS_COLUMNS, fill_value=0)
    )


    total_rtis = int(totals.sum())
    full_data = int(totals["Full Data"])
    partial_data = int(totals["Partial Data"])
    denied = int(totals["Denied Data"])
    forwarded = int(totals["Forwarded"])
    no_reply = int(totals["No Reply"])
    data_provided = full_data + partial_data

    cards_data = [
        ("Total RTIs Posted", total_rtis, ACCENT,
         "Overall district entries"),
        ("Full Data", full_data, STATUS_COLORS["Full Data"],
         "Complete information provided"),
        ("Partial Data", partial_data, STATUS_COLORS["Partial Data"],
         "Some information provided"),
        ("Denied Data", denied, STATUS_COLORS["Denied Data"],
         "Information marked as denied"),
        ("Forwarded", forwarded, STATUS_COLORS["Forwarded"],
         "RTI marked as forwarded"),
        ("No Reply", no_reply, STATUS_COLORS["No Reply"],
         "Blank district entries"),
    ]

    cards = []
    for label, value, accent, description in cards_data:
        cards.append(
            html.Div(
                [
                    html.P(
                        label,
                        style={
                            "color": MUTED,
                            "fontSize": "17px",
                            "fontWeight": "bold",
                            "margin": "0 0 10px 0",
                        },
                    ),
                    html.H2(
                        f"{value:,}",
                        style={
                            "color": accent,
                            "fontSize": "36px",
                            "margin": "0 0 8px 0",
                            "lineHeight": "1.1",
                        },
                    ),
                    html.P(
                        description,
                        style={
                            "color": MUTED,
                            "fontSize": "11px",
                            "margin": 0,
                        },
                    ),
                ],
                style={**card_style(accent), "textAlign": "center"},
            )
        )

    # Add a small additional card summarizing full + partial information.
    cards.insert(
        1,
        html.Div(
            [
                html.P(
                    "Data Provided",
                    style={
                        "color": MUTED,
                        "fontSize": "17px",
                        "fontWeight": "bold",
                        "margin": "0 0 10px 0",
                    },
                ),
                html.H2(
                    f"{data_provided:,}",
                    style={
                        "color": "#2DD4BF",
                        "fontSize": "36px",
                        "margin": "0 0 8px 0",
                        "lineHeight": "1.1",
                    },
                ),
                html.P(
                    "Full Data + Partial Data",
                    style={"color": MUTED, "fontSize": "11px", "margin": 0},
                ),
            ],
            style={**card_style("#2DD4BF"), "textAlign": "center"},
        ),
    )

    sunburst_fig = px.sunburst(
        chart_data,
        path=["District", "Status"],
        values="RTI Count",
        color="Status",
        color_discrete_map=STATUS_COLORS,
    )


    sunburst_fig.update_layout(
        template="plotly_dark",
        paper_bgcolor=PANEL,
        plot_bgcolor=PANEL,
        font=dict(
            family="Times New Roman",
            color=TEXT,
            size=13,
        ),
        margin=dict(t=25, l=10, r=10, b=10),
    )

    # Recolour only the inner District segments
    sunburst_fig.update_traces(
        marker=dict(
            colors=[
                "#010713" if parent == "" else STATUS_COLORS.get(label, "#94A3B8")
                for label, parent in zip(
                    sunburst_fig.data[0].labels,
                    sunburst_fig.data[0].parents,
                )
            ]
        ),
        hovertemplate=(
            "Status: %{label}<br>"
            "RTI Count: %{value:,}<extra></extra>"
        ),
    )
    return fig, cards, sunburst_fig


# ------------------------------------------------------------
# 7. RUN APPLICATION
# ------------------------------------------------------------
if __name__ == "__main__":
    app.run(debug=True)


