from __future__ import annotations

import os
import signal
import subprocess
import time
from hmac import compare_digest
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import oracledb
import pandas as pd
import streamlit as st
from dotenv import load_dotenv


st.set_page_config(
    page_title="Oracle validation workbench",
    page_icon=":material/fact_check:",
    layout="wide",
)


@dataclass(frozen=True)
class DbConfig:
    name: str
    prefix: str
    host: str
    port: int
    service: str
    user: str
    password: str


@dataclass
class QueryResult:
    section: str
    title: str
    connection: str
    sql: str
    params: dict[str, Any]
    status: str
    note: str
    row_count: int | None
    data: pd.DataFrame | None


@dataclass(frozen=True)
class ProcessStatus:
    pid: int
    command_line: str


@dataclass(frozen=True)
class InstanceSpec:
    name: str
    service: str
    marker: str


@dataclass
class ProgressTracker:
    run_label: str
    total_steps: int
    progress_slot: Any
    message_slot: Any
    started_at: float
    completed_steps: int = 0

    def tick(self, check_title: str) -> None:
        self.completed_steps += 1
        total = max(self.total_steps, 1)
        ratio = min(self.completed_steps / total, 1.0)

        elapsed = time.time() - self.started_at
        if self.completed_steps > 0:
            remaining_steps = max(total - self.completed_steps, 0)
            eta_seconds = int((elapsed / self.completed_steps) * remaining_steps)
        else:
            eta_seconds = 0

        percent = int(ratio * 100)
        self.progress_slot.progress(percent, text=f"{self.run_label} progress: {percent}%")
        self.message_slot.caption(
            f"{self.completed_steps}/{total} checks complete. Estimated time remaining: ~{eta_seconds}s. "
            f"Current check: {check_title}"
        )

    def complete(self) -> None:
        self.progress_slot.progress(100, text=f"{self.run_label} progress: 100%")
        total_elapsed = int(time.time() - self.started_at)
        self.message_slot.success(f"{self.run_label} completed in ~{total_elapsed}s.")


@dataclass(frozen=True)
class ValidationTemplate:
    key: str
    side: str
    phase: str
    component: str
    title: str
    sql: str | None
    requires: list[str]
    notes: str = ""
    enabled: bool = True


ENV_PATH = Path(__file__).with_name(".env")
load_dotenv(dotenv_path=ENV_PATH, override=True)


PLAYBOOK_RECON_PATH = "/data/usagebrkr/st1/input/vision/recon/VISB.BLACCTSP"
PLAYBOOK_ENV_PATH = "/apps/k2view/env_config"
INSTANCE_SPECS = {
    "RBM": InstanceSpec(name="RBM", service="r2w1st011", marker="rbm"),
    "UBSR": InstanceSpec(name="UBSR", service="ub2wst011", marker="ubsr"),
}

INSTANCE_DEFAULT_PORT = "2056"

_ACTIVE_PROGRESS_TRACKER: ProgressTracker | None = None


def auth_enabled() -> bool:
    mode = (os.getenv("APP_AUTH_MODE") or "oracle").strip().lower()
    return mode in {"oracle", "app"}


def auth_mode() -> str:
    return (os.getenv("APP_AUTH_MODE") or "oracle").strip().lower()


def validate_oracle_login(username: str, password: str) -> tuple[bool, str]:
    """Validate user credentials against RBM and/or UBSR Oracle service(s)."""
    user = username.strip()
    pw = password

    if not user or not pw:
        return False, "Username and password are required."

    def unique_non_empty(values: list[str]) -> list[str]:
        items: list[str] = []
        for value in values:
            token = (value or "").strip()
            if token and token not in items:
                items.append(token)
        return items

    targets = [
        (
            "RBM",
            unique_non_empty([os.getenv("RBM_ORACLE_HOST") or "", os.getenv("ORACLE_HOST") or ""]),
            unique_non_empty([
                os.getenv("RBM_ORACLE_PORT") or "",
                INSTANCE_DEFAULT_PORT,
                os.getenv("ORACLE_PORT") or "",
            ]),
            (os.getenv("RBM_ORACLE_SERVICE") or "r2w1st011").strip(),
        ),
        (
            "UBSR",
            unique_non_empty([os.getenv("UBSR_ORACLE_HOST") or "", os.getenv("ORACLE_HOST") or ""]),
            unique_non_empty([
                os.getenv("UBSR_ORACLE_PORT") or "",
                INSTANCE_DEFAULT_PORT,
                os.getenv("ORACLE_PORT") or "",
            ]),
            (os.getenv("UBSR_ORACLE_SERVICE") or "ub2wst011").strip(),
        ),
    ]

    last_error = ""
    for side, hosts, ports, service in targets:
        if not hosts:
            last_error = f"{side}: host is missing in environment configuration."
            continue

        for host in hosts:
            for port in ports:
                try:
                    dsn = oracledb.makedsn(host=host, port=int(port), service_name=service)
                    with oracledb.connect(user=user, password=pw, dsn=dsn) as conn:
                        with conn.cursor() as cur:
                            cur.execute("SELECT 1 FROM DUAL")
                            cur.fetchone()
                    return True, f"Authenticated via {side} ({host}:{port}/{service})."
                except Exception as exc:
                    last_error = f"{side} ({host}:{port}/{service}): {exc}"

    return False, last_error or "Unable to authenticate against Oracle."


def ensure_authenticated() -> None:
    """Require app login when APP_LOGIN_USER/APP_LOGIN_PASSWORD are configured."""
    if not auth_enabled():
        return

    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if "auth_user" not in st.session_state:
        st.session_state.auth_user = ""

    if st.session_state.authenticated:
        return

    st.title("Oracle validation workbench")
    st.caption("Sign in to continue")

    with st.form("app_login", border=True):
        username = st.text_input("Oracle username")
        password = st.text_input("Oracle password", type="password")
        submitted = st.form_submit_button("Sign in", type="primary", icon=":material/login:")

    if submitted:
        if auth_mode() == "app":
            expected_user = (os.getenv("APP_LOGIN_USER") or "").strip()
            expected_password = (os.getenv("APP_LOGIN_PASSWORD") or "").strip()
            if compare_digest(username, expected_user) and compare_digest(password, expected_password):
                st.session_state.authenticated = True
                st.session_state.auth_user = username
                st.session_state.oracle_user = username
                st.session_state.oracle_password = password
                st.rerun()
            else:
                st.error("Invalid username or password.")
        else:
            ok, message = validate_oracle_login(username, password)
            if ok:
                st.session_state.authenticated = True
                st.session_state.auth_user = username
                st.session_state.oracle_user = username
                st.session_state.oracle_password = password
                st.rerun()
            else:
                st.error(f"Oracle login failed. {message}")

    st.stop()


def render_auth_header() -> None:
    if not auth_enabled():
        return

    with st.container(horizontal=True, horizontal_alignment="right"):
        st.caption(f"Signed in as {st.session_state.get('auth_user', 'user')}")
        if st.button("Logout", icon=":material/logout:"):
            st.session_state.authenticated = False
            st.session_state.auth_user = ""
            st.session_state.oracle_user = ""
            st.session_state.oracle_password = ""
            st.rerun()


# ---------------------------------------------------------------------------
# Categorised validation templates (7 categories, payments excluded)
# ---------------------------------------------------------------------------
# Category → phase mapping used by render_playbook_tab to show headings.
PLAYBOOK_CATEGORIES: dict[str, str] = {
    "1. Core Account & Customer Baseline": "Cat 1",
    "2. Cross-Reference & Translation Mapping": "Cat 2",
    "3. UBSR Recon & Migration Status": "Cat 3",
    "4. Product, Tariff & Catalog (CPI & Geneva)": "Cat 4",
    "5. Tiering & Pricing Schemes (RB_CUSTOM)": "Cat 5",
    "6. Customer Subscription & Discount Application": "Cat 6",
    "7. OBR & Cassandra Validations (Usage & Billing)": "Cat 7",
}

