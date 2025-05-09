#!/usr/bin/env python3
import subprocess
import os
import time
import sys
import threading
import serial
import serial.tools.list_ports
from datetime import datetime
import re
import pyvisa  # 添加 PyVISA 库用于 GPIB 控制

class Logger:
    """
    * Custom logger that outputs to both console and file
    * Handles standard output and error redirection
    """
    def __init__(self, strSerialNumber=None, strLogDir="CT1_LOG"):
        self.objTerminal = sys.stdout
        self.objStderrTerminal = sys.stderr
        if not os.path.exists(strLogDir):
            os.makedirs(strLogDir)
        strTimestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if strSerialNumber:
            self.strLogFilename = os.path.join(strLogDir, f"CT1-{strTimestamp}-{strSerialNumber}.log")
        else:
            self.strLogFilename = os.path.join(strLogDir, f"CT1_DL_{strTimestamp}.log")
        self.objLogFile = open(self.strLogFilename, "w", encoding="utf-8")
        print(f"Logging to file: {self.strLogFilename}")
        
    def write(self, strMessage):
        self.objTerminal.write(strMessage)
        self.objLogFile.write(strMessage)
        self.objLogFile.flush()
        
    def flush(self):
        self.objTerminal.flush()
        self.objLogFile.flush()
    
    def stderrWrite(self, strMessage):
        self.objStderrTerminal.write(strMessage)
        self.objLogFile.write(f"ERROR: {strMessage}")
        self.objLogFile.flush()
        
    def stderrFlush(self):
        self.objStderrTerminal.flush()
        self.objLogFile.flush()
    
    def close(self):
        self.objLogFile.close()

def setupLogging(strSerialNumber=None):
    """
    * Set up logging to both console and file
    * Configures stdout and stderr redirection
    *
    * @param strSerialNumber Device serial number for log filename
    * @return Logger object
    """
    objLogger = Logger(strSerialNumber)
    sys.stdout = objLogger
    class StderrLogger:
        def write(self, strMessage):
            objLogger.stderrWrite(strMessage)
        def flush(self):
            objLogger.stderrFlush()
    
    sys.stderr = StderrLogger()
    return objLogger

def runCommand(strCommand, strCwd=None):
    """
    * Run command and return results with real-time character output
    * Creates separate threads for stdout and stderr processing
    *
    * @param strCommand Command to execute
    * @param strCwd Working directory for command execution
    * @return Tuple containing output lines and return code
    """
    print(f"Executing command: {strCommand}", end='', flush=True)
    print() 
    objProcess = subprocess.Popen(
        strCommand,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=True,
        cwd=strCwd,
        bufsize=0,  
        universal_newlines=False  
    )
    lstOutputLines = []
    strCurrentLine = ""
    def readStream(objStream, bIsError=False):
        while True:
            byteChar = objStream.read(1)
            if not byteChar:
                break
                
            try:
                strChar = byteChar.decode('utf-8', errors='replace')
                if bIsError:
                    sys.stderr.write(strChar)
                    sys.stderr.flush()
                else:
                    sys.stdout.write(strChar)
                    sys.stdout.flush()
                nonlocal strCurrentLine
                if strChar == '\n':
                    if strCurrentLine:
                        lstOutputLines.append(strCurrentLine)
                        strCurrentLine = ""
                else:
                    strCurrentLine += strChar
            except Exception as e:
                print(f"\nError processing output: {str(e)}", flush=True)
    objStdoutThread = threading.Thread(target=readStream, args=(objProcess.stdout, False))
    objStderrThread = threading.Thread(target=readStream, args=(objProcess.stderr, True))
    objStdoutThread.daemon = True
    objStderrThread.daemon = True
    objStdoutThread.start()
    objStderrThread.start()
    nReturncode = objProcess.wait()
    objStdoutThread.join(timeout=1.0)
    objStderrThread.join(timeout=1.0)
    if strCurrentLine:
        lstOutputLines.append(strCurrentLine)
    
    return lstOutputLines, nReturncode

