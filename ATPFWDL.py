#!/usr/bin/env python3
import time
from common import (
    sendUartCommand, 
    checkDeviceConnection, 
    updateFirmware, 
    waitForTestCompletion
)

def atpfwdlProcess(strComPort, strToolPath, strImgPath, strSerialNumber=None, strDeviceId=None):
    """
    * Special process for ATPFWDL (ATP Firmware Download) station
    * Handles device boot sequence, firmware update, and test execution
    *
    * @param strComPort COM port for UART communication
    * @param strToolPath Path to upgrade tool directory
    * @param strImgPath Path to firmware image file
    * @param strSerialNumber Device serial number
    * @param strDeviceId ADB device ID if multiple devices connected
    * @return Boolean indicating success or failure of the process
    """
    print("\n=== Starting ATPFWDL Process ===")
    strStationName = "ATPFWDL"
    bProcessResult = False
    
    if not strComPort:
        print("Error: COM port is required for ATPFWDL station")
        return False
    
    try:
        print("------Sending boot sequence commands------")
        if not sendUartCommand(strComPort, "REQ_INIT"):
            print("Error: REQ_INIT command failed")
            return False
        time.sleep(0.5)
        if not sendUartCommand(strComPort, "REQ_BOOT_ON"):
            print("Error: REQ_BOOT_ON command failed")
            return False
        time.sleep(0.5)
        if not sendUartCommand(strComPort, "REQ_POWER_ON"):
            print("Error: REQ_POWER_ON command failed")
            return False
        time.sleep(0.5)
        if not sendUartCommand(strComPort, "REQ_DC_IN"):
            print("Error: REQ_DC_IN command failed")
            return False
        print("Waiting for device to enter Maskrom mode (5 seconds)...")
        time.sleep(2)
        print("------Checking device connection------")
        nRetryCount = 0
        nMaxRetries = 3
        bConnectionSuccess = False
        
        while not bConnectionSuccess and nRetryCount < nMaxRetries:
            if checkDeviceConnection(strToolPath):
                bConnectionSuccess = True
                break
            
            print(f"Retry {nRetryCount+1}/{nMaxRetries} checking device connection...")
            nRetryCount += 1
            time.sleep(2)
        
        if not bConnectionSuccess:
            print("Error: Device connection failed after boot sequence")
            return False
        print("------Sending REQ_BOOT_OFF command------")
        if not sendUartCommand(strComPort, "REQ_BOOT_OFF"):
            print("Warning: REQ_BOOT_OFF command may have failed. Continuing anyway...")
        time.sleep(1)
        print("Step 4: Updating firmware")
        if not updateFirmware(strToolPath, strImgPath):
            print("Error: Firmware update failed")
            return False
        
        print("Firmware update successful")
        print("------Waiting for device to reboot (90 seconds)...------")
        time.sleep(90) 
        print("------Starting ATP test------")
        if not waitForTestCompletion(strSerialNumber, strStationName, strDeviceId, nTimeoutSeconds=300):
            print("Error: ATP test failed or log file not found")
            return False
        
        print("ATPFWDL process completed successfully")
        bProcessResult = True
        return True
        
    except Exception as e:
        print(f"Error in ATPFWDL process: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        print("Sending final REQ_INIT command to reset the device")
        try:
            if sendUartCommand(strComPort, "REQ_INIT"):
                print("Device reset completed successfully")
            else:
                print("Warning: Device reset may not have completed properly")
        except Exception as e:
            print(f"Warning: Failed to send final REQ_INIT command: {str(e)}") 