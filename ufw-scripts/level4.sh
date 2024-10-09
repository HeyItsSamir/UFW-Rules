#!/bin/bash
# Level 4: Strict Deny All, Allow Only HTTPS

# Ask user if they want to make a backup before resetting UFW

read -p "Do you want to make a backup of the current UFW rules before resetting? (y/n): " backup_choice

if [ "$backup_choice" == "y" ]; then
    sudo ufw status > ~/ufw-rules.backup
    echo "Backup created at ~/ufw-rules.backup"
fi

# Reset UFW
sudo ufw reset

# Default deny all incoming and allow all outgoing
sudo ufw default deny incoming
sudo ufw default allow outgoing

# Allow only HTTPS
sudo ufw allow https

# Enable UFW
sudo ufw enable

# Prompt user to choose logging level

echo "Choose logging level (1-4):"
echo "1. Off"
echo "2. Low"
echo "3. Medium"
echo "4. High"

read -p "Enter your choice: " log_choice

case $log_choice in
    1)
        sudo ufw logging off
        ;;
    2)
        sudo ufw logging low
        ;;
    3)
        sudo ufw logging medium
        ;;
    4)
        sudo ufw logging high
        ;;
    *)
        echo "Invalid choice"
        exit 1
        ;;
esac

echo "Configuration applied successfully."