def checkDeviceConnection(strToolPath):
    """
    * Check device connection status in Maskrom mode
    * Uses upgrade_tool to detect connected devices
    *
    * @param strToolPath Path to the upgrade tool directory
    * @return Boolean indicating device connection status
    """
    print("=== Checking Device Connection ===", flush=True)
    strCommand = f"{os.path.join(strToolPath, 'upgrade_tool')} LD"
    lstOutputLines, nReturnCode = runCommand(strCommand, cwd=strToolPath)
    bDeviceConnected = False
    for strLine in lstOutputLines:
        if "DevNo=" in strLine and "Mode=Maskrom" in strLine:
            bDeviceConnected = True
            break
    
    if not bDeviceConnected:
        print("Error: No device detected or device not in Maskrom mode", flush=True)
        return False
    
    print("Device connection normal, ready for firmware update", flush=True)
    return True

def updateFirmware(strToolPath, strImgPath):
    """
    * Update device firmware using upgrade tool
    * Flashes the firmware image to the connected device
    *
    * @param strToolPath Path to the upgrade tool directory
    * @param strImgPath Path to the firmware image file
    * @return Boolean indicating firmware update success
    """
    print("=== Starting Firmware Update ===", flush=True)
    if not os.path.isabs(strImgPath):
        strImgPath = os.path.join(strToolPath, strImgPath)
    
    strCommand = f"{os.path.join(strToolPath, 'upgrade_tool')} UF {strImgPath}"
    lstOutputLines, nReturnCode = runCommand(strCommand, cwd=strToolPath)
    bUpdateSuccess = False
    for strLine in lstOutputLines:
        if "Upgrade firmware ok" in strLine:
            bUpdateSuccess = True
            break
    
    if bUpdateSuccess:
        print("Firmware update successful!", flush=True)
        return True
    else:
        print("Error: Firmware update failed", flush=True)
        return False

def listComPorts():
    """
    * List all available COM ports in the system
    * Displays device name and description
    *
    * @return List of available COM ports
    """
    print("=== Available COM Ports ===", flush=True)
    lstPorts = list(serial.tools.list_ports.comports())
    
    if not lstPorts:
        print("No COM ports available", flush=True)
        return []
    
    for nIdx, objPort in enumerate(lstPorts):
        print(f"{nIdx+1}. {objPort.device} - {objPort.description}", flush=True)
    
    return lstPorts

def getComPortByNumber(nComNumber):
    """
    * Get COM port from port number
    * Converts number (e.g., 3) to device name (e.g., COM3)
    *
    * @param nComNumber COM port number
    * @return COM port device name or None if not found
    """
    strPortName = f"COM{nComNumber}"
    lstPorts = list(serial.tools.list_ports.comports())
    
    for objPort in lstPorts:
        if objPort.device.upper() == strPortName.upper():
            return objPort.device
    
    return None

def sendUartCommand(strComPort, strCommand, nBaudrate=115200, nTimeout=5, bWaitForResponse=True):
    """
    * Send a single command via UART and return success status
    * Manages serial port communication with the device
    * Automatically checks if response matches expected value
    *
    * @param strComPort COM port device name
    * @param strCommand Command to send
    * @param nBaudrate Communication baudrate
    * @param nTimeout Communication timeout in seconds
    * @param bWaitForResponse Whether to wait for device response
    * @return Boolean indicating success or failure of command
    """
    print(f"Sending UART command: {strCommand}", flush=True)
    strExpectedResponse = None
    if strCommand == "REQ_DC_IN":
        strExpectedResponse = "RES_DC_IN_OK"
    elif strCommand == "REQ_DC_OUT":
        strExpectedResponse = "RES_DC_OUT_OK"
    elif strCommand == "REQ_POWER_ON":
        strExpectedResponse = "RES_POWER_ON_OK"
    elif strCommand == "REQ_POWER_OFF":
        strExpectedResponse = "RES_POWER_OFF_OK"
    elif strCommand == "REQ_BOOT_ON":
        strExpectedResponse = "RES_BOOT_ON_OK"
    elif strCommand == "REQ_BOOT_OFF":
        strExpectedResponse = "RES_BOOT_OFF_OK"
    elif strCommand == "REQ_INIT":
        strExpectedResponse = "RES_INIT_OK"
    
    try:
        objSer = serial.Serial(strComPort, nBaudrate, timeout=nTimeout)
        objSer.reset_input_buffer()
        objSer.write((strCommand).encode('utf-8'))
        
        strResponse = ""
        if bWaitForResponse:
            fStartTime = time.time()
            while (time.time() - fStartTime) < nTimeout:
                if objSer.in_waiting:
                    objData = objSer.read(objSer.in_waiting)
                    try:
                        strDataStr = objData.decode('utf-8', errors='replace')
                        strResponse += strDataStr
                        sys.stdout.write(strDataStr)
                        sys.stdout.flush()
                    except Exception as e:
                        print(f"\nError decoding data: {str(e)}", flush=True)
                if strResponse and (time.time() - fStartTime) > 0.5:
                    time.sleep(0.5)
                    if not objSer.in_waiting:
                        break
                
                time.sleep(0.01)
    
        objSer.close()
        if strExpectedResponse:
            if strExpectedResponse in strResponse:
                print(f"Success: Received expected response: {strExpectedResponse}", flush=True)
                return True
            else:
                print(f"Warning: Expected response '{strExpectedResponse}' not found in command output", flush=True)
                return False
        
    except serial.SerialException as e:
        print(f"Error in UART communication: {str(e)}", flush=True)
        return False

