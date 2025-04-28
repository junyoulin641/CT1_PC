#!/usr/bin/env python3
import subprocess
import argparse
import os
import time
import sys
import re
import threading
import queue
import serial
import serial.tools.list_ports
from datetime import datetime

class Logger:
    """Custom logger that outputs to both console and file"""
    def __init__(self, serial_number=None, log_dir="LOG"):
        self.terminal = sys.stdout
        self.stderr_terminal = sys.stderr
        
        # Create log directory if it doesn't exist
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        
        # Create log filename with timestamp and serial number
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if serial_number:
            self.log_filename = os.path.join(log_dir, f"CT1-{timestamp}-{serial_number}.log")
        else:
            self.log_filename = os.path.join(log_dir, f"CT1_DL_{timestamp}.log")
        
        # Open log file
        self.log_file = open(self.log_filename, "w", encoding="utf-8")
        print(f"Logging to file: {self.log_filename}")
        
    def write(self, message):
        self.terminal.write(message)
        self.log_file.write(message)
        self.log_file.flush()
        
    def flush(self):
        self.terminal.flush()
        self.log_file.flush()
    
    def stderr_write(self, message):
        self.stderr_terminal.write(message)
        self.log_file.write(f"ERROR: {message}")
        self.log_file.flush()
        
    def stderr_flush(self):
        self.stderr_terminal.flush()
        self.log_file.flush()
    
    def close(self):
        self.log_file.close()

def setup_logging(serial_number=None):
    """Set up logging to both console and file"""
    logger = Logger(serial_number)
    sys.stdout = logger
    
    # Create a custom stderr handler
    class StderrLogger:
        def write(self, message):
            logger.stderr_write(message)
        def flush(self):
            logger.stderr_flush()
    
    sys.stderr = StderrLogger()
    return logger

def run_command(command, cwd=None):
    """Run command and return results with real-time character output"""
    print(f"Executing command: {command}", end='', flush=True)
    print()  # Single newline after command
    
    # Use universal_newlines=True for text mode
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=True,
        cwd=cwd,
        bufsize=0,  # Unbuffered
        universal_newlines=False  # Binary mode for raw reading
    )
    
    # Real-time output of command execution results
    output_lines = []
    current_line = ""
    
    # Stream readers that read by character
    def read_stream(stream, is_error=False):
        while True:
            # Read a single byte
            char = stream.read(1)
            if not char:
                break
                
            try:
                # Convert byte to string
                char_str = char.decode('utf-8', errors='replace')
                
                # Print directly for real-time output
                if is_error:
                    sys.stderr.write(char_str)
                    sys.stderr.flush()
                else:
                    sys.stdout.write(char_str)
                    sys.stdout.flush()
                
                # For collecting output
                nonlocal current_line
                if char_str == '\n':
                    if current_line:
                        output_lines.append(current_line)
                        current_line = ""
                else:
                    current_line += char_str
            except Exception as e:
                print(f"\nError processing output: {str(e)}", flush=True)
    
    # Create and start reader threads
    stdout_thread = threading.Thread(target=read_stream, args=(process.stdout, False))
    stderr_thread = threading.Thread(target=read_stream, args=(process.stderr, True))
    stdout_thread.daemon = True
    stderr_thread.daemon = True
    stdout_thread.start()
    stderr_thread.start()
    
    # Wait for process to complete
    returncode = process.wait()
    
    # Wait for threads to finish
    stdout_thread.join(timeout=1.0)
    stderr_thread.join(timeout=1.0)
    
    # Add any remaining partial line
    if current_line:
        output_lines.append(current_line)
    
    return output_lines, returncode

def check_device_connection(tool_path):
    """Check device connection status"""
    print("=== Checking Device Connection ===", flush=True)
    command = f"{os.path.join(tool_path, 'upgrade_tool')} LD"
    output_lines, return_code = run_command(command, cwd=tool_path)
    
    # Check if any device is connected
    device_connected = False
    for line in output_lines:
        if "DevNo=" in line and "Mode=Maskrom" in line:
            device_connected = True
            break
    
    if not device_connected:
        print("Error: No device detected or device not in Maskrom mode", flush=True)
        return False
    
    print("Device connection normal, ready for firmware update", flush=True)
    return True

