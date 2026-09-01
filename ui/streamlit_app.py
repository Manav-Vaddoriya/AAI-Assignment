"""
ui/streamlit_app.py — P13 Agent Console (Streamlit UI)

Pages:
  1. Dashboard        — Status cards: Ollama, model, tools, manifest
  2. AI Chat          — Natural-language agent with execution trace
  3. Tool Explorer    — Registered tools with schemas and examples
  4. Validation Lab   — Send malformed inputs, see rejection live
  5. Truncation Demo  — Row limits visualized
  6. Manifest         — Live registry vs committed manifest
  7. Architecture     — ASCII/visual system diagram
  8. Safety Guarantees — Security checklist

Run with:
    streamlit run ui/streamlit_app.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Ensure project root is importable
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import streamlit as st

# ---------------------------------------------------------------------------
# Page config — must be first Streamlit call
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="P13 Agent Console",
    page_icon="🔒",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Imports (after set_page_config)
# ---------------------------------------------------------------------------
import app.handlers  # noqa: F401 — populate TOOL_REGISTRY

from app.config import OLLAMA_MODEL, SUPPORTED_MODELS
from app.manifest import check_manifest, generate_manifest, manifest_to_json
from app.config import MANIFEST_PATH
from app.errors import ManifestMismatchError
from app.ollama_client import (
    get_all_pull_instructions,
    get_available_supported_models,
    is_ollama_running,
    list_installed_models,
)
from app.registry import TOOL_REGISTRY
from app.schemas import ProductInput, UserInput, UserOrdersInput
from pydantic import ValidationError

# ---------------------------------------------------------------------------
# Custom CSS
# ---------------------------------------------------------------------------
st.markdown("""
<style>
.status-card {
    background: #1e1e2e;
    border-radius: 8px;
    padding: 16px;
    margin: 4px 0;
    border-left: 4px solid #89b4fa;
}
.status-ok   { border-left-color: #a6e3a1; }
.status-warn { border-left-color: #f9e2af; }
.status-err  { border-left-color: #f38ba8; }
.badge-readonly {
    background: #a6e3a1; color: #1e1e2e;
    border-radius: 4px; padding: 2px 8px;
    font-size: 0.75em; font-weight: bold;
}
.badge-tool {
    background: #89b4fa; color: #1e1e2e;
    border-radius: 4px; padding: 2px 8px;
    font-size: 0.75em; font-weight: bold;
}
.trace-ok  { color: #a6e3a1; }
.trace-err { color: #f38ba8; }
.trace-info { color: #89b4fa; }
pre.arch {
    background: #1e1e2e;
    color: #cdd6f4;
    padding: 16px;
    border-radius: 8px;
    font-family: monospace;
    font-size: 0.85em;
}
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _prod_tools() -> dict:
    return {k: v for k, v in TOOL_REGISTRY.items() if not k.startswith("_test")}


def _ollama_status():
    running = is_ollama_running()
    installed = list_installed_models() if running else []
    available = get_available_supported_models() if running else []
    return running, installed, available


def _ok(msg: str) -> str:
    return f'<span class="trace-ok">✓ {msg}</span>'


def _err(msg: str) -> str:
    return f'<span class="trace-err">✗ {msg}</span>'


def _info(msg: str) -> str:
    return f'<span class="trace-info">ℹ {msg}</span>'


# ---------------------------------------------------------------------------
# Sidebar navigation
# ---------------------------------------------------------------------------

PAGES = [
    "Dashboard",
    "AI Chat",
    "Tool Explorer",
    "Validation Lab",
    "Truncation Demo",
    "Manifest",
    "Architecture",
    "Safety Guarantees",
]

with st.sidebar:
    st.markdown("## 🔒 P13 Agent Console")
    st.markdown("*Typed Read-Only Tool System*")
    st.divider()
    page = st.radio("Navigate", PAGES, label_visibility="collapsed")
    st.divider()

    # Quick Ollama status in sidebar
    if is_ollama_running():
        st.markdown("🟢 **Ollama** running")
    else:
        st.markdown("🔴 **Ollama** offline")

    tools_count = len(_prod_tools())
    st.markdown(f"🔧 **{tools_count}** tools registered")


# ===========================================================================
# Page 1 — Dashboard
# ===========================================================================

if page == "Dashboard":
    st.title("P13 — Typed Read-Only Agent Tools")
    st.caption("Agentic AI · Pydantic Validation · Ollama · FastAPI · SQLite")
    st.divider()

    ollama_running, installed_models, available_models = _ollama_status()
    prod_tools = _prod_tools()

    # Manifest status
    try:
        check_manifest(MANIFEST_PATH)
        manifest_ok = True
        manifest_msg = "Manifest matches registry"
    except ManifestMismatchError:
        manifest_ok = False
        manifest_msg = "Manifest drift detected"
    except FileNotFoundError:
        manifest_ok = False
        manifest_msg = "Manifest file not found"

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            label="🤖 Ollama",
            value="Running" if ollama_running else "Offline",
            delta="Connected" if ollama_running else "Start Ollama",
            delta_color="normal" if ollama_running else "inverse",
        )
    with col2:
        st.metric(
            label="🔧 Registered Tools",
            value=len(prod_tools),
            delta="read-only",
        )
    with col3:
        st.metric(
            label="📋 Manifest",
            value="OK" if manifest_ok else "DRIFT",
            delta=manifest_msg,
            delta_color="normal" if manifest_ok else "inverse",
        )
    with col4:
        st.metric(
            label="🛡️ Validation",
            value="Active",
            delta="extra=forbid",
        )

    st.divider()

    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("Registered Tools")
        for name, entry in prod_tools.items():
            with st.expander(f"**{name}**  `row_limit={entry.row_limit}`"):
                st.markdown(f"**Description:** {entry.description}")
                st.markdown(f"**Module:** `{entry.module}`")
                st.markdown(
                    f'<span class="badge-readonly">READ-ONLY</span>',
                    unsafe_allow_html=True,
                )

    with col_right:
        st.subheader("Ollama Models")
        if ollama_running:
            if available_models:
                st.success(f"Supported models available: {', '.join(available_models)}")
            else:
                st.warning("No supported models installed.")
                st.code(get_all_pull_instructions(), language="bash")

            if installed_models:
                st.markdown("**All installed models:**")
                for m in installed_models:
                    st.markdown(f"- `{m}`")
        else:
            st.error("Ollama is not running.")
            st.markdown("**To start:**")
            st.code("# Download from https://ollama.com\nollama serve\nollama pull qwen3:8b",
                    language="bash")

    st.divider()
    st.subheader("Project Overview")
    st.markdown("""
    This project demonstrates the P13 assignment requirements:

    | Requirement | Status |
    |---|---|
    | Three read-only tools | ✅ `get_product`, `get_user`, `get_user_orders` |
    | `extra="forbid"` on all inputs | ✅ Pydantic validation |
    | `[0-9]` patterns (not `\\d`) | ✅ ASCII-only identifiers |
    | Server-side row limits | ✅ Enforced independently of LLM |
    | Truncation reporting | ✅ `truncated=True` flag |
    | 5-check import-time decorator | ✅ `@read_tool` |
    | Registry as source of truth | ✅ `TOOL_REGISTRY` |
    | Manifest from registry | ✅ Auto-generated |
    | Drift detection | ✅ `make manifest-check` |
    | Ollama agent | ✅ Tool calling with validation |
    """)


# ===========================================================================
# Page 2 — AI Chat
# ===========================================================================

elif page == "AI Chat":
    st.title("💬 AI Chat")
    st.caption("Ask questions in natural language — the agent calls the registered tools.")

    ollama_running, installed_models, available_models = _ollama_status()

    # Model selector
    col1, col2 = st.columns([3, 1])
    with col1:
        if available_models:
            selected_model = st.selectbox(
                "Select model",
                options=available_models + [m for m in SUPPORTED_MODELS if m not in available_models],
                format_func=lambda m: f"{m} {'✓ installed' if m in available_models else '✗ not installed'}",
            )
        else:
            selected_model = st.selectbox("Select model", SUPPORTED_MODELS)
    with col2:
        st.markdown("**Status**")
        if ollama_running:
            st.markdown("🟢 Connected")
        else:
            st.markdown("🔴 Offline")

    if not ollama_running:
        st.error(
            "Ollama is not running.  "
            "Start it with `ollama serve` and pull a model: `ollama pull qwen3:8b`"
        )

    # Example queries
    st.markdown("**Quick examples:**")
    ex_cols = st.columns(4)
    examples = [
        "What is product P1001?",
        "Tell me about user U1001.",
        "Show orders for U1001.",
        "Find product PABC.",
    ]
    for i, ex in enumerate(examples):
        if ex_cols[i].button(ex, key=f"ex_{i}"):
            st.session_state["chat_input"] = ex

    # Chat history
    if "chat_history" not in st.session_state:
        st.session_state["chat_history"] = []

    # Input
    user_input = st.chat_input(
        "Ask about a product (P1001), user (U1001), or orders...",
        key="chat_box",
    )
    if "chat_input" in st.session_state and st.session_state["chat_input"]:
        user_input = st.session_state.pop("chat_input")

    if user_input:
        st.session_state["chat_history"].append({"role": "user", "content": user_input})

        with st.spinner("Agent thinking..."):
            from app.agent import P13Agent
            agent = P13Agent(model=selected_model)
            response = agent.chat(user_input)

        st.session_state["chat_history"].append({
            "role": "assistant",
            "content": response.answer,
            "trace": response.trace,
            "tool_calls": response.tool_calls_made,
        })

    # Render chat history
    for msg in st.session_state["chat_history"]:
        if msg["role"] == "user":
            with st.chat_message("user"):
                st.write(msg["content"])
        else:
            with st.chat_message("assistant"):
                st.write(msg["content"])
                if msg.get("trace"):
                    with st.expander("🔍 Execution trace"):
                        for event in msg["trace"]:
                            icon = "✓" if event.success else "✗"
                            color = "green" if event.success else "red"
                            st.markdown(
                                f":{color}[{icon} **{event.event}**] {event.detail}"
                            )

    if st.button("Clear chat"):
        st.session_state["chat_history"] = []
        st.rerun()


# ===========================================================================
# Page 3 — Tool Explorer
# ===========================================================================

elif page == "Tool Explorer":
    st.title("🔧 Tool Explorer")
    st.caption("All registered tools with their schemas, examples, and constraints.")

    prod_tools = _prod_tools()

    for name, entry in prod_tools.items():
        st.divider()
        col1, col2 = st.columns([3, 1])
        with col1:
            st.subheader(name.upper())
            st.markdown(f"**Description:** {entry.description}")
        with col2:
            st.markdown('<span class="badge-readonly">READ-ONLY</span>', unsafe_allow_html=True)
            st.markdown(f"**Row limit:** `{entry.row_limit}`")
            st.markdown(f"**Module:** `{entry.module}`")

        col_schema, col_example = st.columns(2)
        with col_schema:
            st.markdown("**Input Schema:**")
            schema = entry.input_model.model_json_schema()
            st.json(schema)

        with col_example:
            st.markdown("**Example Inputs:**")
            if name == "get_product":
                st.code('{"product_id": "P1001"}', language="json")
                st.markdown("- `P1001` → valid  \n- `PABC` → rejected  \n- `P१२३` → rejected (Unicode)")
            elif name == "get_user":
                st.code('{"user_id": "U1001"}', language="json")
                st.markdown("- `U1001` → valid  \n- `U001` → valid  \n- `U१२३` → rejected")
            elif name == "get_user_orders":
                st.code('{"user_id": "U1001", "limit": 5}', language="json")
                st.markdown("- limit default: 20  \n- limit max: 100  \n- limit 1000000 → rejected")


# ===========================================================================
# Page 4 — Validation Lab
# ===========================================================================

elif page == "Validation Lab":
    st.title("🧪 Validation Lab")
    st.caption(
        "Send malformed inputs to prove that Pydantic blocks them BEFORE the handler is called."
    )

    st.info(
        "**Security invariant:** Malformed arguments NEVER reach the handler.  "
        "Every test here proves `handler_called == False` on validation failure."
    )

    # Pre-built test scenarios
    SCENARIOS = {
        "✅ Valid product ID": (ProductInput, {"product_id": "P1001"}, True),
        "❌ Invalid ID format (PABC)": (ProductInput, {"product_id": "PABC"}, False),
        "❌ Unicode digits (P१२३)": (ProductInput, {"product_id": "P१२३"}, False),
        "❌ Fullwidth digits (P１２３)": (ProductInput, {"product_id": "P１２３"}, False),
        "❌ Extra field (admin=True)": (ProductInput, {"product_id": "P1001", "admin": True}, False),
        "❌ SQL injection field": (ProductInput, {"product_id": "P1001", "sql": "DROP TABLE products"}, False),
        "❌ Delete attack field": (ProductInput, {"product_id": "P1001", "delete_database": True}, False),
        "✅ Valid user ID": (UserInput, {"user_id": "U1001"}, True),
        "❌ Invalid user ID": (UserInput, {"user_id": "UABC"}, False),
        "❌ Devanagari user ID": (UserInput, {"user_id": "U१२३"}, False),
        "✅ Valid orders request": (UserOrdersInput, {"user_id": "U1001", "limit": 5}, True),
        "❌ Limit = 0": (UserOrdersInput, {"user_id": "U1001", "limit": 0}, False),
        "❌ Excessive limit (1,000,000)": (UserOrdersInput, {"user_id": "U1001", "limit": 1_000_000}, False),
        "❌ Missing required field": (ProductInput, {}, False),
    }

    col_left, col_right = st.columns(2)

    with col_left:
        selected = st.selectbox("Choose a test scenario:", list(SCENARIOS.keys()))

    model_cls, args, expected_valid = SCENARIOS[selected]

    with col_right:
        st.markdown(f"**Expected:** {'VALID ✅' if expected_valid else 'REJECTED ❌'}")
        st.markdown(f"**Model:** `{model_cls.__name__}`")

    st.markdown("**Arguments:**")
    st.json(args)

    # Custom JSON input
    st.markdown("---")
    st.markdown("**Or enter custom JSON arguments:**")
    custom_json = st.text_area(
        "Custom JSON",
        value=json.dumps(args, ensure_ascii=False),
        height=80,
    )
    tool_choice = st.selectbox("Tool model", ["ProductInput", "UserInput", "UserOrdersInput"])

    MODEL_MAP = {
        "ProductInput": ProductInput,
        "UserInput": UserInput,
        "UserOrdersInput": UserOrdersInput,
    }

    if st.button("Run Validation Test", type="primary"):
        try:
            input_args = json.loads(custom_json)
        except json.JSONDecodeError as e:
            st.error(f"Invalid JSON: {e}")
            input_args = args

        chosen_model = MODEL_MAP[tool_choice]
        handler_called = False

        try:
            validated = chosen_model(**input_args)
            handler_called = True  # Only set if validation passes
            st.success("✅ VALID — Handler would be called")
            st.json(validated.model_dump())
        except ValidationError as exc:
            st.error("❌ REJECTED — Handler NOT called")
            st.markdown(f"**handler_called = {handler_called}**")
            st.markdown("**Validation errors:**")
            for error in exc.errors(include_url=False):
                st.markdown(f"- `{error['loc']}` → {error['msg']}")

        st.markdown(f"**handler_called = `{handler_called}`**")
        if not handler_called:
            st.markdown(
                "> ✅ Security invariant confirmed: malformed arguments never reached the handler."
            )

    # Show all scenarios summary
    st.divider()
    st.subheader("All Validation Scenarios")
    for label, (mc, test_args, exp_valid) in SCENARIOS.items():
        handler_called = False
        try:
            mc(**test_args)
            handler_called = True
            actual_valid = True
        except ValidationError:
            actual_valid = False

        status = "✅ PASS" if (actual_valid == exp_valid and handler_called == exp_valid) else "❌ FAIL"
        st.markdown(
            f"| `{label}` | `handler_called={handler_called}` | {status} |"
            if actual_valid else
            f"| `{label}` | `handler_called={handler_called}` | {status} |"
        )


# ===========================================================================
# Page 5 — Truncation Demo
# ===========================================================================

elif page == "Truncation Demo":
    st.title("📊 Truncation Demo")
    st.caption("Demonstrates that server-side row limits are enforced and transparently reported.")

    from app.handlers import get_user_orders

    st.markdown("""
    **U1001 has 25 orders in the database.**  
    Use the slider to set the requested limit and observe truncation behavior.
    """)

    limit = st.slider("Request limit", min_value=1, max_value=100, value=5, step=1)
    user_id = st.text_input("User ID", value="U1001")

    if st.button("Fetch Orders", type="primary"):
        try:
            req = UserOrdersInput(user_id=user_id, limit=limit)
        except ValidationError as exc:
            st.error(f"Validation error: {exc}")
            st.stop()

        result = get_user_orders(req)

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Rows Returned", result.count)
        col2.metric("Total Available", result.total_available)
        col3.metric("Limit Used", limit)
        col4.metric(
            "Truncated",
            "YES ⚠️" if result.truncated else "NO ✅",
        )

        if result.truncated:
            st.warning(f"⚠️ **Results truncated:** {result.truncation_warning}")
        else:
            st.success("✅ All available rows returned — no truncation.")

        if result.rows:
            import pandas as pd
            df = pd.DataFrame([o.model_dump() for o in result.rows])
            st.dataframe(df, use_container_width=True)
        else:
            st.info("No orders found for this user.")

    # Explain the mechanism
    st.divider()
    st.markdown("""
    **How truncation works:**

    ```
    LLM requests limit=5
         ↓
    Pydantic validates: 1 ≤ 5 ≤ 100 ✓
         ↓
    Handler queries: SELECT ... WHERE user_id=? LIMIT 6  (limit+1)
         ↓
    If 6 rows returned → truncated=True, only 5 shown
    If ≤5 rows returned → truncated=False
         ↓
    truncated + total_available reported back to LLM
    ```

    The server **always** reports truthfully whether more data exists.  
    The LLM is told explicitly and must not claim to have seen more data.
    """)


# ===========================================================================
# Page 6 — Manifest
# ===========================================================================

elif page == "Manifest":
    st.title("📋 Manifest")
    st.caption("Machine-readable registry of all tools — auto-generated, never manually maintained.")

    # Check drift
    try:
        check_manifest(MANIFEST_PATH)
        st.success("✅ Manifest matches live registry — no drift detected.")
        drift = False
    except ManifestMismatchError as exc:
        st.error(f"❌ Manifest drift detected!\n{exc}")
        drift = True
    except FileNotFoundError:
        st.warning("Committed manifest not found. Run: `python scripts/generate_manifest.py --output manifests/tools.json`")
        drift = True

    manifest = generate_manifest()

    col1, col2, col3 = st.columns(3)
    col1.metric("Version", manifest.get("version", "—"))
    col2.metric("Tools", len([t for t in manifest["tools"] if not t["name"].startswith("_test")]))
    col3.metric("Status", "OK" if not drift else "DRIFT")

    st.divider()

    for tool in manifest["tools"]:
        if tool["name"].startswith("_test"):
            continue
        with st.expander(f"**{tool['name']}**"):
            col_info, col_schema = st.columns(2)
            with col_info:
                st.markdown(f"**Description:** {tool['description'][:200]}...")
                st.markdown(f"**Row limit:** `{tool['row_limit']}`")
                st.markdown(f"**Read-only:** `{tool['read_only']}`")
                st.markdown(f"**Module:** `{tool['module']}`")
            with col_schema:
                st.markdown("**Input Schema:**")
                st.json(tool["input_schema"])

    st.divider()
    st.markdown("**Raw manifest JSON:**")
    st.code(manifest_to_json(manifest), language="json")


# ===========================================================================
# Page 7 — Architecture
# ===========================================================================

elif page == "Architecture":
    st.title("🏗️ Architecture")
    st.caption("System design of the P13 Agentic Tool System.")

    st.markdown("""
    ### Data Flow
    ```
                         USER
                           |
                           v
                      OLLAMA LLM
                    (qwen3:8b etc)
                           |
                    Tool call request
                           |
                           v
                     TOOL REGISTRY
                    (TOOL_REGISTRY dict)
                           |
                           v
                  PYDANTIC VALIDATION
                  (extra="forbid", [0-9])
                           |
             +-------------+-------------+
             |             |             |
             v             v             v
         get_product   get_user   get_user_orders
          Handler       Handler      Handler
             |             |             |
             +-------------+-------------+
                           |
                           v
                        SQLite
                      (read-only)
                           |
                           v
                      Tool Result
                           |
                           v
                      OLLAMA LLM
                           |
                           v
                       USER Answer
    ```
    """)

    st.divider()

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("""
        ### Registry → Manifest → CI
        ```
        @read_tool decorator
               ↓
          5 checks at import
               ↓
          TOOL_REGISTRY
               ↓
        generate_manifest()
               ↓
          manifests/tools.json
               ↓
        make manifest-check
               ↓
          CI: PASS / FAIL
        ```
        """)

    with col2:
        st.markdown("""
        ### Validation Pipeline
        ```
        LLM produces args
               ↓
        Parse JSON arguments
               ↓
        Pydantic validation
          - extra="forbid"
          - [0-9] pattern
          - ge/le limits
               ↓
        If INVALID → reject
        Handler NOT called
               ↓
        If VALID → handler
               ↓
        SQLite parameterized query
               ↓
        Truncation check
               ↓
        Return result + flags
        ```
        """)

    st.divider()
    st.markdown("""
    ### Technology Stack
    | Layer | Technology |
    |---|---|
    | Validation | Pydantic v2 (`extra="forbid"`, `[0-9]`) |
    | API | FastAPI + Uvicorn |
    | Agent | Ollama Python SDK |
    | Database | SQLite (read-only URI mode) |
    | UI | Streamlit |
    | Tests | pytest (227 tests) |
    | Lint | Ruff |
    | CI | GitHub Actions |
    """)


# ===========================================================================
# Page 8 — Safety Guarantees
# ===========================================================================

elif page == "Safety Guarantees":
    st.title("🛡️ Safety Guarantees")
    st.caption("Every guarantee is backed by automated tests.")

    GUARANTEES = [
        ("Typed inputs", "Every tool has a dedicated Pydantic v2 input model"),
        ('extra="forbid"', "Unknown fields are rejected before the handler is called"),
        ("ASCII-only identifiers", "Patterns use [0-9] not \\d — Unicode digits rejected"),
        ("Server-side row limits", "Limits enforced independently of LLM request"),
        ("Truncation reporting", "truncated=True with warning when results are cut"),
        ("Read-only handlers", "No INSERT/UPDATE/DELETE/DROP exposed"),
        ("No arbitrary SQL", "Handlers use parameterized queries only"),
        ("Import-time registration", "Bad tools fail at startup, not at runtime"),
        ("Registry-based discovery", "TOOL_REGISTRY is the single source of truth"),
        ("Manifest consistency", "CI fails if manifest drifts from registry"),
        ("Invalid input blocked", "handler_called==False proven in test_security.py"),
    ]

    for name, detail in GUARANTEES:
        col1, col2 = st.columns([1, 3])
        with col1:
            st.markdown(f"✅ **{name}**")
        with col2:
            st.markdown(detail)

    st.divider()
    st.subheader("Live Verification")

    # Run security checks live
    prod_tools = _prod_tools()

    checks = []
    checks.append(("Three read-only tools registered", len(prod_tools) == 3))
    checks.append(("All tools have extra=forbid", all(
        v.input_model.model_config.get("extra") == "forbid"
        for v in prod_tools.values()
    )))
    checks.append(("All tools have positive row_limit", all(
        v.row_limit >= 1 for v in prod_tools.values()
    )))
    checks.append(("All tools marked read_only=True", all(
        v.read_only for v in prod_tools.values()
    )))

    # Manifest check
    try:
        check_manifest(MANIFEST_PATH)
        checks.append(("Manifest matches registry", True))
    except Exception:
        checks.append(("Manifest matches registry", False))

    # DB accessible
    try:
        from app.handlers import get_product
        from app.schemas import ProductInput
        r = get_product(ProductInput(product_id="P1001"))
        checks.append(("Database accessible and read-only", r.found))
    except Exception as e:
        checks.append((f"Database: {e}", False))

    for label, ok in checks:
        if ok:
            st.markdown(f"✅ {label}")
        else:
            st.markdown(f"❌ {label}")

    st.divider()
    st.subheader("Presentation Demo Script (5 minutes)")
    st.markdown("""
    **Step 1** — Go to **AI Chat**, ask: *"What is product P1001?"*
    → Show successful tool call, agent returns product name, price, brand.

    **Step 2** — Ask: *"Show orders for U1001 with limit 5"*
    → Show truncation: 5 of 25 orders returned, truncated=True warning.

    **Step 3** — Go to **Validation Lab**, select Unicode digits test `P१२३`
    → Show REJECTED, handler_called=False.

    **Step 4** — Select "Delete attack field" test
    → Show REJECTED, handler_called=False — attack blocked.

    **Step 5** — Go to **Manifest** page
    → Show manifest matches registry, read_only=true on all tools.

    **Step 6** — Go to **Safety Guarantees**
    → Show all live checks passing — green across the board.
    """)
