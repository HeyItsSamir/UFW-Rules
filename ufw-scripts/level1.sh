#!/bin/bash
# Level 1: Basic Allow All

# Reset UFW
ufw reset

# Allow all incoming and outgoing traffic
ufw default allow incoming
ufw default allow outgoing

# Enable UFW
ufw enable
