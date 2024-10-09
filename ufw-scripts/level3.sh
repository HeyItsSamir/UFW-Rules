#!/bin/bash
# Level 3: Allow HTTP/HTTPS, SSH, Deny All Else

# Reset UFW
ufw reset

# Default deny all incoming and allow all outgoing
ufw default deny incoming
ufw default allow outgoing

# Allow HTTP, HTTPS, and SSH
ufw allow http
ufw allow https
ufw allow ssh

# Enable UFW
ufw enable
