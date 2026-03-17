import streamlit as st
import pandas as pd
import datetime
from supabase import create_client
from reportlab.pdfgen import canvas
from reportlab.graphics.barcode import code128
from reportlab.lib.units import mm
from io import BytesIO

# ---------------- CONFIG ----------------
st.set_page_config(page_title="MENOLOGY TRIMS TRACKING SYSTEM", layout="wide")

# ---------------- SESSION STATE ----------------
if "success_msg" not in st.session_state:
    st.session_state.success_msg = ""

# ---------------- SUPABASE ----------------
SUPABASE_URL = "https://unmwopzlrlezyurzkbyr.supabase.co"
SUPABASE_KEY = "sb_publishable_HeiJNXkbvn2bdJq3BBA_jA_NGKjje_Z"

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ---------------- HEADER ----------------
col1, col2 = st.columns([8,1])

with col1:
    st.title("MENOLOGY TRIMS TRACKING SYSTEM")

with col2:
    st.image("logo.webp", width=120)

# ---------------- LOAD DATA ----------------
def load_data():
    response = supabase.table("trims").select("*").execute()
    df = pd.DataFrame(response.data)

    if df.empty:
        return pd.DataFrame(columns=[
            "trim_id","trim_name","supplier","lot",
            "factory_unit","total_qty","balance","date_added"
        ])
    return df

def load_issue_data():
    response = supabase.table("issues").select("*").execute()
    df = pd.DataFrame(response.data)

    if df.empty:
        return pd.DataFrame(columns=[
            "trim_id","trim_name","lot",
            "factory_unit","issued_qty","issued_to","issued_date"
        ])
    return df

# ---------------- GENERATE TRIM ID ----------------
def generate_trim_id(df):
    if df.empty:
        return "TRM0001"
    last_id = df["trim_id"].iloc[-1]
    num = int(last_id.replace("TRM", "")) + 1
    return f"TRM{num:04d}"

# ---------------- BARCODE PDF ----------------
def create_barcode_pdf(data):

    buffer = BytesIO()
    width = 60 * mm
    height = 40 * mm

    c = canvas.Canvas(buffer, pagesize=(width, height))

    for _, row in data.iterrows():

        trim_id = str(row["trim_id"])
        lot = str(row["lot"])
        qty = str(row["total_qty"])

        c.setFont("Helvetica-Bold", 9)
        c.drawCentredString(width/2, 32*mm, trim_id)

        c.setFont("Helvetica", 8)
        c.drawCentredString(width/2, 27*mm, f"Lot: {lot}")
        c.drawCentredString(width/2, 23*mm, f"Qty: {qty}")

        barcode = code128.Code128(trim_id, barHeight=12*mm, barWidth=0.45)
        barcode_x = (width - barcode.width) / 2
        barcode.drawOn(c, barcode_x, 8*mm)

        c.showPage()

    c.save()
    pdf_bytes = buffer.getvalue()
    buffer.close()

    return pdf_bytes

# ---------------- LOAD ----------------
df = load_data()

# ---------------- SIDEBAR ----------------
st.sidebar.title("Navigation")

page = st.sidebar.selectbox(
    "Go to",
    ["Dashboard", "Add Trim", "Issue Trim", "Trim Data", "Issue Data", "Print Barcodes", "Delete Trim"]
)

# ---------------- DASHBOARD ----------------
if page == "Dashboard":

    st.header("Inventory Dashboard")

    # Supplier Contribution
    st.subheader("Supplier-wise Stock Contribution")

    if not df.empty:
        supplier_data = df.groupby("supplier")["balance"].sum().sort_values(ascending=False)
        st.bar_chart(supplier_data)
    else:
        st.warning("No trim data available")

    # Issued Today
    st.subheader("Issued Today")

    issue_df = load_issue_data()

    if not issue_df.empty:
        issue_df["issued_date"] = pd.to_datetime(issue_df["issued_date"], errors="coerce")
        today = datetime.date.today()

        today_issues = issue_df[issue_df["issued_date"].dt.date == today]

        if today_issues.empty:
            st.info("No issues recorded today")
        else:
            st.dataframe(today_issues, use_container_width=True)
    else:
        st.warning("No issue data available")

# ---------------- ADD TRIM ----------------
elif page == "Add Trim":

    st.header("Add Trim")

    # Show success message AFTER rerun
    if st.session_state.success_msg:
        st.success(st.session_state.success_msg)
        st.session_state.success_msg = ""

    trim_name = st.text_input("Trim Name")
    supplier = st.text_input("Supplier")
    lot = st.text_input("Lot")
    factory_unit = st.selectbox("Factory Unit", ["Unit 10", "Unit 16"])
    qty = st.number_input("Quantity", min_value=0)

    if st.button("Add Trim"):

        trim_id = generate_trim_id(df)

        supabase.table("trims").insert({
            "trim_id": trim_id,
            "trim_name": trim_name,
            "supplier": supplier,
            "lot": lot,
            "factory_unit": factory_unit,
            "total_qty": int(qty),
            "balance": int(qty),
            "date_added": str(datetime.date.today())
        }).execute()

        st.session_state.success_msg = f"Trim Added Successfully: {trim_id}"
        st.rerun()