PLAYBOOK_TEMPLATES: list[ValidationTemplate] = [
    # ── PAYMENTS excluded note ────────────────────────────────────────────────
    ValidationTemplate(
        key="payments_excluded",
        side="RBM",
        phase="Cat 1",
        component="DT",
        title="Payments setup validations",
        sql=None,
        requires=[],
        notes="Excluded from DT scope because payments setup is not enabled in V2.",
        enabled=False,
    ),
    # ── 1. Core Account & Customer Baseline ──────────────────────────────────
    # Validate profile migration V1→V2, NBD and status correctness.
    ValidationTemplate(
        key="rbm_account",
        side="RBM",
        phase="Cat 1",
        component="Core Account & Customer Baseline",
        title="account by CUSTOMER_REF",
        sql="SELECT * FROM GENEVA_ADMIN.ACCOUNT WHERE CUSTOMER_REF IN ({customer_refs_sql})",
        requires=["customer_refs_sql"],
        notes="Verify CUSTOMER_REF exists. Check NBD (NEXT_BILL_DTM) = 01-03-2025 and STATUS = OK.",
    ),
    ValidationTemplate(
        key="rbm_accountattributes",
        side="RBM",
        phase="Cat 1",
        component="Core Account & Customer Baseline",
        title="accountattributes by ACCOUNT_NUM",
        sql="SELECT * FROM GENEVA_ADMIN.ACCOUNTATTRIBUTES WHERE ACCOUNT_NUM IN ({account_nums_sql})",
        requires=["account_nums_sql"],
        notes="Check DOMAIN_ID and cycle number attributes.",
    ),
    ValidationTemplate(
        key="rbm_customer",
        side="RBM",
        phase="Cat 1",
        component="Core Account & Customer Baseline",
        title="customer by CUSTOMER_REF",
        sql="SELECT * FROM GENEVA_ADMIN.CUSTOMER WHERE CUSTOMER_REF IN ({customer_refs_sql})",
        requires=["customer_refs_sql"],
        notes="Customer should have an entry here post-migration.",
    ),
    ValidationTemplate(
        key="rbm_customerattributes",
        side="RBM",
        phase="Cat 1",
        component="Core Account & Customer Baseline",
        title="customerattributes by CUSTOMER_REF",
        sql="SELECT * FROM GENEVA_ADMIN.CUSTOMERATTRIBUTES WHERE CUSTOMER_REF IN ({customer_refs_sql})",
        requires=["customer_refs_sql"],
    ),
    ValidationTemplate(
        key="rbm_customertype",
        side="RBM",
        phase="Cat 1",
        component="Core Account & Customer Baseline",
        title="customertype",
        sql="SELECT * FROM GENEVA_ADMIN.CUSTOMERTYPE",
        requires=[],
    ),
    ValidationTemplate(
        key="rbm_domaingroup",
        side="RBM",
        phase="Cat 1",
        component="Core Account & Customer Baseline",
        title="domaingroup",
        sql="SELECT * FROM GENEVA_ADMIN.DOMAINGROUP",
        requires=[],
    ),
    ValidationTemplate(
        key="rbm_billsummary_cat1",
        side="RBM",
        phase="Cat 1",
        component="Core Account & Customer Baseline",
        title="billsummary by ACCOUNT_NUM",
        sql="SELECT * FROM GENEVA_ADMIN.BILLSUMMARY WHERE ACCOUNT_NUM IN ({account_nums_sql}) ORDER BY BILL_SEQ DESC",
        requires=["account_nums_sql"],
        notes="Validate BILL_DTM. Current cycle FEB 30 → BILL_DTM should be last NBD (31-JAN-25). Post bilcalc: should be NEXT month NBD.",
    ),

    # ── 2. Cross-Reference & Translation Mapping (MZADMIN & DB2CDC) ──────────
    # V1 source ID → V2 target ID validation for Billing and Rating.
    ValidationTemplate(
        key="ubsr_ref_rating_map",
        side="UBSR",
        phase="Cat 2",
        component="Cross-Reference & Translation Mapping",
        title="mzadmin.ref_vis_xlt_rating_trans_map",
        sql="SELECT * FROM MZADMIN.REF_VIS_XLT_RATING_TRANS_MAP WHERE RBM_ID_VALUE IN ({rbm_ids_sql})",
        requires=["rbm_ids_sql"],
        notes="Validate V1 source RBM ID maps to correct V2 rating target.",
    ),
    ValidationTemplate(
        key="ubsr_ref_billing_map",
        side="UBSR",
        phase="Cat 2",
        component="Cross-Reference & Translation Mapping",
        title="mzadmin.ref_vis_xlt_billing_trans_map",
        sql="SELECT * FROM MZADMIN.REF_VIS_XLT_BILLING_TRANS_MAP WHERE TARGET_ID IN ({target_ids_sql})",
        requires=["target_ids_sql"],
        notes="SOURCE_ID = V1 side value. TARGET_ID = V2 value.",
    ),
    ValidationTemplate(
        key="ubsr_db2cdc_billing_map",
        side="UBSR",
        phase="Cat 2",
        component="Cross-Reference & Translation Mapping",
        title="db2cdc.ref_vis_xlt_billing_trans_map",
        sql="SELECT * FROM DB2CDC.REF_VIS_XLT_BILLING_TRANS_MAP WHERE TARGET_ID IN ({target_ids_sql})",
        requires=["target_ids_sql"],
    ),
    ValidationTemplate(
        key="ubsr_db2cdc_rating_map",
        side="UBSR",
        phase="Cat 2",
        component="Cross-Reference & Translation Mapping",
        title="db2cdc.ref_vis_xlt_rating_trans_map",
        sql="SELECT * FROM DB2CDC.REF_VIS_XLT_RATING_TRANS_MAP WHERE RBM_ID_VALUE IN ({rbm_ids_sql})",
        requires=["rbm_ids_sql"],
    ),
    ValidationTemplate(
        key="ubsr_db2cdc_billing_prod_hier",
        side="UBSR",
        phase="Cat 2",
        component="Cross-Reference & Translation Mapping",
        title="db2cdc.ref_vis_billing_prod_hier",
        sql="SELECT * FROM DB2CDC.REF_VIS_BILLING_PROD_HIER",
        requires=[],
        notes="BILLING_ID_CHLD = billing tariff ID. BILLING_ID_PRNT = V2 side value.",
    ),
    ValidationTemplate(
        key="ubsr_db2cdc_rating_prod_hier",
        side="UBSR",
        phase="Cat 2",
        component="Cross-Reference & Translation Mapping",
        title="db2cdc.ref_vis_rating_prod_hier",
        sql="SELECT * FROM DB2CDC.REF_VIS_RATING_PROD_HIER",
        requires=[],
    ),
    ValidationTemplate(
        key="ubsr_db2cdc_prc_element",
        side="UBSR",
        phase="Cat 2",
        component="Cross-Reference & Translation Mapping",
        title="db2cdc.ref_vis_svc_prod_prc_element",
        sql="SELECT * FROM DB2CDC.REF_VIS_SVC_PROD_PRC_ELEMENT WHERE SVC_PROD_ID IN ({svc_prod_ids_sql})",
        requires=["svc_prod_ids_sql"],
        notes="Price up validations.",
    ),
    ValidationTemplate(
        key="ubsr_db2cdc_prc_components",
        side="UBSR",
        phase="Cat 2",
        component="Cross-Reference & Translation Mapping",
        title="db2cdc.ref_vis_svc_prod_prc_elm_comps",
        sql="SELECT * FROM DB2CDC.REF_VIS_SVC_PROD_PRC_ELM_COMPS WHERE SVC_PROD_ID IN ({svc_prod_ids_sql})",
        requires=["svc_prod_ids_sql"],
    ),
    ValidationTemplate(
        key="ubsr_cycle_hist",
        side="UBSR",
        phase="Cat 2",
        component="Cross-Reference & Translation Mapping",
        title="mzadmin.ref_rcn_bl_cycle_config_hist",
        sql=(
            "SELECT * FROM MZADMIN.REF_RCN_BL_CYCLE_CONFIG_HIST "
            "WHERE RECON_CYCLE='{recon_cycle}' ORDER BY CREATE_DATE_TS DESC"
        ),
        requires=["recon_cycle"],
        notes="Used to derive the latest audit ID. Validate LEGACY_BILL_CYCLE_CODE, VISION2_BILL_CYCLE_CODE = 30 and TAX_GEO_CODE is populated.",
    ),

    # ── 3. UBSR Recon & Migration Status ─────────────────────────────────────
    # Validate translation and status of legacy MTNs/Accounts into V2.
    ValidationTemplate(
        key="ubsr_sub_rcn_fixes",
        side="UBSR",
        phase="Cat 3",
        component="UBSR Recon & Migration Status",
        title="ubsr.sub_rcn_fixes",
        sql=(
            "SELECT * FROM UBSR.SUB_RCN_FIXES WHERE AUDIT_ID IN ({audit_ids_sql}) "
            "AND PROCESS_TYPE='UBSRTORBM_PRODUCTS_BILLING'"
        ),
        requires=["audit_ids_sql"],
    ),
    ValidationTemplate(
        key="ubsr_recon_full_processing",
        side="UBSR",
        phase="Cat 3",
        component="UBSR Recon & Migration Status",
        title="ubsr.recon_full_processing_list",
        sql="SELECT * FROM UBSR.RECON_FULL_PROCESSING_LIST WHERE AUDIT_ID IN ({audit_ids_sql})",
        requires=["audit_ids_sql"],
    ),
    ValidationTemplate(
        key="ubsr_sub_cust_acct_mdn",
        side="UBSR",
        phase="Cat 3",
        component="UBSR Recon & Migration Status",
        title="ubsr.sub_cust_acct_mdn",
        sql="SELECT * FROM UBSR.SUB_CUST_ACCT_MDN WHERE CUST_ID_NO IN ({customer_refs_sql})",
        requires=["customer_refs_sql"],
    ),
    ValidationTemplate(
        key="ubsr_sub_ln_prim_id_mdn",
        side="UBSR",
        phase="Cat 3",
        component="UBSR Recon & Migration Status",
        title="ubsr.sub_ln_prim_id_mdn",
        sql="SELECT * FROM UBSR.SUB_LN_PRIM_ID_MDN",
        requires=[],
    ),
    ValidationTemplate(
        key="ubsr_ref_vis_ln_prim_multi",
        side="UBSR",
        phase="Cat 3",
        component="UBSR Recon & Migration Status",
        title="ubsr.ref_vis_ln_prim_multi_id",
        sql="SELECT * FROM UBSR.REF_VIS_LN_PRIM_MULTI_ID WHERE LN_OF_SVC_ID_NO_P2 IN ({mdns_sql})",
        requires=["mdns_sql"],
    ),
    ValidationTemplate(
        key="ubsr_sub_ln_svc_prod_usg_seg_ba",
        side="UBSR",
        phase="Cat 3",
        component="UBSR Recon & Migration Status",
        title="ubsr.sub_ln_svc_prod_usg_seg_ba",
        sql=(
            "SELECT * FROM UBSR.SUB_LN_SVC_PROD_USG_SEG_BA "
            "WHERE LN_OF_SVC_ID_NO_P2 IN ({mdns_sql}) AND SVC_PROD_ID IN ({svc_prod_ids_sql})"
        ),
        requires=["mdns_sql", "svc_prod_ids_sql"],
    ),
    ValidationTemplate(
        key="ubsr_sub_ln_of_svc_cust_ba",
        side="UBSR",
        phase="Cat 3",
        component="UBSR Recon & Migration Status",
        title="ubsr.sub_ln_of_svc_cust_ba",
        sql="SELECT * FROM UBSR.SUB_LN_OF_SVC_CUST_BA WHERE CUST_ID_NO IN ({customer_refs_sql})",
        requires=["customer_refs_sql"],
    ),
    ValidationTemplate(
        key="ubsr_eoc_cycle_tracking",
        side="UBSR",
        phase="Cat 3",
        component="UBSR Recon & Migration Status",
        title="ubsr.eoc_cycle_tracking",
        sql=(
            "SELECT * FROM UBSR.EOC_CYCLE_TRACKING WHERE CYCLE_MONTH={cycle_month} "
            "AND BL_CYC_NO={bl_cyc_no} AND PROC_TYPE='PROD'"
        ),
        requires=["cycle_month", "bl_cyc_no"],
        notes="ACCOUNT_STATUS should be REPORT_AGGREGATION_DONE.",
    ),
    ValidationTemplate(
        key="ubsr_eoc_cycle_summary",
        side="UBSR",
        phase="Cat 3",
        component="UBSR Recon & Migration Status",
        title="ubsr.eoc_cycle_summary",
        sql=(
            "SELECT * FROM UBSR.EOC_CYCLE_SUMMARY WHERE CYCLE_MONTH={cycle_month} "
            "AND BL_CYC_NO={bl_cyc_no} AND PROC_TYPE='PROD'"
        ),
        requires=["cycle_month", "bl_cyc_no"],
        notes="ACCOUNT_STATUS should be FINAL.",
    ),
    ValidationTemplate(
        key="ubsr_sub_xlt_bl_rbm_billing",
        side="UBSR",
        phase="Cat 3",
        component="UBSR Recon & Migration Status",
        title="ubsr.sub_xlt_bl_rbm_billing",
        sql=(
            "SELECT * FROM UBSR.SUB_XLT_BL_RBM_BILLING WHERE CUST_ID_NO IN ({customer_refs_sql}) "
            "AND RBM_ID_VALUE IN ({rbm_ids_sql}) AND MDN IN ({mdns_sql})"
        ),
        requires=["customer_refs_sql", "rbm_ids_sql", "mdns_sql"],
        notes="Billing-related data. Check RBM SEQ. Can also verify MDN disconnect.",
    ),
    ValidationTemplate(
        key="ubsr_sub_xlt_bl_rbm",
        side="UBSR",
        phase="Cat 3",
        component="UBSR Recon & Migration Status",
        title="ubsr.sub_xlt_bl_rbm",
        sql=(
            "SELECT * FROM UBSR.SUB_XLT_BL_RBM WHERE CUST_ID_NO IN ({customer_refs_sql}) "
            "AND RBM_ID_VALUE IN ({rbm_ids_sql}) AND MDN IN ({mdns_sql})"
        ),
        requires=["customer_refs_sql", "rbm_ids_sql", "mdns_sql"],
        notes="Rating and usage posting validation.",
    ),
    ValidationTemplate(
        key="ubsr_reed_recon",
        side="UBSR",
        phase="Cat 3",
        component="UBSR Recon & Migration Status",
        title="reed.reed_recon",
        sql="SELECT * FROM REED.REED_RECON WHERE CUST_ID_NO IN ({customer_refs_sql})",
        requires=["customer_refs_sql"],
        notes="Verify errors in recon.",
    ),
    ValidationTemplate(
        key="ubsr_conv_imdt_bl_acct",
        side="UBSR",
        phase="Cat 3",
        component="UBSR Recon & Migration Status",
        title="conv_imdt.bl_acct_cust_mtn",
        sql="SELECT * FROM CONV_IMDT.BL_ACCT_CUST_MTN WHERE CUST_ID_NO IN ({customer_refs_sql})",
        requires=["customer_refs_sql"],
    ),

    # ── 4. Product, Tariff & Catalog (CPI & Geneva) ───────────────────────────
    # Post-CPI conversion and super compare validation for Plans, MTNs, SPOs, SFOs.
    ValidationTemplate(
        key="rbm_product",
        side="RBM",
        phase="Cat 4",
        component="Product, Tariff & Catalog (CPI & Geneva)",
        title="product by PRODUCT_ID",
        sql="SELECT * FROM GENEVA_ADMIN.PRODUCT WHERE PRODUCT_ID IN ({product_ids_sql})",
        requires=["product_ids_sql"],
        notes="CPI check. Validate product definition after CPI conversion.",
    ),
    ValidationTemplate(
        key="rbm_vzfincompdtls",
        side="RBM",
        phase="Cat 4",
        component="Product, Tariff & Catalog (CPI & Geneva)",
        title="vzfincompdtls latest catalogue",
        sql=(
            "SELECT * FROM RB_CUSTOM.VZFINCOMPDTLS "
            "WHERE PRODUCT_ID IN ({product_ids_sql}) "
            "AND CATALOGUE_CHANGE_ID=(SELECT MAX(CATALOGUE_CHANGE_ID) FROM GENEVA_ADMIN.CATALOGUECHANGE)"
        ),
        requires=["product_ids_sql"],
    ),
    ValidationTemplate(
        key="rbm_productfamily",
        side="RBM",
        phase="Cat 4",
        component="Product, Tariff & Catalog (CPI & Geneva)",
        title="geneva_admin.productfamily",
        sql="SELECT * FROM GENEVA_ADMIN.PRODUCTFAMILY",
        requires=[],
    ),
    ValidationTemplate(
        key="rbm_conv_idb_product_instance",
        side="RBM",
        phase="Cat 4",
        component="Product, Tariff & Catalog (CPI & Geneva)",
        title="conv_imdt.idb_product_instance",
        sql="SELECT * FROM CONV_IMDT.IDB_PRODUCT_INSTANCE",
        requires=[],
        notes="Post DT check.",
    ),
    ValidationTemplate(
        key="rbm_tariffelement",
        side="RBM",
        phase="Cat 4",
        component="Product, Tariff & Catalog (CPI & Geneva)",
        title="tariffelement by PRODUCT_ID",
        sql="SELECT * FROM GENEVA_ADMIN.TARIFFELEMENT WHERE PRODUCT_ID IN ({product_ids_sql})",
        requires=["product_ids_sql"],
    ),
    ValidationTemplate(
        key="rbm_tariffelementband",
        side="RBM",
        phase="Cat 4",
        component="Product, Tariff & Catalog (CPI & Geneva)",
        title="tariffelementband latest catalogue",
        sql=(
            "SELECT * FROM GENEVA_ADMIN.TARIFFELEMENTBAND "
            "WHERE PRODUCT_ID IN ({product_ids_sql}) "
            "AND CATALOGUE_CHANGE_ID=(SELECT MAX(CATALOGUE_CHANGE_ID) FROM GENEVA_ADMIN.CATALOGUECHANGE)"
        ),
        requires=["product_ids_sql"],
    ),
    ValidationTemplate(
        key="rbm_tariffelementattrdetails",
        side="RBM",
        phase="Cat 4",
        component="Product, Tariff & Catalog (CPI & Geneva)",
        title="tariffelementattrdetails BOMPID",
        sql=(
            "SELECT * FROM GENEVA_ADMIN.TARIFFELEMENTATTRDETAILS "
            "WHERE PRODUCT_ID IN ({product_ids_sql}) AND ONE_OFF_ATTR_VALUE='BOMPID' "
            "AND CATALOGUE_CHANGE_ID=(SELECT MAX(CATALOGUE_CHANGE_ID) FROM GENEVA_ADMIN.CATALOGUECHANGE)"
        ),
        requires=["product_ids_sql"],
    ),
    ValidationTemplate(
        key="rbm_productpriceattribute",
        side="RBM",
        phase="Cat 4",
        component="Product, Tariff & Catalog (CPI & Geneva)",
        title="productpriceattribute",
        sql="SELECT * FROM GENEVA_ADMIN.PRODUCTPRICEATTRIBUTE",
        requires=[],
        notes="CPI check.",
    ),
    ValidationTemplate(
        key="rbm_ratingcatalogue",
        side="RBM",
        phase="Cat 4",
        component="Product, Tariff & Catalog (CPI & Geneva)",
        title="ratingcatalogue",
        sql="SELECT * FROM GENEVA_ADMIN.RATINGCATALOGUE ORDER BY RATING_CATALOGUE_ID DESC",
        requires=[],
    ),
    ValidationTemplate(
        key="rbm_cataloguechange",
        side="RBM",
        phase="Cat 4",
        component="Product, Tariff & Catalog (CPI & Geneva)",
        title="cataloguechange",
        sql="SELECT * FROM GENEVA_ADMIN.CATALOGUECHANGE ORDER BY CATALOGUE_CHANGE_ID DESC",
        requires=[],
    ),
    ValidationTemplate(
        key="rbm_conv_ln_price_guarantee",
        side="RBM",
        phase="Cat 4",
        component="Product, Tariff & Catalog (CPI & Geneva)",
        title="conv_imdt.ln_price_guarantee by LN_OF_SVC_ID_NO_P2",
        sql="SELECT * FROM CONV_IMDT.LN_PRICE_GUARANTEE WHERE LN_OF_SVC_ID_NO_P2 IN ({mdns_sql})",
        requires=["mdns_sql"],
        notes="Post DT check.",
    ),

    # ── 5. Tiering & Pricing Schemes (RB_CUSTOM) ─────────────────────────────
    # Price-ups, Price Lock, and Tier Schemes.
    ValidationTemplate(
        key="rbm_vztierschemepriceinfo",
        side="RBM",
        phase="Cat 5",
        component="Tiering & Pricing Schemes (RB_CUSTOM)",
        title="rb_custom.vztierschemepriceinfo",
        sql="SELECT * FROM RB_CUSTOM.VZTIERSCHEMEPRICEINFO WHERE TIER_SCHEME_NO IN ({tier_scheme_ids_sql})",
        requires=["tier_scheme_ids_sql"],
        notes="CPI: validate tier scheme and group ID.",
    ),
    ValidationTemplate(
        key="rbm_vztierschemegrouptier",
        side="RBM",
        phase="Cat 5",
        component="Tiering & Pricing Schemes (RB_CUSTOM)",
        title="rb_custom.vztierschemegrouptier",
        sql=(
            "SELECT * FROM RB_CUSTOM.VZTIERSCHEMEGROUPTIER "
            "WHERE TIER_SCHEME_GROUP_ID IN ({tier_scheme_group_ids_sql}) ORDER BY PRIORITY_NO"
        ),
        requires=["tier_scheme_group_ids_sql"],
        notes="CPI: tier group definitions.",
    ),
    ValidationTemplate(
        key="rbm_vztierschemetierfincomps",
        side="RBM",
        phase="Cat 5",
        component="Tiering & Pricing Schemes (RB_CUSTOM)",
        title="rb_custom.vztierschemetierfincomps",
        sql="SELECT * FROM RB_CUSTOM.VZTIERSCHEMETIERFINCOMPS",
        requires=[],
    ),
    ValidationTemplate(
        key="rbm_vztierschemepricecriteria",
        side="RBM",
        phase="Cat 5",
        component="Tiering & Pricing Schemes (RB_CUSTOM)",
        title="rb_custom.vztierschemepricecriteria",
        sql="SELECT * FROM RB_CUSTOM.VZTIERSCHEMEPRICECRITERIA",
        requires=[],
    ),
    ValidationTemplate(
        key="rbm_vzeventsourcestatus",
        side="RBM",
        phase="Cat 5",
        component="Tiering & Pricing Schemes (RB_CUSTOM)",
        title="rb_custom.vzeventsourcestatus",
        sql="SELECT * FROM RB_CUSTOM.VZEVENTSOURCESTATUS WHERE ACCOUNT_NUM IN ({account_nums_sql})",
        requires=["account_nums_sql"],
        notes="Pre bilcalc check. Event source status per account.",
    ),
    ValidationTemplate(
        key="rbm_custeventsource",
        side="RBM",
        phase="Cat 5",
        component="Tiering & Pricing Schemes (RB_CUSTOM)",
        title="custeventsource by CUSTOMER_REF",
        sql="SELECT * FROM GENEVA_ADMIN.CUSTEVENTSOURCE WHERE CUSTOMER_REF IN ({customer_refs_sql})",
        requires=["customer_refs_sql"],
    ),
    ValidationTemplate(
        key="rbm_vzmvrefreshlist",
        side="RBM",
        phase="Cat 5",
        component="Tiering & Pricing Schemes (RB_CUSTOM)",
        title="rb_custom.vzw_mvrefreshlist",
        sql="SELECT * FROM RB_CUSTOM.VZW_MVREFRESHLIST",
        requires=[],
    ),

    # ── 6. Customer Subscription & Discount Application ───────────────────────
    # Products and discounts attached to customer post-migration.
    ValidationTemplate(
        key="rbm_custhasproduct",
        side="RBM",
        phase="Cat 6",
        component="Customer Subscription & Discount Application",
        title="custhasproduct by CUSTOMER_REF",
        sql="SELECT * FROM GENEVA_ADMIN.CUSTHASPRODUCT WHERE CUSTOMER_REF IN ({customer_refs_sql})",
        requires=["customer_refs_sql"],
        notes="Validate product alignment with migrated customer.",
    ),
    ValidationTemplate(
        key="rbm_custproductstatus",
        side="RBM",
        phase="Cat 6",
        component="Customer Subscription & Discount Application",
        title="custproductstatus",
        sql="SELECT * FROM GENEVA_ADMIN.CUSTPRODUCTSTATUS WHERE CUSTOMER_REF IN ({customer_refs_sql})",
        requires=["customer_refs_sql"],
    ),
    ValidationTemplate(
        key="rbm_custproductattrdetails",
        side="RBM",
        phase="Cat 6",
        component="Customer Subscription & Discount Application",
        title="custproductattrdetails",
        sql="SELECT * FROM GENEVA_ADMIN.CUSTPRODUCTATTRDETAILS WHERE CUSTOMER_REF IN ({customer_refs_sql})",
        requires=["customer_refs_sql"],
        notes="Check attribute 30 and 31. If processed in BilCalc it should be in CPAD table.",
    ),
    ValidationTemplate(
        key="rbm_custproductdetails",
        side="RBM",
        phase="Cat 6",
        component="Customer Subscription & Discount Application",
        title="custproductdetails",
        sql="SELECT * FROM GENEVA_ADMIN.CUSTPRODUCTDETAILS WHERE CUSTOMER_REF IN ({customer_refs_sql})",
        requires=["customer_refs_sql"],
    ),
    ValidationTemplate(
        key="rbm_billsummary_cat6",
        side="RBM",
        phase="Cat 6",
        component="Customer Subscription & Discount Application",
        title="billsummary",
        sql="SELECT * FROM GENEVA_ADMIN.BILLSUMMARY WHERE ACCOUNT_NUM IN ({account_nums_sql}) ORDER BY BILL_SEQ DESC",
        requires=["account_nums_sql"],
    ),
    ValidationTemplate(
        key="rbm_billproductcharge",
        side="RBM",
        phase="Cat 6",
        component="Customer Subscription & Discount Application",
        title="billproductcharge",
        sql="SELECT * FROM GENEVA_ADMIN.BILLPRODUCTCHARGE WHERE ACCOUNT_NUM IN ({account_nums_sql})",
        requires=["account_nums_sql"],
    ),
    ValidationTemplate(
        key="rbm_acchasonetimecharge",
        side="RBM",
        phase="Cat 6",
        component="Customer Subscription & Discount Application",
        title="acchasonetimecharge",
        sql="SELECT * FROM GENEVA_ADMIN.ACCHASONETIMECHARGE WHERE ACCOUNT_NUM IN ({account_nums_sql})",
        requires=["account_nums_sql"],
        notes="OTC_ID as per HLD.",
    ),
    ValidationTemplate(
        key="rbm_custproddiscountdetails",
        side="RBM",
        phase="Cat 6",
        component="Customer Subscription & Discount Application",
        title="custproddiscountdetails",
        sql="SELECT * FROM GENEVA_ADMIN.CUSTPRODDISCOUNTDETAILS WHERE CUSTOMER_REF IN ({customer_refs_sql})",
        requires=["customer_refs_sql"],
        notes="Verify before and after discount buckets.",
    ),
    ValidationTemplate(
        key="rbm_custprodratingdiscount",
        side="RBM",
        phase="Cat 6",
        component="Customer Subscription & Discount Application",
        title="custprodratingdiscount",
        sql="SELECT * FROM GENEVA_ADMIN.CUSTPRODRATINGDISCOUNT WHERE CUSTOMER_REF IN ({customer_refs_sql})",
        requires=["customer_refs_sql"],
    ),
    ValidationTemplate(
        key="rbm_custproductdiscountusage",
        side="RBM",
        phase="Cat 6",
        component="Customer Subscription & Discount Application",
        title="custproductdiscountusage",
        sql="SELECT * FROM GENEVA_ADMIN.CUSTPRODUCTDISCOUNTUSAGE WHERE CUSTOMER_REF IN ({customer_refs_sql})",
        requires=["customer_refs_sql"],
    ),
    ValidationTemplate(
        key="rbm_tariffelementdiscount",
        side="RBM",
        phase="Cat 6",
        component="Customer Subscription & Discount Application",
        title="tariffelementdiscount",
        sql=(
            "SELECT * FROM GENEVA_ADMIN.TARIFFELEMENTDISCOUNT "
            "WHERE PRODUCT_ID IN ({product_ids_sql})"
        ),
        requires=["product_ids_sql"],
    ),
    ValidationTemplate(
        key="rbm_eventdiscount",
        side="RBM",
        phase="Cat 6",
        component="Customer Subscription & Discount Application",
        title="eventdiscount",
        sql="SELECT * FROM GENEVA_ADMIN.EVENTDISCOUNT",
        requires=[],
    ),
    ValidationTemplate(
        key="rbm_eventdiscountstep",
        side="RBM",
        phase="Cat 6",
        component="Customer Subscription & Discount Application",
        title="eventdiscountstep",
        sql="SELECT * FROM GENEVA_ADMIN.EVENTDISCOUNTSTEP",
        requires=[],
    ),

    # ── 7. OBR & Cassandra Validations (Usage & Billing Postings) ────────────
    # Validates rating, usage postings, and invoice generation.
    ValidationTemplate(
        key="rbm_usttaxtransactions",
        side="RBM",
        phase="Cat 7",
        component="OBR & Cassandra Validations",
        title="usttaxtransactions",
        sql="SELECT * FROM GENEVA_ADMIN.USTTAXTRANSACTIONS",
        requires=[],
        notes="GMF Cassandra tax transaction.",
    ),
    ValidationTemplate(
        key="rbm_usttaxdetails",
        side="RBM",
        phase="Cat 7",
        component="OBR & Cassandra Validations",
        title="usttaxdetails",
        sql="SELECT * FROM GENEVA_ADMIN.USTTAXDETAILS",
        requires=[],
        notes="GMF Cassandra tax detail.",
    ),
    ValidationTemplate(
        key="rbm_costedevent",
        side="RBM",
        phase="Cat 7",
        component="OBR & Cassandra Validations",
        title="costedevent_* usage postings",
        sql="SELECT * FROM GENEVA_ADMIN.COSTEDEVENT_250216000 WHERE CUSTOMER_REF IN ({customer_refs_sql})",
        requires=["customer_refs_sql"],
        notes="Replace table suffix with actual event partition table name.",
    ),
    ValidationTemplate(
        key="rbm_obr_automation_log",
        side="RBM",
        phase="Cat 7",
        component="OBR & Cassandra Validations",
        title="obr_flow.obr_automation_log_sumry",
        sql="SELECT * FROM OBR_FLOW.OBR_AUTOMATION_LOG_SUMRY",
        requires=[],
    ),
    ValidationTemplate(
        key="rbm_obr_bill_product_info",
        side="RBM",
        phase="Cat 7",
        component="OBR & Cassandra Validations",
        title="obr_bill.bill_product_info",
        sql="SELECT * FROM OBR_BILL.BILL_PRODUCT_INFO WHERE ACCOUNT_NUM IN ({account_nums_sql})",
        requires=["account_nums_sql"],
    ),
    ValidationTemplate(
        key="rbm_obr_bill_acct_mdn",
        side="RBM",
        phase="Cat 7",
        component="OBR & Cassandra Validations",
        title="obr_bill.bill_acct_mdn_master",
        sql="SELECT * FROM OBR_BILL.BILL_ACCT_MDN_MASTER WHERE ACCOUNT_NUM IN ({account_nums_sql})",
        requires=["account_nums_sql"],
    ),
    ValidationTemplate(
        key="rbm_obr_inbd_account_details",
        side="RBM",
        phase="Cat 7",
        component="OBR & Cassandra Validations",
        title="obr_inbd.account_details",
        sql="SELECT * FROM OBR_INBD.ACCOUNT_DETAILS WHERE ACCOUNT_NUM IN ({account_nums_sql})",
        requires=["account_nums_sql"],
    ),
    ValidationTemplate(
        key="rbm_mtnlu1_bill_acct_mdn",
        side="RBM",
        phase="Cat 7",
        component="OBR & Cassandra Validations",
        title="mtnlu1.bill_acct_mdn_master (Fabric)",
        sql="SELECT * FROM MTNLU1.BILL_ACCT_MDN_MASTER WHERE ACCOUNT_NUM IN ({account_nums_sql})",
        requires=["account_nums_sql"],
    ),
    ValidationTemplate(
        key="rbm_mtnlu1_ln_prim_multi",
        side="RBM",
        phase="Cat 7",
        component="OBR & Cassandra Validations",
        title="mtnlu1.ln_prim_multi_id (Fabric)",
        sql="SELECT * FROM MTNLU1.LN_PRIM_MULTI_ID WHERE MDN IN ({mdns_sql})",
        requires=["mdns_sql"],
    ),
    ValidationTemplate(
        key="rbm_mtnlu1_proddet",
        side="RBM",
        phase="Cat 7",
        component="OBR & Cassandra Validations",
        title="mtnlu1.proddet (Fabric)",
        sql="SELECT * FROM MTNLU1.PRODDET",
        requires=[],
    ),
    ValidationTemplate(
        key="rbm_acclu1_proddet",
        side="RBM",
        phase="Cat 7",
        component="OBR & Cassandra Validations",
        title="acclu1.proddet (Fabric)",
        sql="SELECT * FROM ACCLU1.PRODDET WHERE ACCOUNT_NUM IN ({account_nums_sql})",
        requires=["account_nums_sql"],
    ),
]


