import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import os

st.set_page_config(page_title="Lumpsum Return Scanner", layout="wide")

def load_lumpsum_data(uploaded_file):
    if uploaded_file is not None:
        try:
            # Lumpsum data usually starts from row 5 (header=4) based on exploration
            if uploaded_file.name.endswith('.xls'):
                df = pd.read_excel(uploaded_file, engine='xlrd', header=4)
            else:
                df = pd.read_excel(uploaded_file, engine='openpyxl', header=4)
            return df
        except Exception as e:
            st.error(f"Error loading file: {e}")
            return None
    return None

def format_currency(val):
    if pd.isna(val):
        return "-"
    try:
        return f"{int(val):,}"
    except:
        return val

def format_percentage(val):
    if pd.isna(val):
        return "-"
    try:
        return f"{val:.2f}%"
    except:
        return val

def clean_scheme_name(name):
    if not isinstance(name, str):
        return name
    
    # Remove common suffixes
    # Order matters: longer ones first
    suffixes = ["Reg Gr", "Gr Gr", "Dir Gr", "Reg IDCW", "Dir IDCW", "Reg", "Gr", "Growth", "Direct"]
    
    for _ in range(3): # Try removing up to 3 suffixes
        found = False
        for suffix in suffixes:
            if name.endswith(" " + suffix) or name.endswith("-" + suffix):
                name = name[:-len(suffix)-1].strip()
                found = True
                break
            elif name.endswith(suffix):
                name = name[:-len(suffix)].strip()
                found = True
                break
        if not found:
            break
            
    # If it doesn't end with "Fund", append " Fund"
    if not name.lower().endswith(" fund"):
        name += " Fund"
        
    return name

st.title("💰 Lumpsum Return Scanner")

# Sidebar for settings
with st.sidebar:
    st.header("Settings")
    uploaded_file = st.file_uploader("Upload Lumpsum Excel File", type=["xls", "xlsx"])
    
    persistent_file = "last_updated_lumpsum_data.xls"
    
    # Logic to keep the last updated file
    if uploaded_file is not None:
        # Save the uploaded file locally to persist it
        with open(persistent_file, "wb") as f:
            f.write(uploaded_file.getbuffer())
        st.success("File uploaded and saved as default!")
        df = load_lumpsum_data(uploaded_file)
    else:
        # If no file is uploaded, try the last saved persistent file first
        if os.path.exists(persistent_file):
            try:
                df = pd.read_excel(persistent_file, engine='xlrd', header=4)
                st.info("Using last updated data.")
            except:
                df = None
        
        # Fallback to original default file if no persistent file or if loading failed
        if df is None:
            default_path = "Trailing-returns.xls"
            if os.path.exists(default_path):
                try:
                    df = pd.read_excel(default_path, engine='xlrd', header=4)
                    st.info(f"Using default file: {default_path}")
                except Exception as e:
                    df = None
                    st.error(f"Error loading default file: {e}")
        
        if df is None:
            st.warning("Please upload an Excel file.")

    if df is not None:
        lumpsum_amount = st.number_input("Enter Lumpsum Amount (₹)", min_value=1000, value=100000, step=1000)
        view_mode = st.radio("Select View Mode", ["Single Fund View", "Top Funds View"])

