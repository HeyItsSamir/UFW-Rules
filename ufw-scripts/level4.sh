#!/bin/bash
# Level 4: Strict Deny All, Allow Only HTTPS

# Reset UFW
ufw reset

# Default deny all incoming and allow all outgoing
ufw default deny incoming
ufw default allow outgoing

# Allow only HTTPS
ufw allow https

# Enable UFW
ufw enable
