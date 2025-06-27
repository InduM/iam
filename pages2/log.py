import streamlit as st
from utils.utils_login import is_logged_in
from datetime import datetime, date
from backend.log_backend import LogBackend
from utils.utils_log import (
    create_default_log, get_date_constraints, can_add_log_for_date,
    initialize_session_state, ensure_log_fields, get_log_columns,
    get_category_options, get_priority_options, get_status_options,
    format_log_summary, display_spoc_info
)


def render_date_controls(backend, username):
    """Render date picker and control buttons"""
    date_constraints = get_date_constraints()
    default_date = date_constraints["today"]
    
    col1, col2, col3 = st.columns([5, 1, 2])
    
    with col1:
        selected_date = st.date_input(
            "Select Date", 
            value=default_date, 
            key="selected_date", 
            label_visibility="collapsed"
        )
        can_add = can_add_log_for_date(selected_date)

    with col2:
        st.button(
            "➕ Log", 
            on_click=lambda: st.session_state.logs.append(create_default_log()), 
            disabled=not can_add
        )

    with col3:
        def refresh_logs():
            with st.spinner("Refreshing logs..."):
                selected_date_str = selected_date.strftime("%Y-%m-%d")
                fetched_logs = backend.fetch_logs(selected_date_str, username)
                st.session_state.logs = []
                
                for log in fetched_logs:
                    st.session_state.logs.append(ensure_log_fields(log))
                
                if not st.session_state.logs:
                    st.session_state.logs.append(create_default_log())
                
                st.session_state.last_selected_date = selected_date
                st.session_state.refresh_triggered = False

        if st.button("🔄 Refresh") and not st.session_state.refresh_triggered:
            st.session_state.refresh_triggered = True
            refresh_logs()

    return selected_date


def render_input_field(col_widget, field, log, widget_key, user_projects, client_names, client_dict):
    """Render individual input field based on field type"""
    if field == "Time":
        log_time = datetime.strptime(log[field], "%H:%M").time() if isinstance(log[field], str) else log.get(field, datetime.now().time())
        new_time = col_widget.time_input("Time", value=log_time, key=widget_key)
        log[field] = new_time.strftime("%H:%M")

    elif field == "Priority":
        options = get_priority_options()
        idx = options.index(log[field]) if log[field] in options else 0
        log[field] = col_widget.selectbox("Priority", options=options, index=idx, key=widget_key)

    elif field == "Category":
        options = get_category_options()
        idx = options.index(log[field]) if log[field] in options else 0
        selected = col_widget.selectbox("Category", options=options, index=idx, key=widget_key)
        if selected == "Other":
            custom = col_widget.text_input("Specify Other Category", key=widget_key + "_custom")
            log[field] = custom
        else:
            log[field] = selected

    elif field == "Status":
        options = get_status_options()
        idx = options.index(log[field]) if log[field] in options else 0
        log[field] = col_widget.selectbox("Status", options=options, index=idx, key=widget_key)

    elif field == "Client Name":
        options = [""] + client_names
        idx = options.index(log[field]) if log[field] in options else 0
        selected_client = col_widget.selectbox("Client Name", options=options, index=idx, key=widget_key, on_change=None)
        log[field] = selected_client
        
        # Display SPOC information
        display_spoc_info(col_widget, client_dict, selected_client)

    elif field == "Project Name":
        options = [""] + user_projects
        idx = options.index(log[field]) if log[field] in options else 0
        log[field] = col_widget.selectbox("Project Name", options=options, index=idx, key=widget_key)

    else:
        log[field] = col_widget.text_area(field, value=log[field], key=widget_key)


def render_log_table(backend, username, selected_date, user_projects, client_names, client_dict):
    """Render the main log table with all entries"""
    log_columns = get_log_columns()
    
    def delete_log_row(index):
        log_to_delete = st.session_state.logs[index]
        selected_date_str = selected_date.strftime("%Y-%m-%d")
        backend.delete_log(selected_date_str, username, log_to_delete["Time"])
        del st.session_state.logs[index]

    with st.container():
        st.markdown('<div class="scroll-container"><div class="block-container">', unsafe_allow_html=True)
        
        for i, log in enumerate(st.session_state.logs):
            log["Time"] = datetime.now().strftime("%H:%M")
            summary = format_log_summary(log)
            
            with st.expander(f"Log Entry {i+1} — {summary}", expanded=True):
                col_left, col_right = st.columns(2)

                # Split fields between columns
                for j, (field, _) in enumerate(log_columns):
                    if field == "Time":
                        continue  # Hide from UI but keep in DB
                    
                    target_col = col_left if j % 2 == 0 else col_right
                    render_input_field(
                        target_col, field, log, f"{field}_{i}", 
                        user_projects, client_names, client_dict
                    )

                st.button(
                    "🗑️ Delete this log", 
                    key=f"delete_{i}", 
                    on_click=lambda idx=i: delete_log_row(idx)
                )


def handle_date_change(backend, username, selected_date):
    """Handle date change and fetch logs for new date"""
    if st.session_state.last_selected_date != selected_date:
        selected_date_str = selected_date.strftime("%Y-%m-%d")
        fetched_logs = backend.fetch_logs(selected_date_str, username)
        
        st.session_state.logs = []
        for log in fetched_logs:
            st.session_state.logs.append(ensure_log_fields(log))
        
        if not st.session_state.logs:
            st.session_state.logs.append(create_default_log())
        
        st.session_state.last_selected_date = selected_date


def render_save_button(backend, username, selected_date):
    """Render save button and handle save operation"""
    if st.button("💾 Save"):
        selected_date_str = selected_date.strftime("%Y-%m-%d")
        if backend.save_logs(selected_date_str, username, st.session_state.logs):
            st.success("Logs saved to MongoDB successfully!")


@st.cache_data(ttl=300)  # Cache for 5 minutes to improve performance
def get_cached_client_data():
    """Get cached client data"""
    backend = LogBackend()
    return backend.get_client_data()


def run():
    """Main function to run the log application"""
    # Login check
    if not is_logged_in():
        st.switch_page("option.py")

    # Initialize
    username = st.session_state["username"]
    backend = LogBackend()
    initialize_session_state()

    # Get data
    client_names, client_dict = get_cached_client_data()
    user_projects = backend.get_user_projects(username)

    # Render UI components
    selected_date = render_date_controls(backend, username)
    handle_date_change(backend, username, selected_date)
    render_log_table(backend, username, selected_date, user_projects, client_names, client_dict)
    render_save_button(backend, username, selected_date)