def update_firmware(tool_path, img_path):
    """Update firmware"""
    print("=== Starting Firmware Update ===", flush=True)
    # Build complete image path
    if not os.path.isabs(img_path):
        img_path = os.path.join(tool_path, img_path)
    
    command = f"{os.path.join(tool_path, 'upgrade_tool')} UF {img_path}"
    output_lines, return_code = run_command(command, cwd=tool_path)
    
    # Check if update was successful
    update_success = False
    for line in output_lines:
        if "Upgrade firmware ok" in line:
            update_success = True
            break
    
    if update_success:
        print("Firmware update successful!", flush=True)
        return True
    else:
        print("Error: Firmware update failed", flush=True)
        return False

def list_com_ports():
    """List all available COM ports"""
    print("=== Available COM Ports ===", flush=True)
    ports = list(serial.tools.list_ports.comports())
    
    if not ports:
        print("No COM ports available", flush=True)
        return []
    
    for i, port in enumerate(ports):
        print(f"{i+1}. {port.device} - {port.description}", flush=True)
    
    return ports

def get_com_port_by_number(com_number):
    """Get COM port from number (e.g., COM3)"""
    port_name = f"COM{com_number}"
    ports = list(serial.tools.list_ports.comports())
    
    for port in ports:
        if port.device.upper() == port_name.upper():
            return port.device
    
    return None

def send_uart_command(com_port, command, baudrate=115200, timeout=5, wait_for_response=True):
    """Send a single command via UART and return the response"""
    print(f"Sending UART command: {command}", flush=True)
    
    # Define expected response based on command
    expected_response = None
    if command == "REQ_DC_IN":
        expected_response = "RES_DC_IN_OK"
    elif command == "REQ_DC_OUT":
        expected_response = "RES_DC_OUT_OK"
    elif command == "REQ_POWER_ON":
        expected_response = "RES_POWER_ON_OK"
    elif command == "REQ_POWER_OFF":
        expected_response = "RES_POWER_OFF_OK"
    elif command == "REQ_BOOT_ON":
        expected_response = "RES_BOOT_ON_OK"
    elif command == "REQ_BOOT_OFF":
        expected_response = "RES_BOOT_OFF_OK"
    elif command == "REQ_INIT":
        expected_response = "RES_INIT_OK"
    
    try:
        # Open serial port
        ser = serial.Serial(com_port, baudrate, timeout=timeout)
        
        # Clear any pending data
        ser.reset_input_buffer()
        
        # Send command with newline
        ser.write((command).encode('utf-8'))
        
        response = ""
        if wait_for_response:
            # Wait for response
            start_time = time.time()
            while (time.time() - start_time) < timeout:
                if ser.in_waiting:
                    data = ser.read(ser.in_waiting)
                    try:
                        data_str = data.decode('utf-8', errors='replace')
                        response += data_str
                        sys.stdout.write(data_str)
                        sys.stdout.flush()
                    except Exception as e:
                        print(f"\nError decoding data: {str(e)}", flush=True)
                
                # If we got some response, wait a bit more for any additional data
                if response and (time.time() - start_time) > 0.5:
                    time.sleep(0.5)
                    if not ser.in_waiting:
                        break
                
                time.sleep(0.01)
        
        # Close the port
        ser.close()
        
        # Check if expected response is in the received data
        if expected_response and expected_response not in response:
            print(f"Warning: Expected response '{expected_response}' not found in command output", flush=True)
        
        return response
        
    except serial.SerialException as e:
        print(f"Error in UART communication: {str(e)}", flush=True)
        return None

def check_uart_response(response, expected=None):
    """Check if UART response is valid and contains expected text"""
    if response is None:
        print("Error: No response received from UART command", flush=True)
        return False
    
    # If no specific expected text is provided, check for standard responses
    if not expected:
        standard_responses = [
            "RES_DC_IN_OK", "RES_DC_OUT_OK", 
            "RES_POWER_ON_OK", "RES_POWER_OFF_OK", 
            "RES_BOOT_ON_OK", "RES_BOOT_OFF_OK", 
            "RES_INIT_OK"
        ]
        
        for std_resp in standard_responses:
            if std_resp in response:
                print(f"Success: Received valid response: {std_resp}", flush=True)
                return True
    
    # Check for specific expected text if provided
    elif expected and expected in response:
        print(f"Success: Received expected response: {expected}", flush=True)
        return True
    elif expected:
        print(f"Warning: Expected '{expected}' not found in response", flush=True)
        return False
        
    # If we got here, no valid response was found
    print("Warning: No valid standard response found in UART output", flush=True)
    return False

