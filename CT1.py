#!/usr/bin/env python3
import argparse
import os
import sys
from datetime import datetime

from common import (
    setupLogging,
    getComPortByNumber,
    waitForTestCompletion
)

from ATPFWDL import atpfwdlProcess
from SARF import sarfProcess

def main():
    """
    * Main function that handles command-line arguments and executes appropriate station processes
    * Manages the overall workflow of the CT1 Device Management Tool
    *
    * @return Boolean indicating success or failure of the process
    """
    objParser = argparse.ArgumentParser(description="CT1 Device Management Tool")
    objParser.add_argument("--SerialNumber", help="Device serial number")
    objParser.add_argument("--StationName", help="Test station name")
    objParser.add_argument("--device", help="ADB device ID (if multiple devices connected)")
    objParser.add_argument("--comport", type=int, help="COM port number (e.g., 3 for COM3)", nargs='?', const=None)
    objParser.add_argument("--timeout", type=int, default=600, help="Test completion timeout in seconds (default: 300)")
    
    objArgs = objParser.parse_args()
    objLogger = setupLogging(objArgs.SerialNumber)
    objStartTime = datetime.now()
    print(f"=== CT1 Device Management Tool ===")
    print(f"Start time: {objStartTime.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Parameters: {' '.join(sys.argv[1:])}")
    
    try:
        strDLToolPath = os.path.abspath("upgrade_tool_v2.33_for_window")
        strIQxelPath= os.path.abspath("IQxel")
        strOSImgPath = "update.img"
        print(f"Upgrade tool path: {strDLToolPath}")
        if not os.path.exists(os.path.join(strDLToolPath, "upgrade_tool.exe")):
            print(f"Error: Upgrade tool not found at path {strDLToolPath}")
            return False
        if not os.path.exists(os.path.join(strDLToolPath, "update.img")):
            print(f"Error: Update image not found at path {strDLToolPath}")
            return False
        strComPort = None
        if objArgs.comport is not None:
            strComPort = getComPortByNumber(objArgs.comport)
            if not strComPort:
                print(f"Error: COM{objArgs.comport} not found")
                return False
            print(f"Using COM port: {strComPort}")
        if objArgs.StationName == "ATPFWDL":
            if not strComPort:
                print("Error: ATPFWDL station requires COM port specification")
                return False
            bResult = atpfwdlProcess(
                strComPort=strComPort,
                strToolPath=strDLToolPath,
                strImgPath=strOSImgPath,
                strSerialNumber=objArgs.SerialNumber,
                strDeviceId=objArgs.device
            )
        elif objArgs.StationName == "SARF":
            if not strComPort:
                print("Error: SARF station requires COM port specification")
                return False
            
            bResult = sarfProcess(
                strComPort=strComPort,
                strIQxelPath=strIQxelPath,
                strSerialNumber=objArgs.SerialNumber,
                strDeviceId=objArgs.device,
                nTimeoutSeconds=objArgs.timeout
            )
        elif objArgs.StationName:
            bResult = waitForTestCompletion(
                objArgs.SerialNumber,
                objArgs.StationName,
                strDeviceId=objArgs.device,
                nTimeoutSeconds=objArgs.timeout
            )
        else:
            print("Error: StationName parameter is required")
            print("Usage examples:")
            print("For ATPFWDL station: python CT1.py --StationName ATPFWDL --comport 3 --SerialNumber 123456")
            print("For SARF station: python CT1.py --StationName SARF --comport 3 --SerialNumber 123456")
            print("For other stations: python CT1.py --StationName PreUI --SerialNumber 123456")
            bResult = False
            
        # Print end time and elapsed time
        objEndTime = datetime.now()
        objElapsedTime = objEndTime - objStartTime
        print(f"\n=== Process Completed ===")
        print(f"End time: {objEndTime.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Elapsed time: {objElapsedTime}")
        
        return bResult
        
    finally:
        # Close logger
        if 'objLogger' in locals():
            objLogger.close()
            # Restore original stdout and stderr
            sys.stdout = sys.__stdout__
            sys.stderr = sys.__stderr__

if __name__ == "__main__":
    try:
        bSuccess = main()
        if bSuccess:
            print("Result: PASS")
            sys.exit(0)
        else:
            print("Result: FAIL")
            sys.exit(1)
    except Exception as e:
        print(f"Error occurred: {str(e)}")
        print("Result: FAIL")
        sys.exit(1)