def parse_tokens(raw: str) -> list[str]:
    tokens = [part.strip() for part in raw.replace("\n", ",").split(",")]
    return [token for token in tokens if token]


def parse_int_tokens(raw: str) -> list[int]:
    values: list[int] = []
    for token in parse_tokens(raw):
        if token.lstrip("-").isdigit():
            values.append(int(token))
    return values


def to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")


def env_value(prefix: str, name: str) -> str:
    prefixed = f"{prefix}_{name}" if prefix else name
    return (os.getenv(prefixed) or os.getenv(name) or "").strip()


def load_db_config(prefix: str, label: str) -> tuple[DbConfig | None, list[str]]:
    instance_spec = INSTANCE_SPECS.get(label.upper())

    prefixed = lambda key: (os.getenv(f"{prefix}_{key}") or "").strip() if prefix else ""
    generic = lambda key: (os.getenv(key) or "").strip()

    # Host and user can safely inherit from generic values.
    host = prefixed("ORACLE_HOST") or generic("ORACLE_HOST")
    user = prefixed("ORACLE_USER") or generic("ORACLE_USER")

    # Service and port should prefer instance-specific values to avoid cross-wiring RBM/UBSR.
    port_raw = prefixed("ORACLE_PORT") or INSTANCE_DEFAULT_PORT or generic("ORACLE_PORT")
    service = prefixed("ORACLE_SERVICE") or (instance_spec.service if instance_spec else "") or generic("ORACLE_SERVICE")

    password = prefixed("ORACLE_PASSWORD") or generic("ORACLE_PASSWORD")

    # Use per-session Oracle credentials if the user authenticated via Oracle login.
    session_user = (st.session_state.get("oracle_user") or "").strip() if "oracle_user" in st.session_state else ""
    session_password = (st.session_state.get("oracle_password") or "") if "oracle_password" in st.session_state else ""
    if session_user:
        user = session_user
    if session_password:
        password = session_password

    # Secondary password fallback for launch environments that use ORACLE_RBM_PASSWORD / ORACLE_UBSR_PASSWORD.
    if not password:
        if label.upper() == "RBM":
            password = (os.getenv("ORACLE_RBM_PASSWORD") or "").strip()
        elif label.upper() == "UBSR":
            password = (os.getenv("ORACLE_UBSR_PASSWORD") or "").strip()

    missing = [
        name
        for name, value in {
            f"{prefix}_ORACLE_HOST": host,
            f"{prefix}_ORACLE_SERVICE": service,
            f"{prefix}_ORACLE_USER": user,
            f"{prefix}_ORACLE_PASSWORD": password,
        }.items()
        if not value
    ]

    if missing:
        return None, missing

    return (
        DbConfig(
            name=label,
            prefix=prefix,
            host=host,
            port=int(port_raw),
            service=service,
            user=user,
            password=password,
        ),
        [],
    )


