import streamlit as st
import subprocess
import os
import glob
import shlex
import time
from pathlib import Path
import threading
import queue

# Page configuration
st.set_page_config(
    page_title="Linux Command Explorer",
    page_icon="🐧",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for terminal-like appearance
st.markdown("""
<style>
    .main > div {
        padding-top: 2rem;
    }
    .stTextArea textarea {
        font-family: 'Courier New', monospace;
        background-color: #0d1117;
        color: #58a6ff;
        border: 1px solid #30363d;
    }
    .command-output {
        background-color: #0d1117;
        color: #c9d1d9;
        padding: 10px;
        border-radius: 5px;
        font-family: 'Courier New', monospace;
        white-space: pre-wrap;
        border: 1px solid #30363d;
        max-height: 400px;
        overflow-y: auto;
    }
    .command-header {
        background-color: #21262d;
        color: #58a6ff;
        padding: 8px;
        border-radius: 5px 5px 0 0;
        font-family: 'Courier New', monospace;
        font-weight: bold;
        border: 1px solid #30363d;
        border-bottom: none;
    }
    .error-output {
        background-color: #1a1e23;
        color: #f85149;
        padding: 10px;
        border-radius: 5px;
        font-family: 'Courier New', monospace;
        white-space: pre-wrap;
        border: 1px solid #da3633;
        margin-top: 5px;
    }
    .success-output {
        background-color: #0d1421;
        color: #56d364;
        padding: 10px;
        border-radius: 5px;
        font-family: 'Courier New', monospace;
        white-space: pre-wrap;
        border: 1px solid #238636;
        margin-top: 5px;
    }
</style>
""", unsafe_allow_html=True)

def get_bin_commands():
    """Get all executable commands from common bin directories"""
    bin_paths = ['/bin', '/usr/bin', '/usr/local/bin', '/sbin', '/usr/sbin']
    commands = set()
    
    for bin_path in bin_paths:
        if os.path.exists(bin_path):
            try:
                for item in os.listdir(bin_path):
                    full_path = os.path.join(bin_path, item)
                    if os.path.isfile(full_path) and os.access(full_path, os.X_OK):
                        commands.add(item)
            except PermissionError:
                continue
    
    return sorted(list(commands))

def get_command_help(command):
    """Get help information for a command"""
    help_options = ['--help', '-h', 'help']
    
    for help_opt in help_options:
        try:
            if help_opt == 'help':
                cmd = f"help {command}"
            else:
                cmd = f"{command} {help_opt}"
            
            result = subprocess.run(
                cmd, 
                shell=True, 
                capture_output=True, 
                text=True, 
                timeout=5
            )
            
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout
            elif result.stderr.strip():
                return result.stderr
                
        except (subprocess.TimeoutExpired, Exception):
            continue
    
    return "No help information available"

def run_command_safe(command, timeout=10):
    """Safely run a command with timeout and error handling"""
    try:
        # Sanitize command to prevent dangerous operations
        dangerous_commands = [
            'rm', 'rmdir', 'del', 'format', 'fdisk', 'mkfs', 
            'dd', 'shred', 'wipe', 'halt', 'shutdown', 'reboot',
            'init', 'kill', 'killall', 'pkill', 'fuser'
        ]
        
        base_cmd = command.split()[0]
        if base_cmd in dangerous_commands:
            return False, "Command blocked for safety reasons", ""
        
        # Add safe flags for some commands
        safe_commands = {
            'ls': 'ls -la',
            'ps': 'ps aux',
            'df': 'df -h',
            'du': 'du -h --max-depth=1',
            'free': 'free -h',
            'top': 'top -b -n1',
            'netstat': 'netstat -tuln',
            'ss': 'ss -tuln'
        }
        
        if base_cmd in safe_commands and command == base_cmd:
            command = safe_commands[base_cmd]
        
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        
        return True, result.stdout, result.stderr
        
    except subprocess.TimeoutExpired:
        return False, "", "Command timed out"
    except Exception as e:
        return False, "", f"Error: {str(e)}"

# Initialize session state
if 'commands' not in st.session_state:
    st.session_state.commands = []
    st.session_state.loading = True

# Header
st.title("🐧 Linux Command Explorer")
st.markdown("**Explore and execute Linux commands from /bin directories**")

# Sidebar
with st.sidebar:
    st.header("⚙️ Controls")
    
    # Load commands button
    if st.button("🔄 Refresh Commands", type="primary"):
        st.session_state.loading = True
        st.rerun()
    
    # Search functionality
    search_term = st.text_input("🔍 Search Commands", placeholder="Type command name...")
    
    # Filter options
    st.subheader("Filters")
    show_system = st.checkbox("Show system commands", value=True)
    show_user = st.checkbox("Show user commands", value=True)
    
    # Safety settings
    st.subheader("Safety")
    safe_mode = st.checkbox("Safe mode (recommended)", value=True, 
                           help="Prevents execution of potentially dangerous commands")

# Load commands
if st.session_state.loading:
    with st.spinner("Loading commands from /bin directories..."):
        st.session_state.commands = get_bin_commands()
        st.session_state.loading = False
        st.rerun()

# Filter commands based on search
filtered_commands = st.session_state.commands
if search_term:
    filtered_commands = [cmd for cmd in st.session_state.commands 
                        if search_term.lower() in cmd.lower()]

# Main content
col1, col2 = st.columns([1, 2])

with col1:
    st.subheader(f"📋 Commands ({len(filtered_commands)} found)")
    
    if filtered_commands:
        # Display commands in a selectbox
        selected_command = st.selectbox(
            "Select a command:",
            options=filtered_commands,
            index=0 if filtered_commands else None
        )
        
        # Command information
        if selected_command:
            st.markdown(f"**Selected:** `{selected_command}`")
            
            # Get command path
            try:
                which_result = subprocess.run(
                    f"which {selected_command}",
                    shell=True,
                    capture_output=True,
                    text=True
                )
                if which_result.returncode == 0:
                    st.markdown(f"**Path:** `{which_result.stdout.strip()}`")
            except:
                pass
    else:
        st.warning("No commands found matching your search.")

with col2:
    if filtered_commands and 'selected_command' in locals():
        st.subheader(f"🖥️ Command: {selected_command}")
        
        # Command execution section
        st.markdown("### Execute Command")
        
        # Custom command input
        custom_args = st.text_input(
            "Additional arguments (optional):",
            placeholder="e.g., --help, -la, etc.",
            help="Enter additional arguments for the command"
        )
        
        # Build full command
        full_command = selected_command
        if custom_args.strip():
            full_command += f" {custom_args.strip()}"
        
        st.markdown(f"**Command to execute:** `{full_command}`")
        
        # Execute button
        if st.button(f"▶️ Execute: {full_command}", type="primary"):
            with st.spinner("Executing command..."):
                success, stdout, stderr = run_command_safe(full_command)
                
                if success:
                    if stdout:
                        st.markdown('<div class="command-header">✅ Output:</div>', unsafe_allow_html=True)
                        st.markdown(f'<div class="command-output">{stdout}</div>', unsafe_allow_html=True)
                    else:
                        st.success("Command executed successfully (no output)")
                    
                    if stderr:
                        st.markdown('<div class="command-header">⚠️ Warnings/Errors:</div>', unsafe_allow_html=True)
                        st.markdown(f'<div class="error-output">{stderr}</div>', unsafe_allow_html=True)
                else:
                    st.error(f"Command failed: {stderr}")
        
        # Help section
        st.markdown("### 📖 Help Information")
        if st.button(f"📚 Get Help for {selected_command}"):
            with st.spinner("Getting help information..."):
                help_text = get_command_help(selected_command)
                st.markdown('<div class="command-header">Help Output:</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="command-output">{help_text}</div>', unsafe_allow_html=True)
        
        # Quick actions
        st.markdown("### ⚡ Quick Actions")
        col_a, col_b, col_c = st.columns(3)
        
        with col_a:
            if st.button("📋 List Files", help="Execute: ls -la"):
                success, stdout, stderr = run_command_safe("ls -la")
                if success and stdout:
                    st.markdown('<div class="success-output">' + stdout + '</div>', unsafe_allow_html=True)
        
        with col_b:
            if st.button("💾 Disk Usage", help="Execute: df -h"):
                success, stdout, stderr = run_command_safe("df -h")
                if success and stdout:
                    st.markdown('<div class="success-output">' + stdout + '</div>', unsafe_allow_html=True)
        
        with col_c:
            if st.button("🔄 Processes", help="Execute: ps aux | head -10"):
                success, stdout, stderr = run_command_safe("ps aux | head -10")
                if success and stdout:
                    st.markdown('<div class="success-output">' + stdout + '</div>', unsafe_allow_html=True)

# Footer
st.markdown("---")
st.markdown("""
**⚠️ Safety Notice:** This app runs commands on the server. Use caution when executing commands.
Some potentially dangerous commands are blocked for security.

**💡 Tips:** 
- Use the search box to quickly find commands
- Try common arguments like --help, -h for more information
- Check the help section for detailed command documentation
""")

# Statistics
if len(st.session_state.commands) > 0:
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📊 Statistics")
    st.sidebar.metric("Total Commands", len(st.session_state.commands))
    st.sidebar.metric("Filtered Commands", len(filtered_commands))
