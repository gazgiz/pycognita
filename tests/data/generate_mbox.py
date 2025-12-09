
import mailbox
import email.message
import time
import random
from email.utils import formatdate
import os

OUTPUT_FILE = 'tests/data/fake_mbox.dat'

# Ensure clean slate
if os.path.exists(OUTPUT_FILE):
    os.remove(OUTPUT_FILE)

print(f"Generating {OUTPUT_FILE}...")

mbox = mailbox.mbox(OUTPUT_FILE)
mbox.lock()

try:
    # Start time: 100 days ago
    start_time = time.time() - (105 * 86400) 

    for i in range(1, 121):  # Generate 120 emails
        msg = email.message.Message()
        
        # Consistent chronological time: add 12 hours for each message
        msg_time = start_time + (i * 43200) 
        date_str = formatdate(msg_time, localtime=True)
        
        msg['Subject'] = f'Test Email {i}: Project Update'
        msg['From'] = f'sender_{i % 5}@example.com'  # 5 distinct senders
        msg['To'] = 'recipient@example.com'
        msg['Date'] = date_str
        msg['Message-ID'] = f'<msg_{i}_{int(msg_time)}@example.com>'
        msg['X-Sequnce-Num'] = str(i)
        
        body = f"""Hello,

This is test email number {i}.
It was generated at {date_str}.

Regards,
Sender {i % 5}
"""
        msg.set_payload(body)
        
        mbox.add(msg)
        
    print(f"Successfully added {len(mbox)} messages.")

finally:
    mbox.flush()
    mbox.unlock()
    mbox.close()