@st.cache_resource(show_spinner=False)
def get_pool(host: str, port: int, service: str, user: str, password: str) -> oracledb.ConnectionPool:
    dsn = oracledb.makedsn(host=host, port=port, service_name=service)
    return oracledb.create_pool(user=user, password=password, dsn=dsn, min=1, max=6, increment=1)


def run_query(config: DbConfig, sql: str, params: dict[str, Any] | None = None) -> pd.DataFrame:
    pool = get_pool(config.host, config.port, config.service, config.user, config.password)
    with pool.acquire() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params or {})
            rows = cur.fetchall()
            columns = [desc[0] for desc in cur.description] if cur.description else []
    return pd.DataFrame(rows, columns=columns)


def build_in_clause(values: list[Any], prefix: str, params: dict[str, Any]) -> str:
    placeholders: list[str] = []
    for idx, value in enumerate(values):
        key = f"{prefix}{idx}"
        params[key] = value
        placeholders.append(f":{key}")
    return ", ".join(placeholders)


def build_in_filter(column: str, values: list[Any], prefix: str, params: dict[str, Any]) -> str | None:
    if not values:
        return None
    return f"{column} IN ({build_in_clause(values, prefix, params)})"


def first_column_match(df: pd.DataFrame, candidates: list[str]) -> str | None:
    normalized = {str(col).upper(): str(col) for col in df.columns}
    for candidate in candidates:
        match = normalized.get(candidate.upper())
        if match:
            return match
    return None


def dataframe_values(df: pd.DataFrame, candidates: list[str]) -> list[Any]:
    column = first_column_match(df, candidates)
    if not column:
        return []

    seen: list[Any] = []
    for value in df[column].dropna().tolist():
        if value not in seen:
            seen.append(value)
    return seen


def execute_validation(
    results: list[QueryResult],
    config: DbConfig,
    section: str,
    title: str,
    sql: str | None,
    params: dict[str, Any] | None,
    note: str = "",
) -> pd.DataFrame | None:
    global _ACTIVE_PROGRESS_TRACKER

    if not sql:
        results.append(
            QueryResult(
                section=section,
                title=title,
                connection=config.name,
                sql="",
                params=params or {},
                status="SKIPPED",
                note=note or "Missing required input",
                row_count=None,
                data=None,
            )
        )
        if _ACTIVE_PROGRESS_TRACKER is not None:
            _ACTIVE_PROGRESS_TRACKER.tick(title)
        return None

    try:
        df = run_query(config, sql, params)
        results.append(
            QueryResult(
                section=section,
                title=title,
                connection=config.name,
                sql=sql,
                params=params or {},
                status="PASS" if not df.empty else "NO_DATA",
                note=note,
                row_count=len(df.index),
                data=df,
            )
        )
        if _ACTIVE_PROGRESS_TRACKER is not None:
            _ACTIVE_PROGRESS_TRACKER.tick(title)
        return df
    except Exception as exc:
        results.append(
            QueryResult(
                section=section,
                title=title,
                connection=config.name,
                sql=sql or "",
                params=params or {},
                status="ERROR",
                note=str(exc),
                row_count=None,
                data=None,
            )
        )
        if _ACTIVE_PROGRESS_TRACKER is not None:
            _ACTIVE_PROGRESS_TRACKER.tick(title)
        return None


def summary_frame(results: list[QueryResult]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "SECTION": item.section,
                "CHECK": item.title,
                "CONNECTION": item.connection,
                "STATUS": item.status,
                "ROWS": item.row_count,
                "NOTE": item.note,
            }
            for item in results
        ]
    )


def render_result_blocks(results: list[QueryResult], prefix: str) -> None:
    summary_df = summary_frame(results)
    if summary_df.empty:
        st.info("No queries were executed.")
        return

    metric_cols = st.columns(3)
    metric_cols[0].metric("Passing checks", int((summary_df["STATUS"] == "PASS").sum()), border=True)
    metric_cols[1].metric("No-data checks", int((summary_df["STATUS"] == "NO_DATA").sum()), border=True)
    metric_cols[2].metric("Errors", int((summary_df["STATUS"] == "ERROR").sum()), border=True)

    st.dataframe(summary_df, hide_index=True, use_container_width=True)
    st.download_button(
        "Download summary CSV",
        data=to_csv_bytes(summary_df),
        file_name=f"{prefix}_validation_summary.csv",
        mime="text/csv",
        icon=":material/download:",
    )

    for item in results:
        label = f"[{item.status}] {item.section} - {item.title}"
        with st.expander(label, expanded=item.status == "ERROR"):
            if item.note:
                st.caption(item.note)
            if item.sql:
                st.code(item.sql, language="sql")
            if item.params:
                st.code(str(item.params), language="python")
            if item.data is not None:
                st.dataframe(item.data, hide_index=True, use_container_width=True)
                if not item.data.empty:
                    file_name = f"{prefix}_{item.section}_{item.title}".replace(" ", "_").replace("/", "_").lower()
                    st.download_button(
                        f"Download {item.title} CSV",
                        data=to_csv_bytes(item.data),
                        file_name=f"{file_name}.csv",
                        mime="text/csv",
                        icon=":material/download:",
                        key=f"download_{file_name}",
                    )


def render_context_table(title: str, rows: list[dict[str, Any]]) -> None:
    st.subheader(title)
    context_df = pd.DataFrame(rows)
    st.dataframe(context_df, hide_index=True, use_container_width=True)


def estimate_ubsr_steps() -> int:
    return 12


def estimate_rbm_steps(inputs: dict[str, Any]) -> int:
    # Base checks are always invoked; one additional check runs when product IDs are provided.
    base = 42
    return base + (1 if inputs.get("product_ids") else 0)


def run_with_progress(run_label: str, total_steps: int, callback: Any) -> Any:
    global _ACTIVE_PROGRESS_TRACKER

    progress_slot = st.progress(0, text=f"{run_label} progress: 0%")
    message_slot = st.empty()
    tracker = ProgressTracker(
        run_label=run_label,
        total_steps=max(total_steps, 1),
        progress_slot=progress_slot,
        message_slot=message_slot,
        started_at=time.time(),
    )

    _ACTIVE_PROGRESS_TRACKER = tracker
    try:
        result = callback()
        tracker.complete()
        return result
    finally:
        _ACTIVE_PROGRESS_TRACKER = None


def list_server_processes() -> list[ProcessStatus]:
    """Return python processes running server.py on Windows hosts."""
    command = (
        "Get-CimInstance Win32_Process | "
        "Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -match 'server.py' } | "
        "Select-Object ProcessId, CommandLine | ConvertTo-Json"
    )

    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", command],
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
    except Exception:
        return []

    raw = (result.stdout or "").strip()
    if not raw:
        return []

    statuses: list[ProcessStatus] = []
    try:
        import json

        payload = json.loads(raw)
    except Exception:
        return []

    if isinstance(payload, dict):
        payload = [payload]

    if not isinstance(payload, list):
        return []

    for row in payload:
        if not isinstance(row, dict):
            continue
        pid_val = int(row.get("ProcessId") or -1)
        cmd = str(row.get("CommandLine") or "")
        statuses.append(ProcessStatus(pid=pid_val, command_line=cmd))
    return statuses


def classify_instances(processes: list[ProcessStatus]) -> tuple[list[ProcessStatus], list[ProcessStatus], list[ProcessStatus]]:
    rbm_markers = ["--instance rbm", "instance=rbm", "service=r2w1st011", "oracle-rbm"]
    ubsr_markers = ["--instance ubsr", "instance=ubsr", "service=ub2wst011", "oracle-ubsr"]

    rbm: list[ProcessStatus] = []
    ubsr: list[ProcessStatus] = []
    unknown: list[ProcessStatus] = []

    for proc in processes:
        cmd = proc.command_line.lower()
        rbm_hit = any(marker in cmd for marker in rbm_markers)
        ubsr_hit = any(marker in cmd for marker in ubsr_markers)

        if rbm_hit and not ubsr_hit:
            rbm.append(proc)
        elif ubsr_hit and not rbm_hit:
            ubsr.append(proc)
        else:
            unknown.append(proc)

    return rbm, ubsr, unknown


def start_instance_server(config: DbConfig, instance_name: str) -> tuple[bool, str]:
    spec = INSTANCE_SPECS.get(instance_name)
    if spec is None:
        return False, f"Unknown instance: {instance_name}"

    project_root = Path(__file__).resolve().parent
    python_exe = project_root / ".venv" / "Scripts" / "python.exe"
    server_py = project_root / "server.py"

    if not python_exe.exists():
        return False, f"Python executable not found: {python_exe}"
    if not server_py.exists():
        return False, f"Server entrypoint not found: {server_py}"

    env = os.environ.copy()
    env["ORACLE_HOST"] = config.host
    env["ORACLE_PORT"] = str(config.port)
    env["ORACLE_SERVICE"] = spec.service
    env["ORACLE_USER"] = config.user
    env["ORACLE_PASSWORD"] = config.password

    try:
        proc = subprocess.Popen(
            [
                str(python_exe),
                str(server_py),
                "--instance",
                spec.marker,
            ],
            cwd=str(project_root),
            env=env,
            creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0),
        )
        return True, f"Started {instance_name} server (PID {proc.pid})"
    except Exception as exc:
        return False, str(exc)


def stop_processes(processes: list[ProcessStatus]) -> tuple[int, list[str]]:
    stopped = 0
    errors: list[str] = []
    for proc in processes:
        try:
            os.kill(proc.pid, signal.SIGTERM)
            stopped += 1
        except Exception as exc:
            errors.append(f"PID {proc.pid}: {exc}")
    return stopped, errors


def restart_instance_server(config: DbConfig, instance_name: str, processes: list[ProcessStatus]) -> tuple[bool, str]:
    stopped, errors = stop_processes(processes)
    ok, start_msg = start_instance_server(config, instance_name)
    if not ok:
        return False, f"Stopped {stopped}. Restart failed: {start_msg}"
    if errors:
        return True, f"Restarted with warnings. Stopped {stopped}. {'; '.join(errors)}"
    return True, f"Restarted {instance_name}. Stopped {stopped}."


def check_db_ping(config: DbConfig) -> tuple[bool, str]:
    try:
        df = run_query(config, "SELECT 1 AS HEALTH FROM DUAL")
        if df.empty:
            return False, "No rows returned"
        return True, "Connected"
    except Exception as exc:
        return False, str(exc)


