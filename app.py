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
    ["Dashboard", "Add Trim", "Issue Trim", "Trim Data", "Print Barcodes", "Delete Trim"]
)

# ---------------- DASHBOARD ----------------
if page == "Dashboard":

    st.header("Inventory Dashboard")

    col1, col2 = st.columns(2)

    with col1:
        st.metric("Total Trim Types", len(df))

    with col2:
        total_stock = df["balance"].sum() if not df.empty else 0
        st.metric("Total Stock Available", int(total_stock))

    # Today’s trims
    st.subheader("Trims Added Today")

    if not df.empty:
        df["date_added"] = pd.to_datetime(df["date_added"], errors="coerce")
        today = datetime.date.today()

        today_trims = df[df["date_added"].dt.date == today]

        st.dataframe(today_trims)

    # Low stock
    st.subheader("Low Stock (Below 50)")

    if not df.empty:
        low_stock = df[df["balance"] < 50]
        st.dataframe(low_stock)

    # Supplier graph
    st.subheader("Supplier Contribution")

    if not df.empty:
        supplier_data = df.groupby("supplier")["balance"].sum()
        st.bar_chart(supplier_data)

# ---------------- ADD TRIM ----------------
elif page == "Add Trim":

    st.header("Add Trim")

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

        st.success(f"Trim Added: {trim_id}")
        st.rerun()

# ---------------- ISSUE TRIM ----------------
elif page == "Issue Trim":

    st.header("Issue Trim")

    barcode_input = st.text_input("Scan Trim ID")

    if not df.empty and barcode_input in df["trim_id"].values:

        trim = df[df["trim_id"] == barcode_input].iloc[0]

        st.write("Trim Name:", trim["trim_name"])
        st.write("Supplier:", trim["supplier"])
        st.write("Lot:", trim["lot"])
        st.write("Factory Unit:", trim["factory_unit"])
        st.write("Available:", trim["balance"])

        issue_qty = st.number_input("Issue Quantity", min_value=0)

        if st.button("Issue"):

            if issue_qty <= trim["balance"]:

                new_balance = int(trim["balance"]) - int(issue_qty)

                supabase.table("trims").update({
                    "balance": new_balance
                }).eq("trim_id", barcode_input).execute()

                st.success("Trim Issued Successfully")
                st.rerun()

            else:
                st.error("Not enough stock")

# ---------------- TRIM DATA ----------------
elif page == "Trim Data":

    st.header("Trim Inventory Data")

    if not df.empty:

        trim_filter = st.selectbox(
            "Filter by Trim Name",
            ["All"] + df["trim_name"].dropna().unique().tolist()
        )

        supplier_filter = st.selectbox(
            "Filter by Supplier",
            ["All"] + df["supplier"].dropna().unique().tolist()
        )

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

        st.dataframe(filtered_df)

# ---------------- PRINT BARCODES ----------------
elif page == "Print Barcodes":

    st.header("Print Lot Barcodes")

    if not df.empty:

        lots = df["lot"].dropna().unique().tolist()

        selected_lot = st.selectbox("Select Lot", lots)

        lot_data = df[df["lot"] == selected_lot]

        st.dataframe(lot_data)

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
