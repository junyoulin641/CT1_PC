#!/usr/bin/env python3
import time
from common import (
    sendUartCommand,
    waitForTestCompletion,
    settingWiFi11Gchannel7,
    getIQxelValue,
    settingBTTXTest,
    setupGPIB,
    connectGPIB,
    sendGPIBCommand,
    queryGPIB,
    closeGPIB,
    settingLTETXTest,
    getLTERXResult
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
        time.sleep(0.5)
        print("------Test: BT TX Configuration------")
        if not settingBTTXTest():
            print("Error: Failed to configure BT")
            return False
        fSignalPower=getIQxelValue(strIQxelPath,"BT")
        if fSignalPower == None:
            print("Error: Failed to get IQxel BT Signal Power")
            return False
             
        print("------Test: GPIB Communication------")
        bCheckGPIB, rm, strGPIBAddress = setupGPIB()
        if not bCheckGPIB or strGPIBAddress is None:
            print("Error: Not Find GPIB Devices")
            return False
            
        instrument = connectGPIB(rm, strGPIBAddress)
        if instrument is None:
            print("Error: Failed to connect to GPIB instrument")
            return False
        print("------Sending GPIB commands sequence------")
        gpib_commands = [
            "CALLPROC OFF",
            "BANDWIDTH 10MHZ",
            "BAND 1",
            "ULCHAN 18300",
            "TESTPRM TX_MAXPWR_Q_1",
            "PWR_AVG 20"
        ]
            
        for cmd in gpib_commands:
            if not sendGPIBCommand(instrument, cmd):
                print(f"Error: Failed to send GPIB command: {cmd}")
                closeGPIB(instrument)
                return False
            time.sleep(0.5)
        time.sleep(1)
        print("------Test: LTE Band 1 TX Configuration------")
        if not settingLTETXTest(1):
            print("Error: Failed to configure LTE Band 1 TX test")
            closeGPIB(instrument)
            return False
        time.sleep(1)    
        if not sendGPIBCommand(instrument, "SWP"):
                print(f"Error: Failed to send GPIB command: SWP")
                closeGPIB(instrument)
                return False
        time.sleep(1)  
        print("------Querying GPIB for LTE TX power value------")
        strPowerValue = queryGPIB(instrument, "POWER? AVG")
        if strPowerValue is None:
            print("Error: Failed to get power value from GPIB")
            closeGPIB(instrument)
            return False
        try:
            fPowerValue = float(strPowerValue)
            print(f"LTE TX Power Value: {fPowerValue}")
        except ValueError:
            print(f"Error: Invalid power value format: {strPowerValue}")
            closeGPIB(instrument)
            return False
            
        print("------Test: LTE Band 1 RX Test------")
        print("------Setting RX test parameters------")
        if not sendGPIBCommand(instrument, "TESTPRM RX_MAX"):
            print("Error: Failed to set RX test parameters")
            closeGPIB(instrument)
            return False
        time.sleep(1)
        fRxValue = getLTERXResult(1,-50)
        if fRxValue is None:
            print("Error: Failed to get LTE Band 1 RX test result")
            closeGPIB(instrument)
            return False
        print(f"LTE Band 1 RX Test Result: {fRxValue}")
        print("------Test: LTE Band 26 TX Configuration------")
        gpib_commands = [
            "CALLPROC OFF",
            "BANDWIDTH 10MHZ",
            "BAND 26",
            "TESTPRM TX_MAXPWR_Q_1",
            "PWR_AVG 20"
        ]    
        for cmd in gpib_commands:
            if not sendGPIBCommand(instrument, cmd):
                print(f"Error: Failed to send GPIB command: {cmd}")
                closeGPIB(instrument)
                return False
            time.sleep(0.5)
        time.sleep(1)
        if not settingLTETXTest(26):
            print("Error: Failed to configure LTE Band 26 TX test")
            closeGPIB(instrument)
            return False
        time.sleep(1)        
        if not sendGPIBCommand(instrument, "SWP"):
            print(f"Error: Failed to send GPIB command: SWP")
            closeGPIB(instrument)
            return False
        time.sleep(1)  
        print("------Querying GPIB for LTE TX power value------")
        strPowerValue = queryGPIB(instrument, "POWER? AVG")
        if strPowerValue is None:
            print("Error: Failed to get power value from GPIB")
            closeGPIB(instrument)
            return False
        try:
            fPowerValue = float(strPowerValue)
            print(f"LTE TX Power Value: {fPowerValue}")
        except ValueError:
            print(f"Error: Invalid power value format: {strPowerValue}")
            closeGPIB(instrument)
            return False    
        print("------Test: LTE Band 26 RX Test------")
        print("------Setting RX test parameters------")
        if not sendGPIBCommand(instrument, "TESTPRM RX_MAX"):
            print("Error: Failed to set RX test parameters")
            closeGPIB(instrument)
            return False
        time.sleep(2)
        fRxValue = getLTERXResult(26,-50)
        if fRxValue is None:
            print("Error: Failed to get LTE Band 26 RX test result")
            closeGPIB(instrument)
            return False
        print(f"LTE Band 26 RX Test Result: {fRxValue}")
        print("------Starting CT1 SARF test------")
        if not waitForTestCompletion(strSerialNumber, strStationName, strDeviceId, nTimeoutSeconds=nTimeoutSeconds):
            print("Error: SARF test failed or log file not found")
            return False
        
        print("SARF process completed successfully")
        return True
        
    except Exception as e:
        print(f"Error in SARF process: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        closeGPIB(instrument)
        print("Sending final cleanup commands to reset the device")
        try:
            if sendUartCommand(strComPort, "REQ_INIT"):
                print("Device reset completed successfully")
            else:
                print("Warning: Device reset may not have completed properly")
        except Exception as e:
            print(f"Warning: Failed to complete cleanup commands: {str(e)}") 