def render_server_monitor_tab(ubsr_config: DbConfig | None, rbm_config: DbConfig | None) -> None:
    st.subheader("RBM and UBSR server monitor")
    st.caption("Check whether MCP server processes are running and verify RBM/UBSR database connectivity.")

    processes = list_server_processes()
    rbm_procs, ubsr_procs, unknown_procs = classify_instances(processes)

    with st.container(horizontal=True):
        st.metric("RBM server process", "Running" if rbm_procs else "Not detected", border=True)
        st.metric("UBSR server process", "Running" if ubsr_procs else "Not detected", border=True)
        st.metric("Unlabeled server.py processes", len(unknown_procs), border=True)

    with st.container(border=True):
        st.markdown("**Process visibility note**")
        st.write(
            "If you start servers without instance markers, they appear as unlabeled server.py processes. "
            "Recommended commands for clearer detection:"
        )
        st.code("python server.py --instance rbm", language="bash")
        st.code("python server.py --instance ubsr", language="bash")

    details_rows = [
        {
            "Instance": "RBM",
            "PID": proc.pid,
            "Command": proc.command_line,
        }
        for proc in rbm_procs
    ] + [
        {
            "Instance": "UBSR",
            "PID": proc.pid,
            "Command": proc.command_line,
        }
        for proc in ubsr_procs
    ] + [
        {
            "Instance": "Unknown",
            "PID": proc.pid,
            "Command": proc.command_line,
        }
        for proc in unknown_procs
    ]

    st.markdown("**Detected server processes**")
    if details_rows:
        st.dataframe(pd.DataFrame(details_rows), hide_index=True, use_container_width=True)
    else:
        st.info("No running python server.py processes were detected.")

    st.markdown("**Connectivity checks**")
    check_now = st.button("Run RBM/UBSR DB ping", icon=":material/network_check:")
    if check_now:
        ping_rows: list[dict[str, str]] = []

        if rbm_config is None:
            ping_rows.append({"Side": "RBM", "Status": "Not configured", "Detail": "Missing RBM_ORACLE_*"})
        else:
            ok, detail = check_db_ping(rbm_config)
            ping_rows.append({"Side": "RBM", "Status": "Connected" if ok else "Failed", "Detail": detail})

        if ubsr_config is None:
            ping_rows.append({"Side": "UBSR", "Status": "Not configured", "Detail": "Missing UBSR_ORACLE_*"})
        else:
            ok, detail = check_db_ping(ubsr_config)
            ping_rows.append({"Side": "UBSR", "Status": "Connected" if ok else "Failed", "Detail": detail})

        st.dataframe(pd.DataFrame(ping_rows), hide_index=True, use_container_width=True)

    st.markdown("**Server controls**")
    rbm_col, ubsr_col = st.columns(2)

    with rbm_col:
        st.markdown("**RBM**")
        start_rbm = st.button("Start RBM", key="start_rbm", icon=":material/play_arrow:")
        stop_rbm = st.button("Stop RBM", key="stop_rbm", icon=":material/stop:")
        restart_rbm = st.button("Restart RBM", key="restart_rbm", icon=":material/restart_alt:")

    with ubsr_col:
        st.markdown("**UBSR**")
        start_ubsr = st.button("Start UBSR", key="start_ubsr", icon=":material/play_arrow:")
        stop_ubsr = st.button("Stop UBSR", key="stop_ubsr", icon=":material/stop:")
        restart_ubsr = st.button("Restart UBSR", key="restart_ubsr", icon=":material/restart_alt:")

    if start_rbm:
        if rbm_config is None:
            st.error("RBM is not configured.")
        else:
            ok, msg = start_instance_server(rbm_config, "RBM")
            (st.success if ok else st.error)(msg)
            st.rerun()

    if stop_rbm:
        stopped, errors = stop_processes(rbm_procs)
        if stopped:
            st.success(f"Stopped {stopped} RBM process(es).")
        else:
            st.info("No RBM processes detected to stop.")
        if errors:
            st.error("; ".join(errors))
        st.rerun()

    if restart_rbm:
        if rbm_config is None:
            st.error("RBM is not configured.")
        else:
            ok, msg = restart_instance_server(rbm_config, "RBM", rbm_procs)
            (st.success if ok else st.error)(msg)
            st.rerun()

    if start_ubsr:
        if ubsr_config is None:
            st.error("UBSR is not configured.")
        else:
            ok, msg = start_instance_server(ubsr_config, "UBSR")
            (st.success if ok else st.error)(msg)
            st.rerun()

    if stop_ubsr:
        stopped, errors = stop_processes(ubsr_procs)
        if stopped:
            st.success(f"Stopped {stopped} UBSR process(es).")
        else:
            st.info("No UBSR processes detected to stop.")
        if errors:
            st.error("; ".join(errors))
        st.rerun()

    if restart_ubsr:
        if ubsr_config is None:
            st.error("UBSR is not configured.")
        else:
            ok, msg = restart_instance_server(ubsr_config, "UBSR", ubsr_procs)
            (st.success if ok else st.error)(msg)
            st.rerun()


def sql_text_list(values: list[str]) -> str:
    escaped = [value.replace("'", "''") for value in values if value.strip()]
    return ", ".join(f"'{value}'" for value in escaped)


def sql_num_list(values: list[int]) -> str:
    return ", ".join(str(value) for value in values)


def build_playbook_sql_context(inputs: dict[str, Any]) -> dict[str, str]:
    customer_refs = inputs.get("customer_refs", [])
    account_nums = inputs.get("account_nums", [])
    mdns = inputs.get("mdns", [])
    product_ids = inputs.get("product_ids", [])
    svc_prod_ids = inputs.get("svc_prod_ids", [])
    audit_ids = inputs.get("audit_ids", [])
    rbm_ids = inputs.get("rbm_ids", [])
    target_ids = inputs.get("target_ids", [])
    tier_scheme_ids = inputs.get("tier_scheme_ids", [])
    tier_scheme_group_ids = inputs.get("tier_scheme_group_ids", [])

    return {
        "customer_refs_sql": sql_text_list(customer_refs),
        "account_nums_sql": sql_text_list(account_nums),
        "mdns_sql": sql_text_list(mdns),
        "product_ids_sql": sql_num_list(product_ids),
        "svc_prod_ids_sql": sql_num_list(svc_prod_ids),
        "audit_ids_sql": sql_text_list(audit_ids),
        "rbm_ids_sql": sql_text_list(rbm_ids),
        "target_ids_sql": sql_text_list(target_ids),
        "tier_scheme_ids_sql": sql_num_list(tier_scheme_ids),
        "tier_scheme_group_ids_sql": sql_num_list(tier_scheme_group_ids),
        "recon_cycle": inputs.get("recon_cycle", "01"),
        "cycle_month": inputs.get("cycle_month", "202211"),
        "bl_cyc_no": inputs.get("bl_cyc_no", "01"),
    }


def missing_sql_requirements(template: ValidationTemplate, sql_context: dict[str, str]) -> list[str]:
    missing: list[str] = []
    for key in template.requires:
        if not str(sql_context.get(key, "")).strip():
            missing.append(key)
    return missing


def run_playbook_templates(
    config: DbConfig,
    templates: list[ValidationTemplate],
    sql_context: dict[str, str],
) -> list[QueryResult]:
    results: list[QueryResult] = []

    for template in templates:
        section = f"{template.phase} / {template.component}"
        if not template.enabled:
            results.append(
                QueryResult(
                    section=section,
                    title=template.title,
                    connection=config.name,
                    sql=template.sql or "",
                    params={},
                    status="SKIPPED",
                    note=template.notes or "Excluded from run",
                    row_count=None,
                    data=None,
                )
            )
            continue

        missing = missing_sql_requirements(template, sql_context)
        if missing:
            results.append(
                QueryResult(
                    section=section,
                    title=template.title,
                    connection=config.name,
                    sql=template.sql or "",
                    params={},
                    status="SKIPPED",
                    note=f"Missing required inputs: {', '.join(missing)}",
                    row_count=None,
                    data=None,
                )
            )
            continue

        if not template.sql:
            results.append(
                QueryResult(
                    section=section,
                    title=template.title,
                    connection=config.name,
                    sql="",
                    params={},
                    status="SKIPPED",
                    note=template.notes or "No SQL configured",
                    row_count=None,
                    data=None,
                )
            )
            continue

        try:
            rendered_sql = template.sql.format(**sql_context)
        except KeyError as exc:
            results.append(
                QueryResult(
                    section=section,
                    title=template.title,
                    connection=config.name,
                    sql=template.sql,
                    params={},
                    status="ERROR",
                    note=f"Template rendering error: missing token {exc}",
                    row_count=None,
                    data=None,
                )
            )
            continue

        execute_validation(
            results,
            config,
            section,
            template.title,
            rendered_sql,
            None,
            template.notes,
        )

    return results


def render_playbook_results_by_category(
    results: list[QueryResult],
    selected_categories: list[str],
    prefix: str,
) -> None:
    """Render playbook results grouped by the 7 validation categories with labelled section headings."""
    if not results:
        st.info("No results to display.")
        return

    # Actual status values from execute_validation / run_playbook_templates:
    # "PASS", "NO_DATA", "ERROR", "SKIPPED"
    total = len(results)
    passed = sum(1 for r in results if r.status == "PASS")
    no_data = sum(1 for r in results if r.status == "NO_DATA")
    failed = sum(1 for r in results if r.status == "ERROR")
    skipped = sum(1 for r in results if r.status == "SKIPPED")

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Total checks", total)
    m2.metric("✅ Pass", passed)
    m3.metric("⚠️ No data", no_data)
    m4.metric("❌ Error", failed)
    m5.metric("⏭ Skipped", skipped)

    # Group results by category using the phase code embedded in r.section ("Cat N / ...")
    # Build a lookup: phase_code -> list[QueryResult]
    phase_to_results: dict[str, list[QueryResult]] = {}
    for r in results:
        phase_code = r.section.split(" / ")[0]  # e.g. "Cat 1"
        phase_to_results.setdefault(phase_code, []).append(r)

    # Render each selected category as its own bordered container with a heading
    for cat_name in selected_categories:
        phase_code = PLAYBOOK_CATEGORIES.get(cat_name, "")
        cat_results = phase_to_results.get(phase_code, [])
        if not cat_results:
            continue

        cat_passed = sum(1 for r in cat_results if r.status == "PASS")
        cat_no_data = sum(1 for r in cat_results if r.status == "NO_DATA")
        cat_failed = sum(1 for r in cat_results if r.status == "ERROR")

        status_icon = (
            "✅" if cat_failed == 0 and cat_no_data == 0
            else "⚠️" if cat_failed == 0
            else "❌"
        )

        with st.container(border=True):
            st.markdown(f"### {status_icon} {cat_name}")
            st.caption(
                f"{len(cat_results)} checks — "
                f"{cat_passed} pass · {cat_no_data} no data · {cat_failed} error"
            )

            for idx, r in enumerate(cat_results):
                icon = (
                    "✅" if r.status == "PASS"
                    else "⚠️" if r.status == "NO_DATA"
                    else "⏭" if r.status == "SKIPPED"
                    else "❌"
                )
                with st.expander(f"{icon} {r.title}", expanded=(r.status == "ERROR")):
                    if r.note:
                        st.info(r.note)
                    if r.status == "SKIPPED":
                        st.caption("Skipped — missing required inputs for this check.")
                    elif r.status == "ERROR":
                        err_text = r.data if isinstance(r.data, str) else "Query error — see logs."
                        st.error(err_text)
                    else:
                        if r.sql:
                            st.code(r.sql, language="sql")
                        if r.data is not None and not isinstance(r.data, str):
                            st.caption(f"{r.row_count} row(s)")
                            st.dataframe(r.data, use_container_width=True)
                            csv_bytes = r.data.to_csv(index=False).encode()
                            st.download_button(
                                "Download CSV",
                                data=csv_bytes,
                                file_name=f"{prefix}_{r.title.replace(' ', '_').lower()}.csv",
                                mime="text/csv",
                                key=f"dl_{prefix}_{phase_code}_{idx}",
                            )

    # Combined download of all result rows
    all_dfs = []
    for r in results:
        if r.data is not None and not isinstance(r.data, str):
            df = r.data.copy()
            df.insert(0, "_category", r.section)
            df.insert(1, "_table", r.title)
            df.insert(2, "_status", r.status)
            all_dfs.append(df)
    if all_dfs:
        combined = pd.concat(all_dfs, ignore_index=True)
        st.download_button(
            "⬇ Download all results (combined CSV)",
            data=combined.to_csv(index=False).encode(),
            file_name=f"{prefix}_all_results.csv",
            mime="text/csv",
            key=f"dl_{prefix}_all",
        )


def render_playbook_tab(ubsr_config: DbConfig | None, rbm_config: DbConfig | None) -> None:
    st.subheader("Migration validation playbook")
    st.caption(
        "Runs query templates across 7 validation categories with separate RBM and UBSR outputs."
    )

    with st.container(border=True):
        st.markdown("**Manual checkpoints**")
        st.write(f"Recon input file path: {PLAYBOOK_RECON_PATH}")
        st.write(f"Environment file path on server: {PLAYBOOK_ENV_PATH}")
        st.warning("Payments setup checks are intentionally excluded from DT pre-validation.")

    with st.form("playbook_form", border=True):
        st.markdown("**Core identifiers**")
        row1 = st.columns(3)
        customer_refs_raw = row1[0].text_area("Customer refs", placeholder="713267600, 742778442")
        account_nums_raw = row1[1].text_area("Account numbers", placeholder="342330672-1, 742341624-1")
        mdns_raw = row1[2].text_area("MDNs / LN_OF_SVC_ID_NO_P2", placeholder="5339330992, 344400040255061200")

        row2 = st.columns(3)
        product_ids_raw = row2[0].text_input("Product IDs", placeholder="66128, 66126, 62225")
        svc_prod_ids_raw = row2[1].text_input("Service product IDs", placeholder="3727")
        audit_ids_raw = row2[2].text_input("Audit IDs", placeholder="945427, 919664")

        row3 = st.columns(3)
        rbm_ids_raw = row3[0].text_input("RBM ID values", placeholder="68950, 69055, 61870")
        target_ids_raw = row3[1].text_input("Target IDs", placeholder="70001, 70165")
        recon_cycle = row3[2].text_input("Recon cycle", value="01")

        row4 = st.columns(3)
        cycle_month = row4[0].text_input("EOC cycle month", value="202211")
        bl_cyc_no = row4[1].text_input("EOC bill cycle number", value="01")
        run_side = row4[2].selectbox("Validation side", options=["Both", "RBM", "UBSR"])

        row5 = st.columns(2)
        tier_scheme_ids_raw = row5[0].text_input("Tier scheme IDs", placeholder="1117")
        tier_scheme_group_ids_raw = row5[1].text_input("Tier scheme group IDs", placeholder="117")

        category_names = list(PLAYBOOK_CATEGORIES.keys())
        selected_categories = st.multiselect(
            "Categories to run",
            options=category_names,
            default=category_names,
            help="Select which of the 7 validation categories to include in this run.",
        )

        run_playbook = st.form_submit_button("Run validation playbook", type="primary", icon=":material/play_arrow:")

    if not run_playbook:
        return

    raw_inputs = {
        "customer_refs": parse_tokens(customer_refs_raw),
        "account_nums": parse_tokens(account_nums_raw),
        "mdns": parse_tokens(mdns_raw),
        "product_ids": parse_int_tokens(product_ids_raw),
        "svc_prod_ids": parse_int_tokens(svc_prod_ids_raw),
        "audit_ids": parse_tokens(audit_ids_raw),
        "rbm_ids": parse_tokens(rbm_ids_raw),
        "target_ids": parse_tokens(target_ids_raw),
        "recon_cycle": recon_cycle.strip() or "01",
        "cycle_month": cycle_month.strip() or "202211",
        "bl_cyc_no": bl_cyc_no.strip() or "01",
        "tier_scheme_ids": parse_int_tokens(tier_scheme_ids_raw),
        "tier_scheme_group_ids": parse_int_tokens(tier_scheme_group_ids_raw),
    }

    sql_context = build_playbook_sql_context(raw_inputs)
    # Filter by selected categories using the phase code mapping
    selected_phases = {PLAYBOOK_CATEGORIES[cat] for cat in selected_categories}
    selected_templates = [item for item in PLAYBOOK_TEMPLATES if item.phase in selected_phases]

    rbm_templates = [item for item in selected_templates if item.side == "RBM"]
    ubsr_templates = [item for item in selected_templates if item.side == "UBSR"]

    if run_side in ["Both", "RBM"] and rbm_config is None:
        st.error("RBM connection is not configured.")
        return
    if run_side in ["Both", "UBSR"] and ubsr_config is None:
        st.error("UBSR connection is not configured.")
        return

    if run_side == "RBM":
        with st.spinner("Running RBM playbook validations..."):
            rbm_results = run_playbook_templates(rbm_config, rbm_templates, sql_context) if rbm_config else []
        render_playbook_results_by_category(rbm_results, selected_categories, "rbm_playbook")
        return

    if run_side == "UBSR":
        with st.spinner("Running UBSR playbook validations..."):
            ubsr_results = run_playbook_templates(ubsr_config, ubsr_templates, sql_context) if ubsr_config else []
        render_playbook_results_by_category(ubsr_results, selected_categories, "ubsr_playbook")
        return

    with st.spinner("Running RBM and UBSR playbook validations..."):
        rbm_results = run_playbook_templates(rbm_config, rbm_templates, sql_context) if rbm_config else []
        ubsr_results = run_playbook_templates(ubsr_config, ubsr_templates, sql_context) if ubsr_config else []

    rbm_result_tab, ubsr_result_tab = st.tabs(["RBM results", "UBSR results"])
    with rbm_result_tab:
        render_playbook_results_by_category(rbm_results, selected_categories, "rbm_playbook")
    with ubsr_result_tab:
        render_playbook_results_by_category(ubsr_results, selected_categories, "ubsr_playbook")


