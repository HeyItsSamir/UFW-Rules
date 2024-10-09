#!/bin/bash
# Level 2: Allow HTTP/HTTPS, Deny All Else

# Reset UFW
ufw reset

# Default deny all incoming and allow all outgoing
ufw default deny incoming
ufw default allow outgoing

# Allow HTTP and HTTPS
ufw allow http
ufw allow https

# Enable UFW
ufw enable
