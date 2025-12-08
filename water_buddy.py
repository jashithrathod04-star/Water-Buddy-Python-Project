import streamlit as st
import sqlite3
from pathlib import Path

# -------------------------------
# DATABASE SETUP
# -------------------------------

DB_PATH = Path("renteasy_db/renteasy.db")

@st.cache_resource
def get_conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    return conn

def setup_db():
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS rentals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_name TEXT NOT NULL,
            description TEXT,
            price REAL NOT NULL,
            contact_info TEXT NOT NULL
        )
    """)
    conn.commit()

# -------------------------------
# ADD RENTAL ITEM
# -------------------------------

def add_rental(item_name, description, price, contact_info):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO rentals (item_name, description, price, contact_info)
        VALUES (?, ?, ?, ?)
    """, (item_name, description, price, contact_info))
    conn.commit()

# -------------------------------
# FETCH RENTALS
# -------------------------------

def fetch_rentals(search_query=""):
    conn = get_conn()
    cursor = conn.cursor()

    if search_query:
        cursor.execute("""
            SELECT * FROM rentals
            WHERE item_name LIKE ? OR description LIKE ?
        """, (f'%{search_query}%', f'%{search_query}%'))
    else:
        cursor.execute("SELECT * FROM rentals")

    return cursor.fetchall()

# -------------------------------
# DELETE RENTAL
# -------------------------------

def delete_rental(item_id):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM rentals WHERE id = ?", (item_id,))
    conn.commit()

# -------------------------------
# STREAMLIT UI
# -------------------------------

def main():
    st.set_page_config(page_title="RentEasy", page_icon="🧰", layout="wide")
    setup_db()

    st.title("🧰 RentEasy")
    st.subheader("List items for rent & find items you need.")

    menu = ["Add Item", "Browse Items", "Delete Item"]
    choice = st.sidebar.selectbox("Menu", menu)

    # ----------------------
    # ADD ITEM PAGE
    # ----------------------
    if choice == "Add Item":
        st.header("📦 Add Your Item for Rent")

        with st.form("add_item_form"):
            item_name = st.text_input("Item Name")
            description = st.text_area("Description")
            price = st.number_input("Rent Price (₹)", min_value=0.0)
            contact_info = st.text_input("Contact Info (Phone / Email)")

            submit_btn = st.form_submit_button("Add Listing")

        if submit_btn:
            if item_name and price > 0 and contact_info:
                add_rental(item_name, description, price, contact_info)
                st.success("✅ Item added successfully!")
            else:
                st.error("❌ Please fill all required fields.")

    # ----------------------
    # BROWSE ITEMS PAGE
    # ----------------------
    elif choice == "Browse Items":
        st.header("🔍 Browse Available Items")

        search = st.text_input("Search items...", placeholder="Search by name or description")
        items = fetch_rentals(search)

        if items:
            for item in items:
                with st.container(border=True):
                    st.markdown(f"### {item[1]}")
                    st.write(item[2])
                    st.write(f"💰 **Price:** ₹{item[3]}")
                    st.write(f"📞 **Contact:** {item[4]}")
        else:
            st.info("No items found.")

    # ----------------------
    # DELETE ITEMS PAGE
    # ----------------------
    elif choice == "Delete Item":
        st.header("🗑 Delete an Item")

        items = fetch_rentals()

        if items:
            item_dict = {f"{item[1]} (₹{item[3]})": item[0] for item in items}
            choice = st.selectbox("Select Item to Delete", list(item_dict.keys()))

            if st.button("Delete"):
                delete_rental(item_dict[choice])
                st.success("🗑 Item deleted successfully!")
        else:
            st.info("No items available to delete.")

# -------------------------------
# RUN APP
# -------------------------------
if __name__ == "__main__":
    main()
