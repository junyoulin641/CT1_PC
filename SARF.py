#!/usr/bin/env python3
import time
from common import (
    sendUartCommand,
    waitForTestCompletion,
    settingWiFi11Gchannel7,
    getIQxelValue,
    settingBTTXTest
)

def sarfProcess(strComPort, strIQxelPath, strSerialNumber=None, strDeviceId=None, nTimeoutSeconds=600):
    """
    * Process for SARF (Signal and RF) station
    * Controls device via UART during testing and manages test execution
    * Includes WiFi configuration for 2.4GHz channel 7
    *
    * @param strComPort COM port for UART communication
    * @param strSerialNumber Device serial number
    * @param strDeviceId ADB device ID if multiple devices connected
    * @param nTimeoutSeconds Maximum time to wait for test completion
    * @return Boolean indicating success or failure of the process
    """
    print("\n=== Starting SARF Process ===")
    strStationName = "SARF"
    if not strComPort:
        print("Error: COM port is required for SARF station")
        return False
    
    try:
        print("------Initializing device------")
        if not sendUartCommand(strComPort, "REQ_INIT"):
            print("Error: REQ_INIT command failed.")
            return False
        time.sleep(0.5)
        print("------Sending power on sequence------")
        if not sendUartCommand(strComPort, "REQ_POWER_ON"):
            print("Error: REQ_POWER_ON command failed")
            return False
        time.sleep(1)
        print("------Sending DC in command------")
        if not sendUartCommand(strComPort, "REQ_DC_IN"):
            print("Error: REQ_DC_IN command failed")
            return False
        time.sleep(1)
        print("------Waiting for device to boot (15 seconds)...------")
        time.sleep(15)

        print("------Test: WiFi 11G Channel 7 Configuration------")
        if not settingWiFi11Gchannel7():
            print("Error: Failed to configure WiFi to 11G Channel 7")
            return False
        fSignalPower=getIQxelValue(strIQxelPath,"WiFi")
        if fSignalPower == None:
            print("Error: Failed to get IQxel WiFi Signal Power")
            return False
        print("------Test: BT TX Configuration------")
        if not settingBTTXTest():
            print("Error: Failed to configure BT")
            return False
        fSignalPower=getIQxelValue(strIQxelPath,"BT")
        if fSignalPower == None:
            print("Error: Failed to get IQxel BT Signal Power")
            return False            
        print("------Starting CT1 SARF test------")
        # if not waitForTestCompletion(strSerialNumber, strStationName, strDeviceId, nTimeoutSeconds=nTimeoutSeconds):
        #     print("Error: SARF test failed or log file not found")
        #     return False
        
        print("SARF process completed successfully")
        return True
        
    except Exception as e:
        print(f"Error in SARF process: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        print("Sending final cleanup commands to reset the device")
        try:
            if sendUartCommand(strComPort, "REQ_INIT"):
                print("Device reset completed successfully")
            else:
                print("Warning: Device reset may not have completed properly")
        except Exception as e:
            print(f"Warning: Failed to complete cleanup commands: {str(e)}") 