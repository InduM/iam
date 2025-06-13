import streamlit as st
import yagmail
from datetime import datetime, timedelta
from streamlit_autorefresh import st_autorefresh

# --- Email Config ---
EMAIL_USER = "indu3102@gmail.com"
EMAIL_PASS = "ilis hnzl alsl szrk"

# --- Initialize Session State ---
if "last_sent_time" not in st.session_state:
    st.session_state.last_sent_time = None
if "email_active" not in st.session_state:
    st.session_state.email_active = False

# --- UI ---
st.title("⏰ Email Reminder System")

recipients = st.text_area(
    "Enter comma-separated email recipients",
    placeholder="example1@gmail.com, example2@gmail.com"
)

checkbox1 = st.checkbox("✅ Start sending emails every 5 minutes")
checkbox2 = st.checkbox("🛑 Stop sending emails")

# --- Handle checkbox logic ---
if checkbox2:
    st.session_state.email_active = False
    st.success("Email reminders stopped.")
elif checkbox1:
    st.session_state.email_active = True
    st.info("Email reminders activated.")

# --- Auto-refresh every 60 seconds ---
st_autorefresh(interval=60 * 1000, key="email_refresh")

# --- Email Sending Logic ---
def send_emails(recipient_list):
    try:
        yag = yagmail.SMTP(EMAIL_USER, EMAIL_PASS)
        yag.send(
            to=recipient_list,
            subject="⏰ Reminder!",
            contents="Please check the second checkbox to stop these reminders."
        )
        return True
    except Exception as e:
        st.error(f"Failed to send email: {e}")
        return False

# --- Process recipients ---
recipient_list = [email.strip() for email in recipients.split(",") if email.strip()]

# --- Email sending logic (time-based) ---
if st.session_state.email_active and recipient_list:
    now = datetime.now()
    last_sent = st.session_state.last_sent_time

    if not last_sent or now - last_sent >= timedelta(minutes=1): #5
        sent = send_emails(recipient_list)
        if sent:
            st.session_state.last_sent_time = now
            st.success(f"Email sent at {now.strftime('%H:%M:%S')} to {', '.join(recipient_list)}")
    else:
        st.write(f"Next email at: {(last_sent + timedelta(minutes=1)).strftime('%H:%M:%S')}") #5

