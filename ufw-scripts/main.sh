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
        ./level1.sh
        ;;
    2)
        ./level2.sh
        ;;
    3)
        ./level3.sh
        ;;
    4)
        ./level4.sh
        ;;
    *)
        echo "Invalid choice"
        ;;
esac
