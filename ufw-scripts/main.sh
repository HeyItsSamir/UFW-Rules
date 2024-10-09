#!/bin/bash
# Prompt user to choose security level

echo "Choose security level (1-4):"
echo "1. Basic Allow All"
echo "2. Allow HTTP/HTTPS, Deny All Else"
echo "3. Allow HTTP/HTTPS, SSH, Deny All Else"
echo "4. Strict Deny All, Allow Only HTTPS"

read -p "Enter your choice: " choice

case $choice in
    1)
        ./ufw-scripts/level1.sh
        ;;
    2)
        ./ufw-scripts/level2.sh
        ;;
    3)
        ./ufw-scripts/level3.sh
        ;;
    4)
        ./ufw-scripts/level4.sh
        ;;
    *)
        echo "Invalid choice"
        exit 1
        ;;
esac

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

# Ask user if they want to make a backup before resetting UFW

read -p "Do you want to make a backup of the current UFW rules before resetting? (y/n): " backup_choice

if [ "$backup_choice" == "y" ]; then
    sudo ufw status > ~/ufw-rules.backup
    echo "Backup created at ~/ufw-rules.backup"
fi

# Reset UFW
sudo ufw reset

echo "Configuration applied successfully."