# ---------------- ISSUE TRIM ----------------
elif page == "Issue Trim":

    st.header("Issue Trim")

    barcode_input = st.text_input("Scan Trim ID")

    if not df.empty and barcode_input in df["trim_id"].values:

        trim = df[df["trim_id"] == barcode_input].iloc[0]

        st.write("Trim Name:", trim["trim_name"])
        st.write("Lot:", trim["lot"])
        st.write("Available:", trim["balance"])

        issue_qty = st.number_input("Issue Quantity", min_value=0)
        issued_to = st.text_input("Issued To (Line / Department / Person)")

        if st.button("Issue"):

            if issue_qty <= trim["balance"]:

                if issued_to.strip() == "":
                    st.error("Please enter Issued To")

                else:
                    issued_to = issued_to.strip().title()

                    new_balance = int(trim["balance"]) - int(issue_qty)

                    supabase.table("trims").update({
                        "balance": new_balance
                    }).eq("trim_id", barcode_input).execute()

                    supabase.table("issues").insert({
                        "trim_id": trim["trim_id"],
                        "trim_name": trim["trim_name"],
                        "lot": trim["lot"],
                        "factory_unit": trim["factory_unit"],
                        "issued_qty": int(issue_qty),
                        "issued_to": issued_to,
                        "issued_date": str(datetime.date.today())
                    }).execute()

                    st.success(f"Issued to {issued_to}")
                    st.rerun()

            else:
                st.error("Not enough stock")

# ---------------- TRIM DATA ----------------
elif page == "Trim Data":

    st.header("Trim Inventory Data")

    if df.empty:
        st.warning("No trim data available")
    else:

        col1, col2, col3 = st.columns(3)

        with col1:
            trim_filter = st.selectbox(
                "Filter by Trim Name",
                ["All"] + df["trim_name"].dropna().unique().tolist()
            )

        with col2:
            supplier_filter = st.selectbox(
                "Filter by Supplier",
                ["All"] + df["supplier"].dropna().unique().tolist()
            )

        with col3:
            unit_filter = st.selectbox(
                "Filter by Factory Unit",
                ["All"] + df["factory_unit"].dropna().unique().tolist()
            )

        filtered_df = df.copy()

        if trim_filter != "All":
            filtered_df = filtered_df[filtered_df["trim_name"] == trim_filter]

        if supplier_filter != "All":
            filtered_df = filtered_df[filtered_df["supplier"] == supplier_filter]

        if unit_filter != "All":
            filtered_df = filtered_df[filtered_df["factory_unit"] == unit_filter]

        st.dataframe(filtered_df, use_container_width=True)

# ---------------- ISSUE DATA ----------------
elif page == "Issue Data":

    st.header("Issued Trim History")

    issue_df = load_issue_data()

    if issue_df.empty:
        st.warning("No issue history available")
    else:

        col1, col2, col3 = st.columns(3)

        with col1:
            trim_filter = st.selectbox("Trim", ["All"] + issue_df["trim_name"].dropna().unique().tolist())

        with col2:
            lot_filter = st.selectbox("Lot", ["All"] + issue_df["lot"].dropna().unique().tolist())

        with col3:
            issued_to_filter = st.selectbox("Issued To", ["All"] + issue_df["issued_to"].dropna().unique().tolist())

        filtered_df = issue_df.copy()

        if trim_filter != "All":
            filtered_df = filtered_df[filtered_df["trim_name"] == trim_filter]

        if lot_filter != "All":
            filtered_df = filtered_df[filtered_df["lot"] == lot_filter]

        if issued_to_filter != "All":
            filtered_df = filtered_df[filtered_df["issued_to"] == issued_to_filter]

        st.dataframe(filtered_df, use_container_width=True)

# ---------------- PRINT BARCODES ----------------
elif page == "Print Barcodes":

    st.header("Print Lot Barcodes")

    if not df.empty:

        lots = df["lot"].dropna().unique().tolist()
        selected_lot = st.selectbox("Select Lot", lots)

        lot_data = df[df["lot"] == selected_lot]

        if st.button("Generate Lot Barcode PDF"):

            pdf_bytes = create_barcode_pdf(lot_data)

            st.download_button(
                "Download Barcode Labels",
                data=pdf_bytes,
                file_name=f"{selected_lot}_labels.pdf",
                mime="application/pdf"
            )

# ---------------- DELETE ----------------
elif page == "Delete Trim":

    st.header("Delete Trim")

    if not df.empty:

        trim_id = st.selectbox("Select Trim ID", df["trim_id"])

        if st.button("Delete Trim"):

            supabase.table("trims").delete().eq("trim_id", trim_id).execute()

            st.success("Trim Deleted Successfully")
            st.rerun()