def run_ubsr_validations(config: DbConfig, inputs: dict[str, Any]) -> tuple[list[QueryResult], list[dict[str, Any]]]:
    results: list[QueryResult] = []
    context_rows: list[dict[str, Any]] = []

    customer_ids = inputs["customer_ids"]
    rbm_ids = inputs["rbm_ids"]
    target_ids = inputs["target_ids"]
    mdns = inputs["mdns"]
    svc_prod_ids = inputs["svc_prod_ids"]
    audit_ids = inputs["audit_ids"]
    recon_cycle = inputs["recon_cycle"]

    base_params: dict[str, Any] = {}
    base_filters = [
        build_in_filter("CUST_ID_NO", customer_ids, "cust", base_params),
        build_in_filter("RBM_ID_VALUE", rbm_ids, "rbm", base_params),
        build_in_filter("MDN", mdns, "mdn", base_params),
    ]
    base_where = " AND ".join(filter(None, base_filters))

    execute_validation(
        results,
        config,
        "UBSR billing",
        "sub_xlt_bl_rbm_billing",
        f"SELECT * FROM UBSR.SUB_XLT_BL_RBM_BILLING WHERE {base_where}" if base_where else None,
        base_params if base_where else None,
        "Primary billing-side match on customer, RBM ID, and MDN.",
    )
    execute_validation(
        results,
        config,
        "UBSR rating",
        "sub_xlt_bl_rbm",
        f"SELECT * FROM UBSR.SUB_XLT_BL_RBM WHERE {base_where}" if base_where else None,
        base_params if base_where else None,
        "Primary rating-side match on customer, RBM ID, and MDN.",
    )

    comparison_sql = None
    if base_where:
        comparison_sql = f"""
        SELECT 'BILLING' AS SOURCE, COUNT(*) AS ROW_COUNT
        FROM UBSR.SUB_XLT_BL_RBM_BILLING
        WHERE {base_where}
        UNION ALL
        SELECT 'RATING' AS SOURCE, COUNT(*) AS ROW_COUNT
        FROM UBSR.SUB_XLT_BL_RBM
        WHERE {base_where}
        """
    execute_validation(
        results,
        config,
        "UBSR reconciliation",
        "billing_vs_rating_counts",
        comparison_sql,
        base_params if comparison_sql else None,
        "Quick comparison to spot mismatched row presence between billing and rating layers.",
    )

    rbm_params: dict[str, Any] = {}
    rbm_filter = build_in_filter("RBM_ID_VALUE", rbm_ids, "rbm_map", rbm_params)
    execute_validation(
        results,
        config,
        "UBSR mappings",
        "ref_vis_xlt_rating_trans_map",
        f"SELECT * FROM MZADMIN.REF_VIS_XLT_RATING_TRANS_MAP WHERE {rbm_filter}" if rbm_filter else None,
        rbm_params if rbm_filter else None,
    )

    target_params: dict[str, Any] = {}
    target_filter = build_in_filter("TARGET_ID", target_ids, "target", target_params)
    execute_validation(
        results,
        config,
        "UBSR mappings",
        "ref_vis_xlt_billing_trans_map",
        f"SELECT * FROM MZADMIN.REF_VIS_XLT_BILLING_TRANS_MAP WHERE {target_filter}" if target_filter else None,
        target_params if target_filter else None,
    )

    svc_params: dict[str, Any] = {}
    svc_filter = build_in_filter("SVC_PROD_ID", svc_prod_ids, "svc", svc_params)
    execute_validation(
        results,
        config,
        "UBSR products",
        "ref_vis_svc_prod_prc_element",
        f"SELECT * FROM DB2CDC.REF_VIS_SVC_PROD_PRC_ELEMENT WHERE {svc_filter}" if svc_filter else None,
        svc_params if svc_filter else None,
        "Optional. Provide service product IDs to validate product-pricing rows.",
    )

    usg_params: dict[str, Any] = {}
    usg_filters = [
        build_in_filter("LN_OF_SVC_ID_NO_P2", mdns, "mdn_usg", usg_params),
        build_in_filter("SVC_PROD_ID", svc_prod_ids, "svc_usg", usg_params),
    ]
    usg_where = " AND ".join(filter(None, usg_filters))
    execute_validation(
        results,
        config,
        "UBSR products",
        "sub_ln_svc_prod_usg_seg_ba",
        f"SELECT * FROM UBSR.SUB_LN_SVC_PROD_USG_SEG_BA WHERE {usg_where}" if usg_where else None,
        usg_params if usg_where else None,
        "Runs with MDN only or MDN plus service product IDs.",
    )

    recon_params: dict[str, Any] = {}
    recon_filter = build_in_filter("CUST_ID_NO", customer_ids, "recon_cust", recon_params)
    execute_validation(
        results,
        config,
        "UBSR reconciliation",
        "reed_recon",
        f"SELECT * FROM REED.REED_RECON WHERE {recon_filter}" if recon_filter else None,
        recon_params if recon_filter else None,
    )

    cycle_df = execute_validation(
        results,
        config,
        "UBSR audit",
        "ref_rcn_bl_cycle_config_hist",
        """
        SELECT *
        FROM MZADMIN.REF_RCN_BL_CYCLE_CONFIG_HIST
        WHERE RECON_CYCLE = :recon_cycle
        ORDER BY CREATE_DATE_TS DESC
        """,
        {"recon_cycle": recon_cycle},
        "Used to derive the latest audit ID when none is supplied.",
    )

    derived_audit_ids = audit_ids[:]
    if not derived_audit_ids and cycle_df is not None and not cycle_df.empty:
        derived_audit_ids = [str(value) for value in dataframe_values(cycle_df, ["AUDIT_ID"])[:1]]

    context_rows.append({"Context": "Recon cycle", "Value": recon_cycle, "Source": "User input"})
    context_rows.append(
        {
            "Context": "Audit IDs used",
            "Value": ", ".join(derived_audit_ids) if derived_audit_ids else "None",
            "Source": "User input or latest cycle history row",
        }
    )

    audit_fix_params: dict[str, Any] = {"process_type": "UBSRTORBM_PRODUCTS_BILLING"}
    audit_fix_filter = build_in_filter("AUDIT_ID", derived_audit_ids, "audit_fix", audit_fix_params)
    execute_validation(
        results,
        config,
        "UBSR audit",
        "sub_rcn_fixes",
        (
            f"SELECT * FROM UBSR.SUB_RCN_FIXES WHERE {audit_fix_filter} AND PROCESS_TYPE = :process_type"
            if audit_fix_filter
            else None
        ),
        audit_fix_params if audit_fix_filter else None,
    )

    audit_list_params: dict[str, Any] = {}
    audit_list_filter = build_in_filter("AUDIT_ID", derived_audit_ids, "audit_list", audit_list_params)
    execute_validation(
        results,
        config,
        "UBSR audit",
        "recon_full_processing_list",
        f"SELECT * FROM UBSR.RECON_FULL_PROCESSING_LIST WHERE {audit_list_filter}" if audit_list_filter else None,
        audit_list_params if audit_list_filter else None,
    )

    prim_params: dict[str, Any] = {}
    prim_filter = build_in_filter("LN_OF_SVC_ID_NO_P2", mdns, "prim_mdn", prim_params)
    execute_validation(
        results,
        config,
        "UBSR line mappings",
        "ref_vis_ln_prim_multi_id",
        f"SELECT * FROM UBSR.REF_VIS_LN_PRIM_MULTI_ID WHERE {prim_filter}" if prim_filter else None,
        prim_params if prim_filter else None,
    )

    return results, context_rows