def checkAndGetAdbDevice(strDeviceId=None, nMaxRetries=30):
    """
    * Check for available ADB devices and select one to use
    * Attempts to detect the specified device or auto-detect an available one
    *
    * @param strDeviceId Specific device ID to look for (optional)
    * @param nMaxRetries Maximum number of retry attempts
    * @return Tuple (success status, device ID if found, ADB command prefix)
    """
    print("Waiting for device to be available on ADB...")
    bAdbDeviceReady = False
    nRetryCount = 0
    
    while not bAdbDeviceReady and nRetryCount < nMaxRetries:
        try:
            lstAdbDevicesCmd = ['adb', 'devices']
            strDevicesOutput = subprocess.run(lstAdbDevicesCmd, capture_output=True, text=True).stdout
            if strDeviceId:
                bAdbDeviceReady = strDeviceId in strDevicesOutput
            else:
                lstLines = strDevicesOutput.strip().split('\n')
                for strLine in lstLines[1:]: 
                    if strLine and 'device' in strLine and 'emulator' not in strLine:
                        bAdbDeviceReady = True
                        if not strDeviceId:
                            strDeviceId = strLine.split()[0]
                            print(f"Auto-detected device: {strDeviceId}")
                            break
            
            if bAdbDeviceReady:
                print("Device is available on ADB")
                break
                
            print(".", end="", flush=True)
            time.sleep(1)
            nRetryCount += 1
            
        except Exception as e:
            print(f"Error checking ADB device: {str(e)}")
            time.sleep(1)
            nRetryCount += 1
    
    if not bAdbDeviceReady:
        print("\nError: Device not available on ADB after waiting")
        return False, None, None
    lstAdbPrefix = ['adb']
    if strDeviceId:
        lstAdbPrefix.extend(['-s', strDeviceId])
    
    return True, strDeviceId, lstAdbPrefix