def wait_for_test_completion(serial_number, station_name, device_id=None, timeout_seconds=300):
    """
    Wait for test completion and pull log files from device
    
    Args:
        serial_number: Device serial number
        station_name: Test station name
        device_id: ADB device ID (if multiple devices connected)
        timeout_seconds: Maximum time to wait for test completion in seconds (default: 5 minutes)
    """
    if not serial_number:
        serial_number = "00000000000"
    
    print(f"Waiting for test completion... (Serial: {serial_number}, Station: {station_name})")
    print(f"Timeout set to {timeout_seconds} seconds")
    
    # Ensure output directory exists - Use LOG directory consistently
    log_dir = os.path.join(os.getcwd(), "LOG")
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
        print(f"Created output directory: {log_dir}")
    
    # Wait for device to be available on ADB
    print("Waiting for device to be available on ADB...")
    adb_device_ready = False
    retry_count = 0
    max_retries = 30  # 30 seconds max wait time for ADB device
    
    while not adb_device_ready and retry_count < max_retries:
        try:
            # Check if device is available in ADB
            adb_devices_cmd = ['adb', 'devices']
            devices_output = subprocess.run(adb_devices_cmd, capture_output=True, text=True).stdout
            
            # If specific device ID is provided, check for it
            if device_id:
                adb_device_ready = device_id in devices_output
            else:
                # Otherwise check if any device is connected (except emulators)
                lines = devices_output.strip().split('\n')
                for line in lines[1:]:  # Skip the first line which is the header
                    if line and 'device' in line and 'emulator' not in line:
                        adb_device_ready = True
                        # If we found a device but no specific ID was given, use this device
                        if not device_id:
                            device_id = line.split()[0]
                            print(f"Auto-detected device: {device_id}")
                            break
            
            if adb_device_ready:
                print("Device is available on ADB")
                break
                
            print(".", end="", flush=True)
            time.sleep(1)
            retry_count += 1
            
        except Exception as e:
            print(f"Error checking ADB device: {str(e)}")
            time.sleep(1)
            retry_count += 1
    
    if not adb_device_ready:
        print("\nError: Device not available on ADB after waiting")
        return False
    
    # Set up ADB command prefix
    adb_prefix = ['adb']
    if device_id:
        adb_prefix.extend(['-s', device_id])
    
    try:
        # First set up logcat monitoring to ensure we don't miss any output
        print("Setting up logcat monitoring...")
        
        # Clear existing logcat buffer to ensure we only capture new logs
        subprocess.run(adb_prefix + ['logcat', '-c'], check=True)
        
        # Start logcat process to monitor TEST_RESULT tag
        logcat_cmd = adb_prefix + ['logcat', '-v', 'time', 'TEST_RESULT:D', '*:S']
        
        # Launch the logcat process
        process = subprocess.Popen(
            logcat_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        
        print("Logcat monitoring started.")
        
        # Then send the test broadcast command
        print("Sending test broadcast command...")
        broadcast_cmd = adb_prefix + [
            'shell', 
            'am', 'broadcast', 
            '-n', 'com.rtk.ct1atptest/.domain.TestControlReceiver', 
            '-a', 'com.rtk.ct1atptest.PCATP', 
            '--es', 'SerialNumber', serial_number, 
            '--es', 'StationName', station_name
        ]
        
        broadcast_result = subprocess.run(broadcast_cmd, capture_output=True, text=True)
        if "Broadcast completed" not in broadcast_result.stdout:
            print(f"Error: Broadcast command may not have been successfully sent")
            print(f"Output: {broadcast_result.stdout}")
            print(f"Error: {broadcast_result.stderr}")
            return False
        
        print("Broadcast command sent successfully, waiting for test completion...")
        print("Monitoring logcat output, waiting for 'ATP Test Finish!!' message...")
        
        # Process logcat output and wait for timeout
        test_success = False
        start_time = time.time()
        
        # Set up non-blocking reads for Windows compatibility
        process.stdout.flush()
        
        # Use polling instead of select.select for Windows compatibility
        while True:
            # Check if we've exceeded the timeout
            elapsed_time = time.time() - start_time
            if elapsed_time > timeout_seconds:
                print(f"Error: Timeout after waiting {timeout_seconds} seconds for test completion")
                return False
            
            # Check if process has terminated
            if process.poll() is not None:
                print("Error: Logcat process terminated unexpectedly")
                break
                
            # Read available output without blocking
            line = process.stdout.readline()
            if line:
                # Check if line contains target message
                if "ATP Test Finish!!" in line:
                    print(f"\nDetected test completion message: {line.strip()}")
                    
                    # Give system some time to ensure log files are fully written
                    print("Waiting for log files to complete writing...")
                    time.sleep(2)
                    
                    # Look for specific log file using the specified path and format
                    log_path = f"/storage/emulated/0/Android/data/com.rtk.ct1atptest/files/Logs/{station_name}.txt"
                    print(f"Checking log file: {log_path}")
                    
                    # Check if file exists
                    check_cmd = adb_prefix + ['shell', f'test -e "{log_path}" && echo "EXISTS" || echo "NOT_FOUND"']
                    check_result = subprocess.run(check_cmd, capture_output=True, text=True)
                    
                    if "EXISTS" not in check_result.stdout:
                        print(f"Error: Log file not found: {log_path}")
                        return False
                    
                    print(f"Found log file: {log_path}")
                    
                    # Create target filename
                    filename = f"{station_name}.txt"
                    output_path = os.path.join(log_dir, filename)
                    
                    # Use adb pull to download log file
                    print(f"Downloading log file...")
                    pull_cmd = adb_prefix + ['pull', log_path, output_path]
                    pull_result = subprocess.run(pull_cmd, capture_output=True, text=True)
                    
                    if "1 file pulled" in pull_result.stderr:
                        print(f"Success! Log file saved to: {output_path}")
                        test_success = True
                    else:
                        print(f"Error: Could not download log file")
                        print(f"Error message: {pull_result.stderr}")
                    
                    break
            else:
                # Small sleep to prevent high CPU usage
                time.sleep(0.1)
            
            # Show progress and remaining time every 30 seconds
            if int(elapsed_time) % 30 == 0 and int(elapsed_time) > 0:
                remaining = timeout_seconds - elapsed_time
                print(f"Still waiting... {int(remaining)} seconds remaining", flush=True)
        
        return test_success
    
    except KeyboardInterrupt:
        print("\nOperation interrupted by user")
        return False
    except Exception as e:
        print(f"Error: {str(e)}")
        return False
    finally:
        # Make sure to close logcat process
        if 'process' in locals():
            process.terminate()

def atpfwdl_process(com_port, tool_path, img_path, serial_number=None, device_id=None):
    """Special process for ATPFWDL station"""
    print("\n=== Starting ATPFWDL Process ===")
    station_name = "ATPFWDL"
    process_result = False
    
    if not com_port:
        print("Error: COM port is required for ATPFWDL station")
        return False
    
    try:
        # Step 1: Send boot sequence commands over UART
        print("Step 1: Sending boot sequence commands")
        
        # Initialize the device
        response = send_uart_command(com_port, "REQ_INIT")
        if not check_uart_response(response, "RES_INIT_OK"):
            print("Warning: REQ_INIT command may have failed. Continuing anyway...")
        time.sleep(0.5)
        
        # Send boot on command
        response = send_uart_command(com_port, "REQ_BOOT_ON")
        if not check_uart_response(response, "RES_BOOT_ON_OK"):
            print("Error: REQ_BOOT_ON command failed")
            return False
        time.sleep(0.5)
        
        # Send power on command
        response = send_uart_command(com_port, "REQ_POWER_ON")
        if not check_uart_response(response, "RES_POWER_ON_OK"):
            print("Error: REQ_POWER_ON command failed")
            return False
        time.sleep(0.5)
        
        # Send DC in command
        response = send_uart_command(com_port, "REQ_DC_IN")
        if not check_uart_response(response, "RES_DC_IN_OK"):
            print("Error: REQ_DC_IN command failed")
            return False
        
        # Give device time to boot into Maskrom mode
        print("Waiting for device to enter Maskrom mode (5 seconds)...")
        time.sleep(2)
        
        # Step 2: Check device connection
        print("Step 2: Checking device connection")
        retry_count = 0
        max_retries = 3
        connection_success = False
        
        while not connection_success and retry_count < max_retries:
            if check_device_connection(tool_path):
                connection_success = True
                break
            
            print(f"Retry {retry_count+1}/{max_retries} checking device connection...")
            retry_count += 1
            time.sleep(2)
        
        if not connection_success:
            print("Error: Device connection failed after boot sequence")
            return False
        
        # Step 3: Send REQ_BOOT_OFF command
        print("Step 3: Sending REQ_BOOT_OFF command")
        response = send_uart_command(com_port, "REQ_BOOT_OFF")
        if not check_uart_response(response, "RES_BOOT_OFF_OK"):
            print("Warning: REQ_BOOT_OFF command may have failed. Continuing anyway...")
        time.sleep(1)
        
        # Step 4: Update firmware
        print("Step 4: Updating firmware")
        if not update_firmware(tool_path, img_path):
            print("Error: Firmware update failed")
            return False
        
        print("Firmware update successful")
        
        # Step 5: Wait for device to reboot and stabilize
        print("Step 5: Waiting for device to reboot (90 seconds)...")
        time.sleep(90)  # Increased wait time to 90 seconds
        
        # Step 6: Send test broadcast command to device
        print("Step 6: Starting ATP test")
        if not wait_for_test_completion(serial_number, station_name, device_id, timeout_seconds=300):
            print("Error: ATP test failed or log file not found")
            return False
        
        print("ATPFWDL process completed successfully")
        process_result = True
        return True
        
    except Exception as e:
        print(f"Error in ATPFWDL process: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Final reset command always executed regardless of success or failure
        print("Sending final REQ_INIT command to reset the device")
        try:
            response = send_uart_command(com_port, "REQ_INIT")
            if check_uart_response(response, "RES_INIT_OK"):
                print("Device reset completed successfully")
            else:
                print("Warning: Device reset may not have completed properly")
        except Exception as e:
            print(f"Warning: Failed to send final REQ_INIT command: {str(e)}")

def main():
    parser = argparse.ArgumentParser(description="CT1 Device Management Tool")
    parser.add_argument("--SerialNumber", help="Device serial number")
    parser.add_argument("--StationName", help="Test station name")
    parser.add_argument("--device", help="ADB device ID (if multiple devices connected)")
    parser.add_argument("--comport", type=int, help="COM port number (e.g., 3 for COM3)", nargs='?', const=None)
    parser.add_argument("--timeout", type=int, default=300, help="Timeout in seconds for test completion (default: 300)")
    
    args = parser.parse_args()
    
    # Set up logging - capture all output to log file with SerialNumber as part of filename
    logger = setup_logging(args.SerialNumber)
    
    # Print start time and command line arguments
    start_time = datetime.now()
    print(f"=== CT1 Device Management Tool ===")
    print(f"Start time: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Arguments: {' '.join(sys.argv[1:])}")
    
    try:
        # Set upgrade tool path
        tool_path = os.path.abspath("upgrade_tool_v2.33_for_window")
        img_path = "update.img"
        
        print(f"Upgrade tool path: {tool_path}")
        
        # Check if tool and image files exist
        if not os.path.exists(os.path.join(tool_path, "upgrade_tool.exe")):
            print(f"Error: Upgrade tool not found at path {tool_path}")
            return False
        
        if not os.path.exists(os.path.join(tool_path, "update.img")):
            print(f"Error: Update image not found at path {tool_path}")
            return False
        
        # Get COM port if specified
        com_port = None
        if args.comport is not None:
            com_port = get_com_port_by_number(args.comport)
            if not com_port:
                print(f"Error: COM{args.comport} not found")
                return False
            print(f"Using COM port: {com_port}")
        
        # Handle ATPFWDL station
        if args.StationName == "ATPFWDL":
            if not com_port:
                print("Error: COM port is required for ATPFWDL station")
                return False
            
            result = atpfwdl_process(
                com_port=com_port,
                tool_path=tool_path,
                img_path=img_path,
                serial_number=args.SerialNumber,
                device_id=args.device
            )
        
        # For other stations, just do the test broadcast
        elif args.StationName:
            result = wait_for_test_completion(
                args.SerialNumber,
                args.StationName,
                device_id=args.device,
                timeout_seconds=args.timeout
            )
        
        else:
            print("Error: StationName parameter is required")
            print("Usage examples:")
            print("  For ATPFWDL station: python CT1_DL.py --StationName ATPFWDL --comport 3 --SerialNumber 123456")
            print("  For other stations: python CT1_DL.py --StationName PreUI --SerialNumber 123456")
            result = False
            
        # Print end time and elapsed time
        end_time = datetime.now()
        elapsed_time = end_time - start_time
        print(f"\n=== Process Completed ===")
        print(f"End time: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Elapsed time: {elapsed_time}")
        
        return result
        
    finally:
        # Close logger to ensure all data is written to file
        if 'logger' in locals():
            logger.close()
            # Restore original stdout and stderr
            sys.stdout = sys.__stdout__
            sys.stderr = sys.__stderr__

if __name__ == "__main__":
    try:
        success = main()
        if success:
            print("Result: PASS")
            sys.exit(0)
        else:
            print("Result: FAIL")
            sys.exit(1)
    except Exception as e:
        print(f"Error occurred: {str(e)}")
        print("Result: FAIL")
        sys.exit(1)