def run_rbm_validations(config: DbConfig, inputs: dict[str, Any]) -> tuple[list[QueryResult], list[dict[str, Any]]]:
    results: list[QueryResult] = []
    context_rows: list[dict[str, Any]] = []

    customer_refs = inputs["customer_refs"]
    product_ids = inputs["product_ids"]
    mtns = inputs["mtns"]
    account_nums = inputs["account_nums"]
    product_seqs = inputs["product_seqs"]
    run_ids = inputs["run_ids"]
    scm_audit_codes = inputs["scm_audit_codes"]

    customer_params: dict[str, Any] = {}
    customer_filter = build_in_filter("CUSTOMER_REF", customer_refs, "cust_ref", customer_params)
    account_df = execute_validation(
        results,
        config,
        "RBM customer",
        "account",
        f"SELECT * FROM GENEVA_ADMIN.ACCOUNT WHERE {customer_filter}" if customer_filter else None,
        customer_params if customer_filter else None,
        "If account numbers are omitted, they are derived from this result set.",
    )

    derived_account_nums = account_nums[:]
    if not derived_account_nums and account_df is not None and not account_df.empty:
        derived_account_nums = [str(value) for value in dataframe_values(account_df, ["ACCOUNT_NUM"])]

    context_rows.append(
        {
            "Context": "Account numbers used",
            "Value": ", ".join(derived_account_nums) if derived_account_nums else "None",
            "Source": "User input or ACCOUNT lookup",
        }
    )

    seed_params: dict[str, Any] = {}
    seed_filters = [
        build_in_filter("CUSTOMER_REF", customer_refs, "cust_seed", seed_params),
        build_in_filter("PRODUCT_ID", product_ids, "prod_seed", seed_params),
    ]
    seed_where = " AND ".join(filter(None, seed_filters))
    seed_df = execute_validation(
        results,
        config,
        "RBM products",
        "custhasproduct_seed",
        f"SELECT * FROM GENEVA_ADMIN.CUSTHASPRODUCT WHERE {seed_where}" if seed_where else None,
        seed_params if seed_where else None,
        "Used to derive product sequence IDs when they are not entered explicitly.",
    )

    derived_product_seqs = product_seqs[:]
    if not derived_product_seqs and seed_df is not None and not seed_df.empty:
        derived_product_seqs = [int(value) for value in dataframe_values(seed_df, ["PRODUCT_SEQ"])]

    context_rows.append(
        {
            "Context": "Product sequences used",
            "Value": ", ".join(str(value) for value in derived_product_seqs) if derived_product_seqs else "None",
            "Source": "User input or CUSTHASPRODUCT seed query",
        }
    )

    product_params: dict[str, Any] = {}
    product_filter = build_in_filter("PRODUCT_ID", product_ids, "prod", product_params)
    execute_validation(
        results,
        config,
        "RBM products",
        "vzsvcprodcat",
        f"SELECT * FROM RB_CUSTOM.VZSVCPRODCAT WHERE {product_filter}" if product_filter else None,
        product_params if product_filter else None,
    )
    execute_validation(
        results,
        config,
        "RBM products",
        "tariffelement",
        f"SELECT * FROM GENEVA_ADMIN.TARIFFELEMENT WHERE {product_filter}" if product_filter else None,
        product_params if product_filter else None,
    )

    bills_params: dict[str, Any] = {}
    bills_filter = build_in_filter("ACCOUNT_NUM", derived_account_nums, "acct_bill", bills_params)
    execute_validation(
        results,
        config,
        "RBM billing",
        "billsummary",
        f"SELECT * FROM GENEVA_ADMIN.BILLSUMMARY WHERE {bills_filter}" if bills_filter else None,
        bills_params if bills_filter else None,
    )

    event_params: dict[str, Any] = {}
    event_filters = [
        build_in_filter("ACCOUNT_NUM", derived_account_nums, "acct_evt", event_params),
        build_in_filter("EVENT_SOURCE", mtns, "mtn_evt", event_params),
    ]
    event_where = " AND ".join(filter(None, event_filters))
    execute_validation(
        results,
        config,
        "RBM lines",
        "vzeventsourcestatus",
        f"SELECT * FROM RB_CUSTOM.VZEVENTSOURCESTATUS WHERE {event_where}" if event_where else None,
        event_params if event_where else None,
    )

    cust_event_params: dict[str, Any] = {}
    cust_event_filters = [
        build_in_filter("CUSTOMER_REF", customer_refs, "cust_evt", cust_event_params),
        build_in_filter("EVENT_SOURCE", mtns, "evt_src", cust_event_params),
    ]
    cust_event_where = " AND ".join(filter(None, cust_event_filters))
    execute_validation(
        results,
        config,
        "RBM lines",
        "custeventsource",
        f"SELECT * FROM GENEVA_ADMIN.CUSTEVENTSOURCE WHERE {cust_event_where}" if cust_event_where else None,
        cust_event_params if cust_event_where else None,
    )

    acct_attr_params: dict[str, Any] = {}
    acct_attr_filter = build_in_filter("ACCOUNT_NUM", derived_account_nums, "acct_attr", acct_attr_params)
    execute_validation(
        results,
        config,
        "RBM customer",
        "accountattributes",
        f"SELECT * FROM GENEVA_ADMIN.ACCOUNTATTRIBUTES WHERE {acct_attr_filter}" if acct_attr_filter else None,
        acct_attr_params if acct_attr_filter else None,
    )

    execute_validation(
        results,
        config,
        "RBM products",
        "vzfincompdtls",
        (
            f"SELECT * FROM RB_CUSTOM.VZFINCOMPDTLS WHERE {product_filter} "
            f"AND CATALOGUE_CHANGE_ID = (SELECT MAX(CATALOGUE_CHANGE_ID) FROM GENEVA_ADMIN.CATALOGUECHANGE)"
            if product_filter
            else None
        ),
        product_params if product_filter else None,
        "Uses the latest catalogue change ID.",
    )
    execute_validation(
        results,
        config,
        "RBM products",
        "tariffelementband",
        (
            f"SELECT * FROM GENEVA_ADMIN.TARIFFELEMENTBAND WHERE {product_filter} "
            f"AND CATALOGUE_CHANGE_ID = (SELECT MAX(CATALOGUE_CHANGE_ID) FROM GENEVA_ADMIN.CATALOGUECHANGE)"
            if product_filter
            else None
        ),
        product_params if product_filter else None,
        "Uses the latest catalogue change ID.",
    )

    attr_params: dict[str, Any] = {}
    attr_filters = [
        build_in_filter("CUSTOMER_REF", customer_refs, "cust_attr", attr_params),
        build_in_filter("PRODUCT_ID", product_ids, "prod_attr", attr_params),
    ]
    attr_where = " AND ".join(filter(None, attr_filters))
    execute_validation(
        results,
        config,
        "RBM products",
        "custproductattrdetails",
        f"SELECT * FROM GENEVA_ADMIN.CUSTPRODUCTATTRDETAILS WHERE {attr_where}" if attr_where else None,
        attr_params if attr_where else None,
    )

    cust_only_params: dict[str, Any] = {}
    cust_only_filter = build_in_filter("CUSTOMER_REF", customer_refs, "cust_only", cust_only_params)
    execute_validation(
        results,
        config,
        "RBM products",
        "custproductcharge",
        f"SELECT * FROM GENEVA_ADMIN.CUSTPRODUCTCHARGE WHERE {cust_only_filter}" if cust_only_filter else None,
        cust_only_params if cust_only_filter else None,
    )
    execute_validation(
        results,
        config,
        "RBM products",
        "custproductdetails",
        f"SELECT * FROM GENEVA_ADMIN.CUSTPRODUCTDETAILS WHERE {cust_only_filter}" if cust_only_filter else None,
        cust_only_params if cust_only_filter else None,
    )

    cmaf_params: dict[str, Any] = {}
    cmaf_filters = [
        build_in_filter("CUST_ID_NO", customer_refs, "cmaf_cust", cmaf_params),
        build_in_filter("NPA||NXX||TLN", mtns, "cmaf_mtn", cmaf_params),
    ]
    cmaf_where = " AND ".join(filter(None, cmaf_filters))
    execute_validation(
        results,
        config,
        "RBM conversion",
        "conv_imdt.cmaf_u",
        f"SELECT * FROM CONV_IMDT.CMAF_U WHERE {cmaf_where}" if cmaf_where else None,
        cmaf_params if cmaf_where else None,
    )

    acct_details_params: dict[str, Any] = {}
    acct_details_filter = build_in_filter("ACCOUNT_NUM", derived_account_nums, "acct_det", acct_details_params)
    execute_validation(
        results,
        config,
        "RBM customer",
        "accountdetails",
        f"SELECT * FROM GENEVA_ADMIN.ACCOUNTDETAILS WHERE {acct_details_filter}" if acct_details_filter else None,
        acct_details_params if acct_details_filter else None,
    )

    execute_validation(
        results,
        config,
        "RBM products",
        "product",
        f"SELECT * FROM GENEVA_ADMIN.PRODUCT WHERE {product_filter}" if product_filter else None,
        product_params if product_filter else None,
    )
    execute_validation(
        results,
        config,
        "RBM products",
        "product_5g_fwa",
        (
            f"SELECT * FROM GENEVA_ADMIN.PRODUCT WHERE PRODUCT_DESC LIKE '%5G FWA%' AND {product_filter}"
            if product_filter
            else "SELECT * FROM GENEVA_ADMIN.PRODUCT WHERE PRODUCT_DESC LIKE '%5G FWA%'"
        ),
        product_params if product_filter else None,
    )

    label_params: dict[str, Any] = {}
    label_filters = [
        build_in_filter("CUSTOMER_REF", customer_refs, "cust_label", label_params),
        build_in_filter("PRODUCT_LABEL", mtns, "prod_label", label_params),
    ]
    label_where = " AND ".join(filter(None, label_filters))
    execute_validation(
        results,
        config,
        "RBM lines",
        "custproductdetails_by_label",
        f"SELECT * FROM GENEVA_ADMIN.CUSTPRODUCTDETAILS WHERE {label_where}" if label_where else None,
        label_params if label_where else None,
    )

    has_prod_params: dict[str, Any] = {}
    has_prod_filters = [
        build_in_filter("CUSTOMER_REF", customer_refs, "cust_has", has_prod_params),
        build_in_filter("PRODUCT_SEQ", derived_product_seqs, "seq_has", has_prod_params),
    ]
    has_prod_where = " AND ".join(filter(None, has_prod_filters))
    execute_validation(
        results,
        config,
        "RBM products",
        "custhasproduct_conv",
        (
            f"SELECT * FROM GENEVA_ADMIN.CUSTHASPRODUCT WHERE {has_prod_where} AND CUST_ORDER_NUM LIKE '%CONV%'"
            if has_prod_where
            else None
        ),
        has_prod_params if has_prod_where else None,
    )

    status_params: dict[str, Any] = {}
    status_filters = [
        build_in_filter("CUSTOMER_REF", customer_refs, "cust_status", status_params),
        build_in_filter("PRODUCT_SEQ", derived_product_seqs, "seq_status", status_params),
    ]
    status_where = " AND ".join(filter(None, status_filters))
    execute_validation(
        results,
        config,
        "RBM products",
        "custproductstatus",
        f"SELECT * FROM GENEVA_ADMIN.CUSTPRODUCTSTATUS WHERE {status_where}" if status_where else None,
        status_params if status_where else None,
    )

    bill_prod_params: dict[str, Any] = {}
    bill_prod_filters = [
        build_in_filter("ACCOUNT_NUM", derived_account_nums, "acct_bpc", bill_prod_params),
        build_in_filter("PRODUCT_SEQ", derived_product_seqs, "seq_bpc", bill_prod_params),
    ]
    bill_prod_where = " AND ".join(filter(None, bill_prod_filters))
    execute_validation(
        results,
        config,
        "RBM billing",
        "billproductcharge",
        f"SELECT * FROM GENEVA_ADMIN.BILLPRODUCTCHARGE WHERE {bill_prod_where}" if bill_prod_where else None,
        bill_prod_params if bill_prod_where else None,
    )

    execute_validation(results, config, "RBM reference", "customertype", "SELECT * FROM GENEVA_ADMIN.CUSTOMERTYPE", None)
    execute_validation(
        results,
        config,
        "RBM reference",
        "components_versions",
        "SELECT * FROM GENEVA_ADMIN.COMPONENTS_VERSIONS WHERE COMPONENT_ID = 'VZWRB' ORDER BY INSTALL_DATE DESC",
        None,
    )
    execute_validation(
        results,
        config,
        "RBM reference",
        "billingrba_flow",
        """
        SELECT *
        FROM BILLINGRBA_ADMIN.FLOW
        WHERE FLOW_NAME IN ('BILLCALC_Pre_BGTest')
          AND STEP_NAME IN ('BILLCALC_BAU_SubAcc_BGTest', 'BILLCALC_PhyAcc_BGTest')
        """,
        None,
    )

    otc_params: dict[str, Any] = {}
    otc_filter = build_in_filter("ACCOUNT_NUM", derived_account_nums, "acct_otc", otc_params)
    execute_validation(
        results,
        config,
        "RBM billing",
        "acchasonetimecharge",
        f"SELECT * FROM GENEVA_ADMIN.ACCHASONETIMECHARGE WHERE {otc_filter}" if otc_filter else None,
        otc_params if otc_filter else None,
    )

    bill_custom_params: dict[str, Any] = {}
    bill_custom_filter = build_in_filter("CUST_ID_NO", customer_refs, "bill_cmaf", bill_custom_params)
    execute_validation(
        results,
        config,
        "RBM conversion",
        "bill_custom.cmaf_u_by_customer",
        f"SELECT * FROM BILL_CUSTOM.CMAF_U WHERE {bill_custom_filter}" if bill_custom_filter else None,
        bill_custom_params if bill_custom_filter else None,
    )

    tln_params: dict[str, Any] = {}
    tln_filters = [
        build_in_filter("CUST_ID_NO", customer_refs, "cust_tln", tln_params),
        build_in_filter("TLN", mtns, "tln", tln_params),
    ]
    tln_where = " AND ".join(filter(None, tln_filters))
    execute_validation(
        results,
        config,
        "RBM conversion",
        "bill_custom.cmaf_u_by_tln",
        f"SELECT * FROM BILL_CUSTOM.CMAF_U WHERE {tln_where}" if tln_where else None,
        tln_params if tln_where else None,
    )

    execute_validation(results, config, "RBM reference", "ubmaint.acctlist", "SELECT * FROM UBMAINT.ACCTLIST", None)

    run_params: dict[str, Any] = {}
    run_filter = build_in_filter("RUN_ID", run_ids, "run", run_params)
    execute_validation(
        results,
        config,
        "RBM conversion",
        "ops_extraction",
        f"SELECT * FROM CONV_IMDT.OPS_EXTRACTION WHERE {run_filter}" if run_filter else None,
        run_params if run_filter else None,
    )

    ei_params: dict[str, Any] = {}
    ei_filters = [
        build_in_filter("CUST_ID_NO", customer_refs, "ei_cust", ei_params),
        build_in_filter("RUN_ID", run_ids, "ei_run", ei_params),
    ]
    ei_where = " AND ".join(filter(None, ei_filters))
    execute_validation(
        results,
        config,
        "RBM conversion",
        "ei_customer",
        f"SELECT * FROM CONV_IMDT.EI_CUSTOMER WHERE {ei_where}" if ei_where else None,
        ei_params if ei_where else None,
    )

    primary_run_id = run_ids[0] if run_ids else None
    execute_validation(
        results,
        config,
        "RBM conversion",
        "ei_customer_failures",
        (
            "SELECT CUST_ID_NO, STATUS, REASON FROM CONV_IMDT.EI_CUSTOMER "
            "WHERE RUN_ID = :run_id AND STATUS != 'SUCCESS'"
            if primary_run_id is not None
            else None
        ),
        {"run_id": primary_run_id} if primary_run_id is not None else None,
    )
    execute_validation(
        results,
        config,
        "RBM conversion",
        "ops_extract_customer",
        "SELECT * FROM CONV_IMDT.OPS_EXTRACT_CUSTOMER WHERE RUN_ID = :run_id" if primary_run_id is not None else None,
        {"run_id": primary_run_id} if primary_run_id is not None else None,
    )

    if product_ids:
        tariff_params: dict[str, Any] = {}
        outer_filter = build_in_filter("te.PRODUCT_ID", product_ids, "tariff_prod", tariff_params)
        inner_filter = build_in_filter("PRODUCT_ID", product_ids, "tariff_sub", tariff_params)
        execute_validation(
            results,
            config,
            "RBM analysis",
            "tariff_configuration",
            f"""
            SELECT te.PRODUCT_ID,
                   te.TARIFF_ID,
                   te.CHARGE_PERIOD,
                   te.CHARGE_PERIOD_UNITS,
                   te.IN_ADVANCE_BOO,
                   te.PRO_RATE_BOO,
                   te.SYNCHRONISE_BOO,
                   te.REFUNDABLE_BOO,
                   TO_CHAR(te.START_DAT, 'DD-MON-YYYY') AS TARIFF_START,
                   TO_CHAR(te.END_DAT, 'DD-MON-YYYY') AS TARIFF_END,
                   scope.RECURRING_ATTR_VALUE AS SCOPE
            FROM GENEVA_ADMIN.TARIFFELEMENT te
            LEFT JOIN GENEVA_ADMIN.TARIFFELEMENTATTRDETAILS scope
              ON te.PRODUCT_ID = scope.PRODUCT_ID
             AND scope.PRODUCT_PRICE_ATTR_ID = 2
            WHERE {outer_filter}
              AND te.CATALOGUE_CHANGE_ID = (
                    SELECT MAX(CATALOGUE_CHANGE_ID)
                    FROM GENEVA_ADMIN.TARIFFELEMENT
                    WHERE {inner_filter}
              )
            """,
            tariff_params,
            "Configuration view for the selected product IDs.",
        )

    account_product_params: dict[str, Any] = {}
    account_product_filters = [
        build_in_filter("a.ACCOUNT_NUM", derived_account_nums, "acct_ap", account_product_params),
        build_in_filter("chp.PRODUCT_ID", product_ids, "prod_ap", account_product_params),
    ]
    account_product_where = " AND ".join(filter(None, account_product_filters))
    execute_validation(
        results,
        config,
        "RBM analysis",
        "account_product_lifecycle",
        f"""
        SELECT a.ACCOUNT_NUM,
               a.CUSTOMER_REF,
               TO_CHAR(a.NEXT_BILL_DTM, 'DD-MON-YY') AS NEXT_BILL_DATE,
               a.LAST_BILL_SEQ,
               chp.PRODUCT_SEQ,
               chp.PRODUCT_ID,
               TO_CHAR(cpd.START_DAT, 'DD-MON-YY') AS PRODUCT_START,
               TO_CHAR(cpd.END_DAT, 'DD-MON-YY') AS PRODUCT_END,
               cps.PRODUCT_STATUS,
               TO_CHAR(cps.EFFECTIVE_DTM, 'DD-MON-YY HH24:MI:SS') AS STATUS_DATE
        FROM GENEVA_ADMIN.ACCOUNT a
        JOIN GENEVA_ADMIN.CUSTHASPRODUCT chp
          ON a.CUSTOMER_REF = chp.CUSTOMER_REF
        JOIN GENEVA_ADMIN.CUSTPRODUCTDETAILS cpd
          ON chp.CUSTOMER_REF = cpd.CUSTOMER_REF
         AND chp.PRODUCT_SEQ = cpd.PRODUCT_SEQ
        LEFT JOIN (
            SELECT CUSTOMER_REF,
                   PRODUCT_SEQ,
                   PRODUCT_STATUS,
                   EFFECTIVE_DTM,
                   ROW_NUMBER() OVER (
                       PARTITION BY CUSTOMER_REF, PRODUCT_SEQ
                       ORDER BY EFFECTIVE_DTM DESC
                   ) AS rn
            FROM GENEVA_ADMIN.CUSTPRODUCTSTATUS
        ) cps
          ON chp.CUSTOMER_REF = cps.CUSTOMER_REF
         AND chp.PRODUCT_SEQ = cps.PRODUCT_SEQ
         AND cps.rn = 1
        WHERE {account_product_where}
        """
        if account_product_where
        else None,
        account_product_params if account_product_where else None,
    )

    nbd_params: dict[str, Any] = {}
    nbd_filters = [
        build_in_filter("CUSTOMER_REF", customer_refs, "cust_nbd", nbd_params),
        build_in_filter("PRODUCT_SEQ", derived_product_seqs, "seq_nbd", nbd_params),
    ]
    nbd_where = " AND ".join(filter(None, nbd_filters))
    execute_validation(
        results,
        config,
        "RBM analysis",
        "product_status_at_nbd",
        f"""
        SELECT PRODUCT_STATUS,
               TO_CHAR(EFFECTIVE_DTM, 'DD-MON-YY HH24:MI:SS') AS STATUS_DATE,
               CUSTOMER_REF,
               PRODUCT_SEQ
        FROM GENEVA_ADMIN.CUSTPRODUCTSTATUS
        WHERE {nbd_where}
        ORDER BY EFFECTIVE_DTM DESC
        """
        if nbd_where
        else None,
        nbd_params if nbd_where else None,
    )

    first_customer_ref = customer_refs[0] if customer_refs else None
    execute_validation(
        results,
        config,
        "RBM analysis",
        "product_start_vs_nbd",
        """
        SELECT TO_CHAR(cpd.START_DAT, 'DD-MON-YY') AS PRODUCT_START,
               TO_CHAR(a.NEXT_BILL_DTM, 'DD-MON-YY') AS NEXT_BILL_DATE,
               CASE
                   WHEN cpd.START_DAT > a.NEXT_BILL_DTM THEN 'NOT YET ELIGIBLE'
                   ELSE 'ELIGIBLE FOR BILLING'
               END AS STATUS,
               cpd.PRODUCT_SEQ,
               cpd.PRODUCT_ID
        FROM GENEVA_ADMIN.CUSTPRODUCTDETAILS cpd
        JOIN GENEVA_ADMIN.ACCOUNT a
          ON SUBSTR(a.ACCOUNT_NUM, 1, INSTR(a.ACCOUNT_NUM, '-') - 1) = cpd.CUSTOMER_REF
        WHERE cpd.CUSTOMER_REF = :customer_ref
        """
        if first_customer_ref
        else None,
        {"customer_ref": first_customer_ref} if first_customer_ref else None,
    )

    if customer_refs:
        discount_params: dict[str, Any] = {}
        discount_filter = build_in_filter("chp.CUSTOMER_REF", customer_refs, "cust_disc", discount_params)
        execute_validation(
            results,
            config,
            "RBM pricing",
            "tariffelementdiscount",
            f"""
            SELECT ted.PRODUCT_ID,
                   ed.DISCOUNT_NAME,
                   ed.DISCOUNT_DESC,
                   ed.ASSESSMENT_EVENT_TYPE_ID,
                   ed.PRIORITY_NUM,
                   ed.PRO_RATING_BOO,
                   eds.EVENT_DISCOUNT_ID,
                   eds.STEP_NUMBER,
                   eds.THRESHOLD,
                   eds.DISCOUNT_PCT,
                   ed.DISC_ACT_THOLD_SET_ID,
                   ed.ASSESSMENT_FILTER_ID,
                   eds.DISC_THRESHOLD_TO_CREATE_OTC,
                   ed.OTC_ID,
                   eds.EXTERNAL_ACTION_ID,
                   eds.LATE_EVENT_CRITERIA,
                   ed.MAX_NUM_BUCKETS,
                   ed.DYNAMIC_DISCOUNT_BOO,
                   ted.START_DAT,
                   ted.END_DAT
            FROM GENEVA_ADMIN.TARIFFELEMENTDISCOUNT ted
            JOIN GENEVA_ADMIN.EVENTDISCOUNT ed
              ON ted.EVENT_DISCOUNT_ID = ed.EVENT_DISCOUNT_ID
            JOIN GENEVA_ADMIN.EVENTDISCOUNTSTEP eds
              ON ed.EVENT_DISCOUNT_ID = eds.EVENT_DISCOUNT_ID
            JOIN GENEVA_ADMIN.CATALOGUECHANGE cc
              ON cc.CATALOGUE_CHANGE_ID = ted.CATALOGUE_CHANGE_ID
            JOIN GENEVA_ADMIN.CUSTHASPRODUCT chp
              ON ted.PRODUCT_ID = chp.PRODUCT_ID
            WHERE ted.END_DAT IS NULL
              AND cc.CATALOGUE_STATUS = 3
              AND ed.CATALOGUE_CHANGE_ID = cc.CATALOGUE_CHANGE_ID
              AND eds.CATALOGUE_CHANGE_ID = cc.CATALOGUE_CHANGE_ID
              AND ed.ASSESSMENT_EVENT_TYPE_ID IN ('1', '7')
              AND {discount_filter}
            """,
            discount_params,
            "Discount configuration for products attached to the selected customer(s).",
        )

    sla_params: dict[str, Any] = {}
    sla_filter = build_in_filter("ACCOUNT_NUM", derived_account_nums, "acct_sla", sla_params)
    execute_validation(
        results,
        config,
        "RBM reference",
        "vzsafeslamtndtl",
        f"SELECT * FROM GENEVA_ADMIN.VZSAFESLAMTNDTL WHERE {sla_filter}" if sla_filter else None,
        sla_params if sla_filter else None,
    )
    execute_validation(
        results,
        config,
        "RBM reference",
        "vzmtndowntimedtls",
        f"SELECT * FROM GENEVA_ADMIN.VZMTNDOWNTIMEDTLS WHERE {sla_filter}" if sla_filter else None,
        sla_params if sla_filter else None,
    )

    scm_params: dict[str, Any] = {}
    scm_filter = build_in_filter("SCM_AUDIT_CD", scm_audit_codes, "scm", scm_params)
    execute_validation(
        results,
        config,
        "RBM content",
        "content_unbilled_event",
        f"SELECT * FROM BCS_CUSTOM.CONTENT_UNBILLED_EVENT WHERE {scm_filter}" if scm_filter else None,
        scm_params if scm_filter else None,
        "Optional. Provide SCM audit code(s) to validate content-unbilled staging tables.",
    )
    execute_validation(
        results,
        config,
        "RBM content",
        "content_unbilled_components",
        f"SELECT * FROM BCS_CUSTOM.CONTENT_UNBILLED_COMPONENTS WHERE {scm_filter}" if scm_filter else None,
        scm_params if scm_filter else None,
    )
    execute_validation(
        results,
        config,
        "RBM content",
        "content_unbilled_lic_actvity",
        f"SELECT * FROM BCS_CUSTOM.CONTENT_UNBILLED_LIC_ACTVITY WHERE {scm_filter}" if scm_filter else None,
        scm_params if scm_filter else None,
    )
    execute_validation(
        results,
        config,
        "RBM content",
        "content_unbilled_svc_dlvr_addr",
        f"SELECT * FROM BCS_CUSTOM.CONTENT_UNBILLED_SVC_DLVR_ADDR WHERE {scm_filter}" if scm_filter else None,
        scm_params if scm_filter else None,
    )

    return results, context_rows


