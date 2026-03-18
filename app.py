import streamlit as st
import pandas as pd
import datetime
from supabase import create_client
from reportlab.pdfgen import canvas
from reportlab.graphics.barcode import code128
from reportlab.lib.units import mm
from io import BytesIO

st.set_page_config(page_title="MENOLOGY TRIMS TRACKING SYSTEM", layout="wide")

# ---------------- SESSION ----------------
if "success_msg" not in st.session_state:
    st.session_state.success_msg = ""

if "form_key" not in st.session_state:
    st.session_state.form_key = 0

# ---------------- SUPABASE ----------------
SUPABASE_URL = "https://unmwopzlrlezyurzkbyr.supabase.co"
SUPABASE_KEY = "sb_publishable_HeiJNXkbvn2bdJq3BBA_jA_NGKjje_Z"
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

st.title("MENOLOGY TRIMS TRACKING SYSTEM")

# ---------------- LOAD ----------------
@st.cache_data(ttl=5)
def load_data():
    res = supabase.table("trims_inventory").select("*").execute()
    return pd.DataFrame(res.data)

def load_issue_data():
    res = supabase.table("trims_issue_log").select("*").execute()
    return pd.DataFrame(res.data)

def generate_trim_id(df):
    if df.empty:
        return "TRM0001"
    last = df["trim_id"].iloc[-1]
    return f"TRM{int(last.replace('TRM',''))+1:04d}"

# ---------------- BARCODE ----------------
def create_barcode_pdf(data):
    buffer = BytesIO()

    width = 100 * mm
    height = 60 * mm

    c = canvas.Canvas(buffer, pagesize=(width, height))

    for _, row in data.iterrows():

        trim_id = str(row["trim_id"])
        trim_type = str(row["trim_type"])
        trim_name = str(row["trim_name"])
        size = str(row["size"]) if row["size"] else ""
        order_no = str(row["order_no"])
        qty = str(row["total_qty"])

        c.setFont("Helvetica-Bold", 14)
        c.drawCentredString(width/2, 52*mm, trim_id)

        c.setFont("Helvetica", 10)

        detail = f"{trim_type}"
        if trim_name:
            detail += f" - {trim_name}"
        if size:
            detail += f" - {size}"

        c.drawCentredString(width/2, 45*mm, detail)
        c.drawCentredString(width/2, 39*mm, f"Order: {order_no}")
        c.drawCentredString(width/2, 34*mm, f"Qty: {qty}")

        barcode = code128.Code128(trim_id, barHeight=20*mm, barWidth=0.6)
        barcode.drawOn(c, (width - barcode.width)/2, 8*mm)

        c.showPage()

    c.save()
    return buffer.getvalue()

# ---------------- LOAD DATA ----------------
df = load_data()

# ---------------- SIDEBAR ----------------
page = st.sidebar.selectbox("Navigation", [
    "Dashboard","Add Trim","Issue Trim",
    "Trim Data","Issue Data","Print Barcodes","Delete Trim"
])
# ---------------- DASHBOARD ----------------
if page == "Dashboard":
    st.header("Inventory Dashboard")

    if df.empty:
        st.warning("No data available")
    else:

        # 🔥 LOW STOCK ALERT (LIMIT = 500)
        st.subheader("⚠️Low Stock Alerts (Below 500)")

        low_stock = df[df["balance"] < 500]

        if not low_stock.empty:
            st.dataframe(low_stock[[
                "trim_id","trim_type","trim_name","balance"
            ]].reset_index(drop=True))
        else:
            st.success("No low stock items")

    st.divider()

    # 🔥 ISSUED TODAY
    st.subheader("Issued Today")

    issue_df = load_issue_data()

    if not issue_df.empty:
        issue_df["issued_date"] = pd.to_datetime(issue_df["issued_date"])
        today = datetime.date.today()

        today_data = issue_df[issue_df["issued_date"].dt.date == today]

        if not today_data.empty:
            st.dataframe(today_data.reset_index(drop=True))
        else:
            st.info("No issues today")
    else:
        st.warning("No issue data available")


# ---------------- ADD TRIM ----------------
elif page == "Add Trim":
    st.header("Add Trim")

    if st.session_state.success_msg:
        st.success(st.session_state.success_msg)
        st.session_state.success_msg = ""

    # 🔹 Dynamic dropdown (outside form)
    trim_type = st.selectbox("Select Trims", [
        "Select","Label","Patch","Zip","Washcare","Button",
        "Stopper","W/C","Puler","Rope","Locket",
        "Clip","Sticker","Tape","Eyelet","Other"
    ])

    with st.form(key=f"form_{st.session_state.form_key}"):

        trim_name = st.text_input("Trim Description")

        size = None
        if trim_type == "Label":
            size = st.text_input("Size")

        supplier = st.text_input("Supplier")
        invoice = st.text_input("Invoice Number")
        order = st.text_input("Order Number")
        unit = st.selectbox("Factory Unit", ["Unit 1","Unit 2"])
        qty = st.number_input("Quantity", min_value=0)

        submit = st.form_submit_button("Add")

    if submit:

        if trim_type == "Select":
            st.error("Select trim type")

        else:
            tid = generate_trim_id(df)

            supabase.table("trims_inventory").insert({
                "trim_id": tid,
                "trim_type": trim_type,
                "trim_name": trim_name,
                "size": size,
                "supplier": supplier,
                "invoice_no": invoice,
                "order_no": order,
                "factory_unit": unit,
                "total_qty": int(qty),
                "balance": int(qty),
                "date_added": str(datetime.date.today())
            }).execute()

            st.session_state.success_msg = f"Trim Added: {tid}"
            st.session_state.form_key += 1
            st.rerun()