if df is not None:
    # Clean up column names (remove extra spaces)
    df.columns = [c.strip() for c in df.columns]
    
    # Clean up scheme names
    if 'Scheme Name' in df.columns:
        df['Scheme Name'] = df['Scheme Name'].apply(clean_scheme_name)
    
    if view_mode == "Single Fund View":
        st.header("🎯 Single Fund Lumpsum Analysis")
        
        fund_name = st.selectbox("Select Fund Name", df['Scheme Name'].dropna().unique())
        fund_data = df[df['Scheme Name'] == fund_name].iloc[0]
        
        # Dynamically detect available durations from columns containing 'Rtn (%)'
        # e.g., '3 Yrs Rtn (%)' -> '3 Year'
        available_rtn_cols = [c for c in df.columns if isinstance(c, str) and "Rtn (%)" in c]
        duration_map = {}
        for col in available_rtn_cols:
            years_str = col.split(' ')[0] # e.g., '3'
            if years_str.isdigit():
                duration_map[f"{years_str} Year"] = col
        
        # Sort duration map keys numerically
        sorted_keys = sorted(duration_map.keys(), key=lambda x: int(x.split(' ')[0]))
        selected_durations = st.multiselect("Select Durations", sorted_keys, default=sorted_keys)
        
        st.subheader(f"📈 {fund_name}")
        st.write(f"Growth of ₹{lumpsum_amount:,} Lumpsum Investment")
        
        # Fund-level metrics (Alpha, Beta, etc.)
        fund_metrics = [
            'Alpha', 'Beta', 'Sharpe Ratio', 'Standard Deviation', 'YTM', 
            'Average Maturity', 'Sortino Ratio', 'CY Quartile Rank', 
            'PY Quartile Rank', 'R-Squared', 'Information Ratio', 
            'Up Market Capture Ratio', 'Down Market Capture Ratio'
        ]
        available_fund_metrics = [m for m in fund_metrics if m in fund_data.index and not pd.isna(fund_data[m])]
        
        table_rows = []
        for label in selected_durations:
            col = duration_map[label]
            if col in fund_data:
                ret_pct = fund_data[col]
                if not pd.isna(ret_pct):
                    try:
                        # Calculation: Amount * (1 + return_pct/100)^years
                        years = int(label.split(' ')[0])
                        current_val = lumpsum_amount * ((1 + (ret_pct / 100)) ** years)
                        
                        row = {
                            "DURATION": label.upper(),
                            "INVESTED AMOUNT": lumpsum_amount,
                            "CURRENT VALUE": current_val,
                            "CAGR %": ret_pct
                        }
                        # Add fund metrics to each row
                        for m in available_fund_metrics:
                            row[m] = fund_data[m]
                        table_rows.append(row)
                    except:
                        continue
        
        if table_rows:
            display_df = pd.DataFrame(table_rows)
            
            # Selectable columns
            all_cols = display_df.columns.tolist()
            # Default columns are the main growth ones
            default_cols = ["DURATION", "INVESTED AMOUNT", "CURRENT VALUE", "CAGR %"]
            selected_cols = st.multiselect("Select columns to display", all_cols, default=[c for c in default_cols if c in all_cols])
            
            if selected_cols:
                formatted_df = display_df[selected_cols].copy()
                for col in formatted_df.columns:
                    if col == "INVESTED AMOUNT" or col == "CURRENT VALUE":
                        formatted_df[col] = formatted_df[col].apply(format_currency)
                    elif col == "CAGR %" or col in fund_metrics:
                        formatted_df[col] = formatted_df[col].apply(format_percentage)
                
                st.dataframe(formatted_df, use_container_width=True)
        else:
            st.warning("No return data available for this fund.")

        # Footer info
        today_str = datetime.now().strftime("%d %b %Y")
        st.markdown(f"**AS ON {today_str}**")
        
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("🔴 **Subscribe**")
        with col2:
            st.markdown("🟢 **9047268800**")
        st.caption("Mutual Fund investments are subject to market risks...")

    elif view_mode == "Top Funds View":
        st.header("🏆 Top Lumpsum Performers")
        
        col1, col2 = st.columns(2)
        with col1:
            top_n = st.number_input("Select Top N", min_value=1, max_value=len(df), value=5, step=1)
        with col2:
            # Sort metrics: CAGR columns, Alpha, and other requested metrics
            requested_metrics = [
                'Alpha', 'Beta', 'Sharpe Ratio', 'Standard Deviation', 'YTM', 
                'Average Maturity', 'Sortino Ratio', 'CY Quartile Rank', 
                'PY Quartile Rank', 'R-Squared', 'Information Ratio', 
                'Up Market Capture Ratio', 'Down Market Capture Ratio'
            ]
            
            # Combine return columns with requested metrics
            base_metrics = [c for c in df.columns if "Rtn (%)" in c]
            metric_options = base_metrics + [m for m in requested_metrics if m in df.columns]
            
            sort_metric = st.selectbox("Sort by Metric", metric_options, index=metric_options.index("3 Yrs Rtn (%)") if "3 Yrs Rtn (%)" in metric_options else 0)
            
        # Fix: Ensure sort metric column is numeric to avoid 'TypeError'
        df_sorted = df.copy()
        df_sorted[sort_metric] = pd.to_numeric(df_sorted[sort_metric], errors='coerce')
        
        # Determine sort order: Smallest to Largest for risk metrics (Beta, SD), Largest to Smallest for others
        is_ascending = sort_metric in ['Beta', 'Standard Deviation', 'Down Market Capture Ratio']
        top_funds = df_sorted.sort_values(by=sort_metric, ascending=is_ascending).head(top_n).copy()
        
        # Calculate growth for the sorted metric if it's a duration
        if "Rtn (%)" in sort_metric:
            try:
                # Try to extract years from column name like "3 Yrs Rtn (%)"
                years_str = sort_metric.split(' ')[0]
                if years_str.isdigit():
                    years = int(years_str)
                    top_funds[f'Value of ₹{lumpsum_amount:,}'] = top_funds[sort_metric].apply(
                        lambda x: lumpsum_amount * ((1 + (x / 100)) ** years) if not pd.isna(x) else np.nan
                    )
            except:
                pass

        # Selectable columns: Category first, then Scheme Name, then metrics
        default_display_cols = ['Category', 'Scheme Name', sort_metric]
        if f'Value of ₹{lumpsum_amount:,}' in top_funds.columns:
            default_display_cols.append(f'Value of ₹{lumpsum_amount:,}')
            
        other_cols = [c for c in df.columns if c not in default_display_cols]
        selected_display_cols = st.multiselect("Select additional columns", other_cols, default=[])
        
        final_cols = default_display_cols + selected_display_cols
        
        # Formatting
        formatted_top = top_funds[final_cols].copy()
        for col in final_cols:
            if "Rtn (%)" in col or "Alpha" in col or col in requested_metrics:
                formatted_top[col] = formatted_top[col].apply(format_percentage)
            elif "Value of" in col or "AUM" in col:
                formatted_top[col] = formatted_top[col].apply(format_currency)

        st.dataframe(formatted_top, use_container_width=True)

else:
    st.info("Please upload an Excel file or ensure 'Trailing-returns.xls' exists.")
