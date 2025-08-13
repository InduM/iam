import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, DataReturnMode


class DeadlineComponents:
    def __init__(self, log_manager):
        self.log_manager = log_manager

    def render_deadline_tab(self):
        """Render deadline extension requests management tab"""
        st.subheader("⏰ Deadline Extension Requests")
        
        # Get pending extension requests
        extension_requests = self.log_manager.get_deadline_extension_requests()
        
        if not extension_requests:
            st.info("📭 No pending deadline extension requests")
            return
        
        st.write(f"**{len(extension_requests)} pending request(s)**")
        
        # Create DataFrame
        df_requests = pd.DataFrame([
            {
                "Project": req["project_name"],
                "Stage": req["stage_name"],
                "Substage": req["substage_name"],
                "Assigned User": req["assigned_user"],
                "Current Deadline": self._format_date(req.get("substage_deadline", req.get("stage_deadline"))),
                "Requested By": req["extension_requested_by"],
                "Requested At": self._format_datetime(req["extension_requested_at"]),
                "Reason": req["extension_reason"][:50] + "..." if len(req["extension_reason"]) > 50 else req["extension_reason"],
                "ID": str(req["_id"])
            }
            for req in extension_requests
        ])
        
        # Grid with filters + multiple selection
        gb = GridOptionsBuilder.from_dataframe(df_requests.drop('ID', axis=1))
        gb.configure_pagination(paginationAutoPageSize=True)
        gb.configure_default_column(editable=False, filter=True, sortable=True, resizable=True)
        gb.configure_selection('multiple', use_checkbox=True)
        gb.configure_column("Reason", wrapText=True, autoHeight=True)
        gridOptions = gb.build()
        
        grid_response = AgGrid(
            df_requests.drop('ID', axis=1),
            gridOptions=gridOptions,
            height=400,
            fit_columns_on_grid_load=True,
            update_mode=GridUpdateMode.SELECTION_CHANGED,
            data_return_mode=DataReturnMode.FILTERED_AND_SORTED,
            key="deadline_requests_grid"
        )
        
        # Get selected rows
        selected_rows = grid_response.get('selected_rows', [])
        if isinstance(selected_rows, pd.DataFrame):
            selected_rows = selected_rows.to_dict('records')
        
        if selected_rows:
            selected_ids = []
            for row in selected_rows:
                match = df_requests[
                    (df_requests["Project"] == row["Project"]) &
                    (df_requests["Stage"] == row["Stage"]) &
                    (df_requests["Substage"] == row["Substage"]) &
                    (df_requests["Assigned User"] == row["Assigned User"])
                ]
                if not match.empty:
                    selected_ids.append(match.iloc[0]["ID"])

            st.markdown(f"**{len(selected_ids)} request(s) selected**")

            col1, col2 = st.columns(2)

            # ✅ Bulk Approve Section
            with col1:
                st.subheader("✅ Bulk Approve Selected")
                new_deadline = st.date_input(
                    "New Deadline for all selected:",
                    value=datetime.now().date() + timedelta(days=7),
                    min_value=datetime.now().date()
                )
                approval_notes = st.text_area(
                    "Approval Notes (Optional):",
                    placeholder="Enter approval notes for all selected requests"
                )
                if st.button("✅ Approve Selected"):
                    for req_id in selected_ids:
                        self.log_manager.approve_deadline_extension(
                            req_id, new_deadline,
                            st.session_state.get("username", "Admin"),
                            approval_notes
                        )
                    st.success(f"✅ Approved {len(selected_ids)} request(s)!")
                    st.rerun()

            # ❌ Bulk Reject Section
            with col2:
                st.subheader("❌ Bulk Reject Selected")
                rejection_notes = st.text_area(
                    "Rejection Reason (Required):",
                    placeholder="Enter rejection reason for all selected requests"
                )
                if st.button("❌ Reject Selected"):
                    if not rejection_notes.strip():
                        st.error("❌ Please provide a rejection reason.")
                    else:
                        for req_id in selected_ids:
                            self.log_manager.reject_deadline_extension(
                                req_id, st.session_state.get("username", "Admin"),
                                rejection_notes
                            )
                        st.success(f"❌ Rejected {len(selected_ids)} request(s)!")
                        st.rerun()

    def _render_extension_approval_form(self, request):
        """Render form to approve/reject deadline extension"""
        with st.expander("📋 Extension Request Details", expanded=True):
            col1, col2 = st.columns([2, 1])
            
            with col1:
                st.write(f"**Project:** {request['project_name']}")
                st.write(f"**Stage:** {request['stage_name']} → {request['substage_name']}")
                st.write(f"**Assigned User:** {request['assigned_user']}")
                st.write(f"**Current Deadline:** {self._format_date(request.get('substage_deadline', request.get('stage_deadline')))}")
                st.write(f"**Requested By:** {request['extension_requested_by']}")
                st.write(f"**Requested At:** {self._format_datetime(request['extension_requested_at'])}")
            
            with col2:
                st.write("**Extension Reason:**")
                st.write(f"*{request['extension_reason']}*")
            
            st.markdown("---")
            
            # Approval form
            col1, col2 = st.columns([1, 1])
            
            with col1:
                st.subheader("✅ Approve Extension")
                new_deadline = st.date_input(
                    "New Deadline:",
                    key=f"new_deadline_{request['_id']}",
                    min_value=datetime.now().date(),
                    value=datetime.now().date() + timedelta(days=7)
                )
                
                approval_notes = st.text_area(
                    "Approval Notes (Optional):",
                    key=f"approval_notes_{request['_id']}",
                    placeholder="Additional notes about the approval..."
                )
                
                if st.button("✅ Approve Extension", key=f"approve_extension_{request['_id']}"):
                    admin_user = st.session_state.get("username", "Admin")
                    if self.log_manager.approve_deadline_extension(
                        str(request["_id"]), 
                        new_deadline, 
                        admin_user, 
                        approval_notes
                    ):
                        st.success("✅ Deadline extension approved!")
                        st.rerun()
                    else:
                        st.error("❌ Failed to approve extension")
            
            with col2:
                st.subheader("❌ Reject Extension")
                rejection_notes = st.text_area(
                    "Rejection Reason:",
                    key=f"rejection_notes_{request['_id']}",
                    placeholder="Please provide reason for rejection..."
                )
                
                if st.button("❌ Reject Extension", key=f"reject_extension_{request['_id']}"):
                    if rejection_notes.strip():
                        admin_user = st.session_state.get("username", "Admin")
                        if self.log_manager.reject_deadline_extension(
                            str(request["_id"]), 
                            admin_user, 
                            rejection_notes
                        ):
                            st.success("✅ Deadline extension rejected!")
                            st.rerun()
                        else:
                            st.error("❌ Failed to reject extension")
                    else:
                        st.error("❌ Please provide a reason for rejection")

    def _format_date(self, date_str):
        """Format date string for display"""
        if not date_str or date_str in ['1970-01-01 00:00:00', None, '']:
            return "Not Set"
        try:
            if isinstance(date_str, str):
                for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d', '%d/%m/%Y']:
                    try:
                        dt = datetime.strptime(date_str, fmt)
                        return dt.strftime('%Y-%m-%d')
                    except ValueError:
                        continue
                return str(date_str)
            elif isinstance(date_str, datetime):
                return date_str.strftime('%Y-%m-%d')
            return str(date_str)
        except Exception:
            return "Invalid Date"

    def _format_datetime(self, dt):
        """Format datetime for display"""
        try:
            if dt is None:
                return "Not Recorded"
            elif isinstance(dt, str):
                return dt
            elif isinstance(dt, datetime):
                return dt.strftime('%Y-%m-%d %H:%M')
            return str(dt)
        except Exception:
            return "Invalid DateTime"