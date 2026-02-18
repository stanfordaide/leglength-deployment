#!/usr/bin/env bash
set -Eeo pipefail

echo "-- Starting pediatric leg length module..."

# Fix for PyTorch 2.x getpwuid() issue: ensure running UID has a passwd entry
# This is needed because PyTorch tries to determine the username for cache directories
fix_passwd_entry() {
    local current_uid=$(id -u)
    local current_gid=$(id -g)
    
    # Check if current UID exists in passwd
    if ! getent passwd "$current_uid" > /dev/null 2>&1; then
        echo "-- Adding passwd entry for UID $current_uid (required by PyTorch)"
        # Create a passwd entry for the current user
        echo "mercure_user:x:$current_uid:$current_gid:Mercure User:/app/v0:/bin/bash" >> /etc/passwd 2>/dev/null || true
    fi
}

# Try to fix passwd entry (may fail if /etc/passwd is read-only, but env vars should handle it)
fix_passwd_entry

# Function to fix permissions and run as appropriate user
run_as_user() {
    local target_uid=${DOCKER_UID:-$(id -u mercureapp)}
    local target_gid=${DOCKER_GID:-$(id -g mercureapp)}
    
    # If running as root, we can try to fix permissions and switch users
    if [ "$(id -u)" = "0" ]; then
        echo "-- Running as root, attempting to fix permissions and switching to user $target_uid:$target_gid"
        
        # Ensure output directory exists
        mkdir -p /output
        
        # Handle MONITORING_DATA_PATH if set
        if [ -n "$MONITORING_DATA_PATH" ]; then
            echo "-- Handling monitoring path: $MONITORING_DATA_PATH"
            mkdir -p "$MONITORING_DATA_PATH"
            
            if ! chown $target_uid:$target_gid "$MONITORING_DATA_PATH" 2>/dev/null; then
                echo "-- Warning: Cannot change ownership of monitoring path, attempting chmod 777"
            fi
            chmod 777 "$MONITORING_DATA_PATH" 2>/dev/null || true
        fi
        
        # Try to fix ownership, but don't fail if we can't
        if ! chown $target_uid:$target_gid /output 2>/dev/null; then
            echo "-- Warning: Cannot change ownership of /output (this is often normal with mounted volumes)"
            echo "-- Attempting to fix permissions instead..."
        fi
        
        # Try to set permissions - this usually works even when chown doesn't
        if chmod 777 /output 2>/dev/null; then
            echo "-- Set /output permissions to 777 (world-writable)"
        else
            echo "-- Warning: Cannot change permissions on /output"
        fi
        
        # Test if we can write to the directory after switching users
        if gosu $target_uid:$target_gid test -w /output 2>/dev/null; then
            echo "-- Successfully configured write access to /output"
            exec gosu $target_uid:$target_gid python run.py $MERCURE_IN_DIR $MERCURE_OUT_DIR
        else
            echo "-- Cannot write to /output as user $target_uid, falling back to root execution"
            echo "-- Note: This is less secure but ensures the application works"
            exec python run.py $MERCURE_IN_DIR $MERCURE_OUT_DIR
        fi
    else
        # Not running as root, check if we can write to output
        if [ -d "/output" ] && [ ! -w "/output" ]; then
            echo "-- Warning: Cannot write to /output directory."
            echo "-- Please ensure proper permissions on host directory:"
            echo "-- chmod 755 /path/to/host/output"
            echo "-- chown \$(id -u):\$(id -g) /path/to/host/output"
        fi
        
        # Run as current user
        exec python run.py $MERCURE_IN_DIR $MERCURE_OUT_DIR
    fi
}

run_as_user
echo "-- Done."