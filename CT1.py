#!/usr/bin/env python3
import subprocess
import argparse
import os
import time
import re
from datetime import datetime

def wait_for_test_completion(serial_number, station_name, device_id=None):
    """
    等待測試完成並從設備拉取日誌檔案
    
    Args:
        serial_number: 設備序號
        station_name: 測試站名稱
        device_id: ADB 設備 ID (如果有多個設備連接)
    """
    serial_number="00000000000"
    station_name="PreUI"
    print(f"等待測試完成... (序號: {serial_number}, 測試站: {station_name})")
    
    # 確保輸出目錄存在
    log_dir = os.path.join(os.getcwd(), "LOG")
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
        print(f"創建輸出目錄: {log_dir}")
    
    # 設置 ADB 命令前綴
    adb_prefix = ['adb']
    if device_id:
        adb_prefix.extend(['-s', device_id])
    
 # 發送測試廣播命令
    print("發送測試廣播命令...")
    broadcast_cmd = adb_prefix + [
        'shell', 
        'am', 'broadcast', 
        '-n', 'com.rtk.ct1atptest/.domain.TestControlReceiver', 
        '-a', 'com.rtk.ct1atptest.PCATP', 
        '--es', 'SerialNumber', serial_number, 
        '--es', 'StationName', station_name
    ]
    
    try:
        broadcast_result = subprocess.run(broadcast_cmd, capture_output=True, text=True)
        if "Broadcast completed" not in broadcast_result.stdout:
            print(f"錯誤: 廣播命令可能未成功發送")
            print(f"輸出: {broadcast_result.stdout}")
            print(f"錯誤: {broadcast_result.stderr}")
            return
        
        print("廣播命令發送成功，開始等待測試完成...")
    
        # 設置 logcat 命令來監聽 TEST_RESULT 標籤
        # 先清除現有的 logcat 緩衝區，確保我們只捕獲新的日誌
        subprocess.run(adb_prefix + ['logcat', '-c'], check=True)
        
        logcat_cmd = adb_prefix + ['logcat', '-v', 'time', 'TEST_RESULT:D', '*:S']
        
        # 啟動 logcat 進程
        process = subprocess.Popen(
            logcat_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        
        print("監聽 logcat 輸出，等待 'ATP Test Finish!!' 訊息...")
        
        # 處理 logcat 輸出
        while True:
            line = process.stdout.readline()
            if not line:
                break
                
            # 檢查是否包含目標訊息
            if "ATP Test Finish!!" in line:
                print(f"\n偵測到測試完成訊息: {line.strip()}")
                
                # 給系統一點時間來確保日誌檔案完全寫入
                print("等待日誌檔案完成寫入...")
                time.sleep(2)
                
                # 尋找特定的日誌檔案 - 使用您指定的路徑和格式
                log_path = f"/storage/emulated/0/Android/data/com.rtk.ct1atptest/files/Logs/{station_name}.txt"
                print(f"檢查日誌檔案: {log_path}")
                
                # 檢查檔案是否存在
                check_cmd = adb_prefix + ['shell', f'test -e "{log_path}" && echo "EXISTS" || echo "NOT_FOUND"']
                check_result = subprocess.run(check_cmd, capture_output=True, text=True)
                
                if "EXISTS" not in check_result.stdout:
                    print(f"錯誤: 找不到日誌檔案: {log_path}")
                    return
                
                print(f"找到日誌檔案: {log_path}")
                
                # 創建目標檔案名稱
                filename = f"{station_name}.txt"
                output_path = os.path.join(log_dir, filename)
                
                # 使用 adb pull 下載日誌檔案
                print(f"下載日誌檔案...")
                pull_cmd = adb_prefix + ['pull', log_path, output_path]
                pull_result = subprocess.run(pull_cmd, capture_output=True, text=True)
                
                if "1 file pulled" in pull_result.stderr:
                    print(f"成功! 日誌檔案已保存到: {output_path}")
                else:
                    print(f"錯誤: 無法下載日誌檔案")
                    print(f"錯誤訊息: {pull_result.stderr}")
                
                break
    
    except KeyboardInterrupt:
        print("\n操作被使用者中斷")
    except Exception as e:
        print(f"錯誤: {str(e)}")
    finally:
        # 確保關閉 logcat 進程
        if 'process' in locals():
            process.terminate()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="等待測試完成並拉取日誌檔案")
    parser.add_argument("--SerialNumber",  help="設備序號")
    parser.add_argument("--StationName",  help="測試站名稱")
    parser.add_argument("--device", help="ADB 設備 ID (如果連接了多個設備)")
    
    args = parser.parse_args()
    wait_for_test_completion(args.SerialNumber, args.StationName, args.device)