def waitForTestCompletion(strSerialNumber, strStationName, strDeviceId=None, nTimeoutSeconds=300):
    """
    * Wait for test completion and pull log files from device
    * Monitors device via ADB and retrieves test result logs
    *
    * @param strSerialNumber Device serial number
    * @param strStationName Test station name
    * @param strDeviceId ADB device ID if multiple devices connected
    * @param nTimeoutSeconds Maximum time to wait for test completion
    * @return Boolean indicating test success
    """
    if not strSerialNumber:
        strSerialNumber = "00000000000"
    
    print(f"Waiting for test completion... (Serial: {strSerialNumber}, Station: {strStationName})")
    print(f"Timeout set to {nTimeoutSeconds} seconds")
    strLogDir = os.path.join(os.getcwd(), "CT1_LOG")
    if not os.path.exists(strLogDir):
        os.makedirs(strLogDir)
        print(f"Created output directory: {strLogDir}")
    bAdbDeviceReady, strDeviceId, lstAdbPrefix = checkAndGetAdbDevice(strDeviceId)
    if not bAdbDeviceReady:
        return False
    subprocess.run(lstAdbPrefix + ["shell", f"svc wifi enable"], capture_output=True, text=True)
    subprocess.run(lstAdbPrefix + ["shell", f"svc bluetooth enable"], capture_output=True, text=True)
    try:
        print("Setting up logcat monitoring...")
        subprocess.run(lstAdbPrefix + ['logcat', '-c'], check=True)
        lstLogcatCmd = lstAdbPrefix + ['logcat', '-v', 'time', 'CT1Broadcast:D', '*:S']
        objProcess = subprocess.Popen(
            lstLogcatCmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        
        print("Logcat monitoring started.")
        print("Sending test broadcast command...")
        lstBroadcastCmd = lstAdbPrefix + [
            'shell', 
            'am', 'broadcast', 
            '-n', 'com.rtk.ct1atptest/.domain.TestControlReceiver', 
            '-a', 'com.rtk.ct1atptest.PCATP', 
            '--es', 'SerialNumber', strSerialNumber, 
            '--es', 'StationName', strStationName
        ]
        
        objBroadcastResult = subprocess.run(lstBroadcastCmd, capture_output=True, text=True)
        if "Broadcast completed" not in objBroadcastResult.stdout:
            print(f"Error: Broadcast command may not have been successfully sent")
            print(f"Output: {objBroadcastResult.stdout}")
            print(f"Error: {objBroadcastResult.stderr}")
            return False
        
        print("Broadcast command sent successfully, waiting for test completion...")
        print("Monitoring logcat output, waiting for 'ATP Test Finish!!' message...")
        bTestSuccess = False
        fStartTime = time.time()
        objProcess.stdout.flush()
        while True:
            fElapsedTime = time.time() - fStartTime
            if fElapsedTime > nTimeoutSeconds:
                print(f"Error: Timeout after waiting {nTimeoutSeconds} seconds for test completion")
                return False
            if objProcess.poll() is not None:
                print("Error: Logcat process terminated unexpectedly")
                break
                
            strLine = objProcess.stdout.readline()
            if strLine:
                if "ATP Test Finish!!" in strLine:
                    print(f"\nDetected test completion message: {strLine.strip()}")
                    print("Waiting for log files to complete writing...")
                    time.sleep(2)
                    strLogPath = f"/storage/emulated/0/Android/data/com.rtk.ct1atptest/files/Logs/{strStationName}.txt"
                    print(f"Checking log file: {strLogPath}")
                    lstCheckCmd = lstAdbPrefix + ['shell', f'test -e "{strLogPath}" && echo "EXISTS" || echo "NOT_FOUND"']
                    objCheckResult = subprocess.run(lstCheckCmd, capture_output=True, text=True)
                    
                    if "EXISTS" not in objCheckResult.stdout:
                        print(f"Error: Log file not found: {strLogPath}")
                        return False
                    
                    print(f"Found log file: {strLogPath}")
                    strFilename = f"{strStationName}.txt"
                    strOutputPath = os.path.join(strLogDir, strFilename)
                    print(f"Downloading log file...")
                    lstPullCmd = lstAdbPrefix + ['pull', strLogPath, strOutputPath]
                    objPullResult = subprocess.run(lstPullCmd, capture_output=True, text=True)
                    
                    if "1 file pulled" in objPullResult.stderr:
                        print(f"Success! Log file saved to: {strOutputPath}")
                        bTestSuccess = True
                    else:
                        print(f"Error: Could not download log file")
                        print(f"Error message: {objPullResult.stderr}")
                    
                    break
            else:
                time.sleep(0.1)
            if int(fElapsedTime) % 30 == 0 and int(fElapsedTime) > 0:
                fRemaining = nTimeoutSeconds - fElapsedTime
                print(f"Still waiting... {int(fRemaining)} seconds remaining", flush=True)
        
        return bTestSuccess
    
    except KeyboardInterrupt:
        print("\nOperation interrupted by user")
        return False
    except Exception as e:
        print(f"Error: {str(e)}")
        return False
    finally:
        if 'objProcess' in locals():
            objProcess.terminate()

def settingWiFi11Gchannel7():
    """
    * Configure WiFi settings for 11G channel 7 using low-level wl commands
    * Sets up WiFi in test mode with specific transmit parameters
    *
    * @return Boolean indicating success or failure of the WiFi configuration
    """
    print("\n=== Setting WiFi to 2.4GHz (11G) Channel 7 (Test Mode) ===")
    bAdbDeviceReady, strDeviceId, lstAdbPrefix = checkAndGetAdbDevice()
    if not bAdbDeviceReady:
        print("Error: Cannot configure WiFi - No ADB device available")
        return False
    
    try:
        print("Configuring WiFi test settings using wl commands...")
        lstWifiCommands = [
            ['root'],
            ['shell', 'svc', 'wifi', 'enable'],
            ['sleep', '2'],
            ['shell', 'ifconfig', 'wlan0', 'up'],
            ['shell', 'wl', 'down'],
            ['shell', 'wl', 'mpc', '0'],
            ['shell', 'wl', 'country', 'ALL'],
            ['shell', 'wl', 'band', 'b'],  
            ['shell', 'wl', 'up'],
            ['shell', 'wl', '2g_rate', '-h', '7', '-b', '20'],
            ['shell', 'wl', 'chanspec', '7/20'],
            ['shell', 'wl', 'phy_watchdog', '0'],
            ['shell', 'wl', 'scansuppress', '1'],
            ['shell', 'wl', 'phy_watchdog', '0'],
            ['shell', 'wl', 'phy_forcecal', '1'],
            ['shell', 'wl', 'phy_txpwrctrl', '1'],
            ['shell', 'wl', 'txpwr1', '-1'],
            ['shell', 'wl', 'pkteng_start', '00:90:4c:14:43:19', 'tx', '100', '1000', '0']
        ]
        for lstCmd in lstWifiCommands:
            if lstCmd[0] == 'sleep':
                time.sleep(int(lstCmd[1]))
                continue
            strCmdDesc = ' '.join(lstCmd)
            print(f"Executing: {strCmdDesc}")
            lstFullCmd = lstAdbPrefix + lstCmd
            objResult = subprocess.run(lstFullCmd, capture_output=True, text=True)
            if objResult.returncode != 0:
                print(f"Warning: Command may have failed: {strCmdDesc}")
                print(f"Error output: {objResult.stderr}")
        
        print("WiFi 2.4GHz Channel 7 test mode configuration completed")
        return True
            
    except Exception as e:
        print(f"Error configuring WiFi test mode: {str(e)}")
        return False

def settingBTTXTest():
    """
    * Configure Bluetooth for TX test mode using ADB commands
    * Sets up Bluetooth device for testing
    *
    * @return Boolean indicating success or failure of the Bluetooth configuration
    """
    print("\n=== Setting Bluetooth TX Test Mode ===")
    bAdbDeviceReady, strDeviceId, lstAdbPrefix = checkAndGetAdbDevice()
    if not bAdbDeviceReady:
        print("Error: Cannot configure Bluetooth - No ADB device available")
        return False
    
    try:
        print("Configuring Bluetooth test settings...")
        rootCmd = lstAdbPrefix + ["root"]
        objResult = subprocess.run(rootCmd, capture_output=True, text=True)
        print("Wait for a while to get root access...")
        time.sleep(1)
        closeBTCmd = lstAdbPrefix +['shell', 'svc', 'bluetooth', 'disable']
        objResult = subprocess.run(closeBTCmd, capture_output=True, text=True)
        closeWiFiCmd = lstAdbPrefix +['shell', 'wl', 'down']
        objResult = subprocess.run(closeWiFiCmd, capture_output=True, text=True)
        pushCmd = lstAdbPrefix + ["push", "./bt_script.sh", "/data/local/tmp/"]
        objResult = subprocess.run(pushCmd, capture_output=True, text=True)
        if objResult.returncode != 0:
            print(f"Error: Failed to push script to device")
            print(f"Error output: {objResult.stderr}")
            return False
        print("Executing Bluetooth commands...")
        chmodCmd = lstAdbPrefix + ["shell", "chmod 777 /data/local/tmp/bt_script.sh"]
        subprocess.run(chmodCmd, capture_output=True, text=True)
                
        runCmd = lstAdbPrefix + ["shell", "/data/local/tmp/bt_script.sh"]
        objResult = subprocess.run(runCmd, capture_output=True, text=True)
        print(objResult.stdout)
        if objResult.stderr:
            print(f"Warning: Bluetooth script execution may have issues:")
            print(f"Error output: {objResult.stderr}")
        cleanupCmd = lstAdbPrefix + ["shell", "rm /data/local/tmp/bt_script.sh"]
        subprocess.run(cleanupCmd, capture_output=True, text=True)
        print("Bluetooth TX test mode configuration completed")
        return True
            
    except Exception as e:
        print(f"Error configuring Bluetooth test mode: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    
def getIQxelValue(strIQxelPath,strModel="WiFi"):
    """
    * Get IQxel test result and extract signal power value
    * Executes IQxel Console.exe and parses the output for signal power
    *
    * @param strIQxelPath Path to IQxel directory
    * @param strModel Test model type ("WiFi" or "BT")
    * @return Float value of signal power in dBm, or None if not found
    """
    print("=== Get IQxel Test Result ===", flush=True)
    if(strModel == "WiFi"):
        strCommand = f"{os.path.join(strIQxelPath, 'Console.exe')} -isWiFiTest true"
    elif(strModel == "BT"):
        strCommand = f"{os.path.join(strIQxelPath, 'Console.exe')} -isWiFiTest false"
    try:
        original_dir = os.getcwd()
        try:
            os.chdir(strIQxelPath)
            lstOutputLines, nReturnCode = runCommand(strCommand)
        finally:
            os.chdir(original_dir)
        if nReturnCode != 0:
            print(f"Warning: IQxel command returned non-zero code: {nReturnCode}")
    except Exception as e:
            print(f"Error executing IQxel command: {str(e)}")
            return None
    
    fSignalPower = None
    for strLine in lstOutputLines:
        if "Signal power:" in strLine:
            try:
                strValue = strLine.split("Signal power:")[1].strip()
                fSignalPower = float(strValue.replace("dBm", "").strip())
                print(f"Found signal power: {fSignalPower} dBm")
                break
            except (ValueError, IndexError) as e:
                print(f"Error parsing signal power value: {str(e)}")
                return None
    
    return fSignalPower

def setupGPIB():
    """
    * Initialize GPIB system using PyVISA
    * Sets up resource manager for GPIB communication
    *
    * @return PyVISA resource manager if successful, None otherwise
    """
    try:
        print("=== Setting up GPIB system ===", flush=True)
        rm = pyvisa.ResourceManager()
        resources = rm.list_resources()
        print(f"Available VISA resources: {resources}", flush=True)
        gpib_address = None
        for res in resources:
            if res.startswith("GPIB"):
                gpib_address = res
                break
        return True,rm,gpib_address
    except Exception as e:
        print(f"Error setting up GPIB: {str(e)}", flush=True)
        return False,None,None

def connectGPIB(rm, address):
    """
    * Connect to a specific GPIB instrument
    * Opens connection to device at specified GPIB address
    *
    * @param rm PyVISA resource manager
    * @param address GPIB address (e.g., 'GPIB0::22::INSTR')
    * @return PyVISA instrument object if connection successful, None otherwise
    """
    try:
        print(f"=== Connecting to GPIB device: {address} ===", flush=True)
        instrument = rm.open_resource(address)
        # Set default timeout to 5 seconds
        instrument.timeout = 5000
        
        # Get instrument identification
        idn = instrument.query("*IDN?").strip()
        print(f"Connected to: {idn}", flush=True)
        return instrument
    except Exception as e:
        print(f"Error connecting to GPIB device {address}: {str(e)}", flush=True)
        return None

def sendGPIBCommand(instrument, command):
    """
    * Send command to GPIB instrument without expecting response
    * Used for setting parameters or triggering actions
    *
    * @param instrument PyVISA instrument object
    * @param command Command string to send
    * @return Boolean indicating success or failure
    """
    try:
        print(f"Sending GPIB command: {command}", flush=True)
        instrument.write(command)
        return True
    except Exception as e:
        print(f"Error sending GPIB command: {str(e)}", flush=True)
        return False

def queryGPIB(instrument, query):
    """
    * Send query to GPIB instrument and return response
    * Used for requesting data or status information
    *
    * @param instrument PyVISA instrument object
    * @param query Query string to send
    * @return Response string if successful, None otherwise
    """
    try:
        print(f"Querying GPIB: {query}", flush=True)
        response = instrument.query(query).strip()
        print(f"Response: {response}", flush=True)
        return response
    except Exception as e:
        print(f"Error querying GPIB: {str(e)}", flush=True)
        return None

def closeGPIB(instrument):
    """
    * Close connection to GPIB instrument
    * Properly terminates the GPIB connection
    *
    * @param instrument PyVISA instrument object
    * @return Boolean indicating success or failure
    """
    try:
        print("Closing GPIB connection", flush=True)
        instrument.close()
        return True
    except Exception as e:
        print(f"Error closing GPIB connection: {str(e)}", flush=True)
        return False

def settingLTETXTest(iLteBand):
    """
    * Configure LTE for TX test mode using AT commands
    * Sets up LTE device for testing based on specified band
    *
    * @param iLteBand LTE band to configure (e.g., 1 or 26)
    * @return Boolean indicating success or failure of the LTE configuration
    """
    print(f"\n=== Setting LTE Band {iLteBand} TX Test Mode ===")
    bAdbDeviceReady, strDeviceId, lstAdbPrefix = checkAndGetAdbDevice()
    if not bAdbDeviceReady:
        print("Error: Cannot configure LTE test mode - No ADB device available")
        return False
    
    try:
        
        subprocess.run(lstAdbPrefix + ["root"], capture_output=True, text=True)
        time.sleep(1)
        logPath = "/data/local/tmp/rxlog.txt"
        subprocess.run(lstAdbPrefix + ["shell", f"rm -f {logPath}"], capture_output=True, text=True)
        subprocess.run(lstAdbPrefix + ["shell", f"nohup cat /dev/ttyUSB2 > {logPath} 2>&1 &"], capture_output=True, text=True)
        time.sleep(1)
        print("Configuring LTE test settings...")
        rootCmd = lstAdbPrefix + ["root"]
        objResult = subprocess.run(rootCmd, capture_output=True, text=True)
        print("Wait for a while to get root access...")
        time.sleep(1)
        print("Entering RF test mode...")
        rfTestCmd = lstAdbPrefix + ['shell', 'echo "AT+QRFTESTMODE=1\\r\\n" > /dev/ttyUSB2']
        objResult = subprocess.run(rfTestCmd, capture_output=True, text=True)
        if objResult.returncode != 0:
            print(f"Error: Failed to enter RF test mode")
            print(f"Error output: {objResult.stderr}")
            return False  
        time.sleep(1)
        if iLteBand == 1:
            print("Configuring LTE Band 1...")
            lteCmd = lstAdbPrefix + ['shell', 'echo "AT+QRFTEST=\\"LTE BAND1\\",18300,\\"ON\\",70,1\\r\\n" > /dev/ttyUSB2']
        elif iLteBand == 26:
            print("Configuring LTE Band 26...")
            lteCmd = lstAdbPrefix + ['shell', 'echo "AT+QRFTEST=\\"LTE BAND26\\",26865,\\"ON\\",70,1\\r\\n" > /dev/ttyUSB2']
        else:
            print(f"Error: Unsupported LTE band {iLteBand}")
            return False
            
        objResult = subprocess.run(lteCmd, capture_output=True, text=True)
        if objResult.returncode != 0:
            print(f"Error: Failed to configure LTE Band {iLteBand}")
            print(f"Error output: {objResult.stderr}")
            return False
            
        print(f"LTE Band {iLteBand} TX test mode configuration completed")
        return True
            
    except Exception as e:
        print(f"Error configuring LTE test mode: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def getLTERXResult(iLteBand,fRxThreshold):
    """
    * Get LTE RX test result using AT commands
    * Sends RX test commands and parses response value
    *
    * @param iLteBand LTE band to test (e.g., 1 or 26)
    * @return Float value of RX signal power if successful, None otherwise
    """
    print(f"\n=== Getting LTE Band {iLteBand} RX Test Result ===")
    bAdbDeviceReady, strDeviceId, lstAdbPrefix = checkAndGetAdbDevice()
    if not bAdbDeviceReady:
        print("Error: Cannot get LTE RX test result - No ADB device available")
        return None
    
    maxRetry = 3
    retryCount = 0
    logPath = "/data/local/tmp/rxlog.txt"
    try:
        while retryCount < maxRetry:
            if iLteBand == 1:
                lteCmd = lstAdbPrefix + ['shell', 'echo "AT+QRFTEST=\\"LTE BAND1\\",18300,\\"ON\\",70,1\\r\\n" > /dev/ttyUSB2']
            elif iLteBand == 26:
                lteCmd = lstAdbPrefix + ['shell', 'echo "AT+QRFTEST=\\"LTE BAND26\\",26865,\\"ON\\",70,1\\r\\n" > /dev/ttyUSB2']
            else:
                print(f"Error: Unsupported LTE band {iLteBand}")
                return None
            subprocess.run(lteCmd, capture_output=True, text=True)
            time.sleep(1)
            if iLteBand == 1:
                atCommand = 'printf "AT+QRXFTM=1,1,300,0,0,3\\r\\n" > /dev/ttyUSB2'
            elif iLteBand == 26:
                atCommand = 'printf "AT+QRXFTM=1,18,8865,0,0,3\\r\\n" > /dev/ttyUSB2'
            else:
                return None
            subprocess.run(lstAdbPrefix + ['shell', atCommand], capture_output=True, text=True)
            time.sleep(2)
            objReadResult = subprocess.run(lstAdbPrefix + ['shell', f'cat {logPath}'], capture_output=True, text=True)
            print(f"Captured output:\n{objReadResult.stdout}")
            matches = re.findall(r'\+QRXFTM:\s*(-?\d+),\s*(-?\d+)', objReadResult.stdout)
            if matches:
                lastMatch = matches[-1]
                fMeasured = float(lastMatch[1])  
                print(f"Parsed LTE RX value (latest): {fMeasured} dBm")

                if fMeasured >= fRxThreshold:
                    print(f"PASS: {fMeasured} >= {fRxThreshold}")
                    return fMeasured
                else:
                    print(f"RETRY: {fMeasured} < {fRxThreshold}")
            else:
                print("No valid +QRXFTM result found")
            
            retryCount += 1
            time.sleep(1)

    except Exception as e:
        print(f"Exception occurred: {e}")
        import traceback
        traceback.print_exc()

    finally:
        subprocess.run(lstAdbPrefix + ['shell', 'pkill -f "cat /dev/ttyUSB2"'], capture_output=True, text=True)
        subprocess.run(lstAdbPrefix + ["shell", f"rm -f {logPath}"], capture_output=True, text=True)


    print(f"FAILED: Exceeded maximum retries ({maxRetry}) without valid result.")
    return None

def loadConfigFile(strConfigFile="./CT1.yaml"):
    """
    * Load and parse YAML configuration file for CT1 testing system
    * Provides centralized configuration management for test parameters and thresholds
    * Falls back to default values if file is not found or cannot be parsed
    *
    * @param strConfigFile Path to the YAML configuration file (default: "CT1.yaml")
    * @return Dictionary containing configuration values, or None if loading fails
    """
    import yaml
    try:
        if os.path.exists(strConfigFile):
            print(f"Loading configuration from: {strConfigFile}")
            with open(strConfigFile, 'r') as f:
                dictConfig = yaml.safe_load(f)
                
            if not dictConfig:
                print("Warning: Config file is empty, using default values")
                return None
                
            print("Configuration loaded successfully")
            return dictConfig
        else:
            print(f"Warning: Config file '{strConfigFile}' not found, using default values")
            return None
    except Exception as e:
        print(f"Error loading config file: {str(e)}")
        print("Using default configuration values")
        return None