def render_connection_status(config: DbConfig | None, missing: list[str], label: str) -> None:
    with st.container(border=True):
        st.subheader(label)
        if config is None:
            st.error("Missing connection settings")
            st.code("\n".join(missing), language="text")
        else:
            st.success(f"{label} ready")
            st.caption(f"{config.host}:{config.port}/{config.service} as {config.user}")


def main() -> None:
    ensure_authenticated()

    ubsr_config, ubsr_missing = load_db_config("UBSR", "UBSR")
    rbm_config, rbm_missing = load_db_config("RBM", "RBM")

    st.title("Oracle validation workbench")
    render_auth_header()
    st.caption(
        "Run table-level UBSR and RBM validations from one Streamlit UI. "
        "The app expects UBSR_ORACLE_* and RBM_ORACLE_* environment variables or matching values in .env."
    )

    with st.sidebar:
        st.header("Connection status")
        render_connection_status(ubsr_config, ubsr_missing, "UBSR")
        render_connection_status(rbm_config, rbm_missing, "RBM")
        st.info(
            "Required per connection: ORACLE_HOST, ORACLE_PORT, ORACLE_SERVICE, ORACLE_USER, ORACLE_PASSWORD."
        )

    monitor_tab, playbook_tab, ubsr_tab, rbm_tab = st.tabs([
        "Server monitor",
        "Guided playbook",
        "UBSR validations",
        "RBM validations",
    ])

    with monitor_tab:
        render_server_monitor_tab(ubsr_config, rbm_config)

    with playbook_tab:
        render_playbook_tab(ubsr_config, rbm_config)

    with ubsr_tab:
        st.subheader("UBSR validation inputs")
        with st.form("ubsr_form"):
            col1, col2 = st.columns(2)
            customer_ids_raw = col1.text_area("Customer ID(s)", placeholder="Example: 123456789")
            rbm_ids_raw = col2.text_area("RBM ID value(s)", placeholder="Example: RBM00123")

            col3, col4 = st.columns(2)
            target_ids_raw = col3.text_area("Target ID(s)", placeholder="Example: TGT1001")
            mdns_raw = col4.text_area("MDN(s)", placeholder="Example: 5299681440")

            col5, col6, col7 = st.columns(3)
            svc_prod_ids_raw = col5.text_input("Service product ID(s)", placeholder="Optional: 12345, 12346")
            audit_ids_raw = col6.text_input("Audit ID(s)", placeholder="Optional: derive latest if blank")
            recon_cycle = col7.text_input("Recon cycle", value="01")

            run_ubsr = st.form_submit_button("Run UBSR validations", type="primary", icon=":material/play_arrow:")

        if run_ubsr:
            if ubsr_config is None:
                st.error("UBSR connection is not configured.")
            else:
                ubsr_inputs = {
                    "customer_ids": parse_tokens(customer_ids_raw),
                    "rbm_ids": parse_tokens(rbm_ids_raw),
                    "target_ids": parse_tokens(target_ids_raw),
                    "mdns": parse_tokens(mdns_raw),
                    "svc_prod_ids": parse_int_tokens(svc_prod_ids_raw),
                    "audit_ids": parse_tokens(audit_ids_raw),
                    "recon_cycle": recon_cycle.strip() or "01",
                }

                if not any([ubsr_inputs["customer_ids"], ubsr_inputs["rbm_ids"], ubsr_inputs["mdns"]]):
                    st.error("Enter at least one of customer ID, RBM ID value, or MDN.")
                else:
                    with st.spinner("Running UBSR validations..."):
                        results, context_rows = run_with_progress(
                            "UBSR validations",
                            estimate_ubsr_steps(),
                            lambda: run_ubsr_validations(ubsr_config, ubsr_inputs),
                        )
                    render_context_table("Derived UBSR context", context_rows)
                    render_result_blocks(results, "ubsr")

    with rbm_tab:
        st.subheader("RBM validation inputs")
        with st.form("rbm_form"):
            col1, col2 = st.columns(2)
            customer_refs_raw = col1.text_area("Customer ID / CUSTOMER_REF", placeholder="Example: 344400040")
            product_ids_raw = col2.text_area("Product ID(s)", placeholder="Example: 68950, 69055")

            col3, col4 = st.columns(2)
            mtns_raw = col3.text_area("MTN(s)", placeholder="Example: 5445558055, 5449312398")
            account_nums_raw = col4.text_area("Account number(s)", placeholder="Optional: 344400040-1")

            col5, col6, col7 = st.columns(3)
            product_seqs_raw = col5.text_input("Product sequence ID(s)", placeholder="Optional: 1766, 52")
            run_ids_raw = col6.text_input("Run ID(s)", placeholder="Optional conversion run IDs")
            scm_audit_codes_raw = col7.text_input("SCM audit code(s)", placeholder="Optional: 191554")

            run_rbm = st.form_submit_button("Run RBM validations", type="primary", icon=":material/play_arrow:")

        if run_rbm:
            if rbm_config is None:
                st.error("RBM connection is not configured.")
            else:
                rbm_inputs = {
                    "customer_refs": parse_tokens(customer_refs_raw),
                    "product_ids": parse_int_tokens(product_ids_raw),
                    "mtns": parse_tokens(mtns_raw),
                    "account_nums": parse_tokens(account_nums_raw),
                    "product_seqs": parse_int_tokens(product_seqs_raw),
                    "run_ids": parse_int_tokens(run_ids_raw),
                    "scm_audit_codes": parse_tokens(scm_audit_codes_raw),
                }

                if not rbm_inputs["customer_refs"]:
                    st.error("Enter at least one customer ID / CUSTOMER_REF.")
                else:
                    with st.spinner("Running RBM validations..."):
                        results, context_rows = run_with_progress(
                            "RBM validations",
                            estimate_rbm_steps(rbm_inputs),
                            lambda: run_rbm_validations(rbm_config, rbm_inputs),
                        )
                    render_context_table("Derived RBM context", context_rows)
                    render_result_blocks(results, "rbm")


if __name__ == "__main__":
    main()