# ---------------- ISSUE ----------------
elif page == "Issue Trim":
    st.header("Issue Trim")

    code = st.text_input("Scan Trim ID")

    if code in df["trim_id"].values:
        row = df[df["trim_id"] == code].iloc[0]

        st.subheader("Trim Details")

        col1, col2 = st.columns(2)

        with col1:
            st.write("Trim ID:", row["trim_id"])
            st.write("Type:", row["trim_type"])
            st.write("Name:", row["trim_name"])
            st.write("Size:", row["size"])

        with col2:
            st.write("Supplier:", row["supplier"])
            st.write("Invoice:", row["invoice_no"])
            st.write("Order:", row["order_no"])
            st.write("Unit:", row["factory_unit"])
            st.write("Available:", row["balance"])

        qty = st.number_input("Issue Qty", min_value=0)
        to = st.text_input("Issued To")

        if st.button("Issue"):
            if qty <= row["balance"]:

                supabase.table("trims_inventory").update({
                    "balance": int(row["balance"]) - int(qty)
                }).eq("trim_id", code).execute()

                supabase.table("trims_issue_log").insert({
                    "trim_id": row["trim_id"],
                    "trim_type": row["trim_type"],
                    "trim_name": row["trim_name"],
                    "size": row["size"],
                    "order_no": row["order_no"],
                    "factory_unit": row["factory_unit"],
                    "issued_qty": int(qty),
                    "issued_to": to,
                    "issued_date": str(datetime.date.today())
                }).execute()

                st.success("Issued Successfully")
                st.rerun()

# ---------------- TRIM DATA ----------------
elif page == "Trim Data":
    st.header("Trim Data")

    if not df.empty:

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            type_f = st.selectbox("Trim Type", ["All"] + df["trim_type"].dropna().unique().tolist())

        with col2:
            supplier_f = st.selectbox("Supplier", ["All"] + df["supplier"].dropna().unique().tolist())

        with col3:
            order_f = st.selectbox("Order Number", ["All"] + df["order_no"].dropna().unique().tolist())

        with col4:
            unit_f = st.selectbox("Unit", ["All"] + df["factory_unit"].dropna().unique().tolist())

        data = df.copy()

        if type_f != "All":
            data = data[data["trim_type"] == type_f]

        if supplier_f != "All":
            data = data[data["supplier"] == supplier_f]

        if order_f != "All":
            data = data[data["order_no"] == order_f]

        if unit_f != "All":
            data = data[data["factory_unit"] == unit_f]

        data["Display"] = data["trim_type"] + " - " + data["trim_name"].fillna("") + " - " + data["size"].fillna("")

        st.dataframe(data[[
            "trim_id","Display","supplier","invoice_no",
            "order_no","factory_unit","total_qty","balance"
        ]].reset_index(drop=True))

# ---------------- ISSUE DATA ----------------
elif page == "Issue Data":
    st.header("Issue Data")

    issue_df = load_issue_data()
    if not issue_df.empty:
        st.dataframe(issue_df.reset_index(drop=True))

# ---------------- PRINT ----------------
elif page == "Print Barcodes":
    st.header("Print Barcodes")

    mode = st.radio("Mode", ["Order Wise","Individual"])

    if mode == "Order Wise":
        orders = df["order_no"].dropna().unique()
        sel = st.selectbox("Order", orders)

        if st.button("Generate"):
            pdf = create_barcode_pdf(df[df["order_no"] == sel])
            st.download_button("Download", pdf, f"{sel}.pdf")

    else:
        tid = st.selectbox("Trim ID", df["trim_id"])

        if st.button("Generate"):
            pdf = create_barcode_pdf(df[df["trim_id"] == tid])
            st.download_button("Download", pdf, f"{tid}.pdf")

# ---------------- DELETE ----------------
elif page == "Delete Trim":
    st.header("Delete Trim")

    tid = st.selectbox("Trim ID", df["trim_id"])

    if st.button("Delete"):
        supabase.table("trims_inventory").delete().eq("trim_id", tid).execute()
        st.success("Deleted")
        st.rerun()
