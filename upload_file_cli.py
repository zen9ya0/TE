import requests
import json
import base64
import argparse
import os
import urllib3

# 關閉 SSL 警告訊息
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def upload_file_to_threat_prevention(api_key, file_path):
    """
    使用 Check Point Threat Prevention API 上傳檔案進行分析
    
    參數:
        api_key (str): API 金鑰
        file_path (str): 要上傳的檔案路徑
    回傳:
        dict: 包含狀態碼、標籤和訊息的字典
    """
    
    # 檢查檔案是否存在
    if not os.path.exists(file_path):
        return {
            "status": {
                "code": 404,
                "label": "FILE_NOT_FOUND",
                "message": f"錯誤: 檔案不存在 - {file_path}"
            }
        }
    
    # API 端點
    url = "https://{TE SERVER}:18194/tecloud/api/v1/file/upload"
    
    # 設定 headers (移除 Content-Type，讓 requests 自動設定)
    headers = {
        'Authorization': api_key
    }
    
    try:
        # 準備檔案
        files = {
            'request': (None, json.dumps({"request": [{
                "features": ["te"]
            }]}), 'application/json'),
            'file': (os.path.basename(file_path), open(file_path, 'rb'), 'application/octet-stream')
        }
        
        # 發送 POST 請求
        response = requests.post(url, headers=headers, files=files, verify=False)
        
        # 檢查回應
        if response.status_code == 200:
            result = response.json()
            # 格式化輸出狀態資訊
            if 'response' in result and 'status' in result['response'][0]:
                status = result['response'][0]['status']
                print(f"\n狀態資訊:")
                print(f"代碼: {status.get('code', 'N/A')}")
                print(f"標籤: {status.get('label', 'N/A')}")
                print(f"訊息: {status.get('message', 'N/A')}\n")
            return result
        else:
            return {
                "status": {
                    "code": response.status_code,
                    "label": "API_ERROR",
                    "message": f"API 錯誤: {response.text}"
                }
            }
            
    except Exception as e:
        return {
            "status": {
                "code": 500,
                "label": "INTERNAL_ERROR",
                "message": f"發生錯誤: {str(e)}"
            }
        }

def query_threat_prevention(api_key, query_id):
    """
    查詢檔案分析結果
    
    參數:
        api_key (str): API 金鑰
        query_id (str): 要查詢的分析 ID 或 SHA1
    回傳:
        dict: 包含查詢結果的字典
    """
    # API 端點
    url = "https://{TE SERVER}:18194/tecloud/api/v1/file/query"
    
    # 設定 headers
    headers = {
        'Authorization': api_key,
        'Content-Type': 'application/json'
    }
    
    try:
        # 準備請求內容
        payload = {
            "request": [{
                "md5": query_id,  # 也可以使用 sha1 或 sha256
                "features": ["te"],
                "te": {
                    "reports": ["full"]
                }
            }]
        }
        
        # 發送 POST 請求
        response = requests.post(url, headers=headers, json=payload, verify=False)
        
        # 檢查回應
        if response.status_code == 200:
            result = response.json()
            if 'response' in result and len(result['response']) > 0:
                response_data = result['response'][0]
                
                # 顯示狀態資訊
                if 'status' in response_data:
                    status = response_data['status']
                    print(f"\n狀態資訊:")
                    print(f"代碼: {status.get('code', 'N/A')}")
                    print(f"標籤: {status.get('label', 'N/A')}")
                    print(f"訊息: {status.get('message', 'N/A')}\n")
                
                # 如果有 TE 分析結果，顯示威脅等級
                if 'te' in response_data:
                    te_data = response_data['te']
                    print(f"分析結果:")
                    print(f"威脅等級: {te_data.get('severity', 'N/A')}")
                    print(f"信心指數: {te_data.get('confidence', 'N/A')}")
                    if 'status' in te_data:
                        print(f"分析狀態: {te_data['status'].get('label', 'N/A')}")
                    print()
            
            return result
        else:
            return {
                "status": {
                    "code": response.status_code,
                    "label": "API_ERROR",
                    "message": f"API 錯誤: {response.text}"
                }
            }
            
    except Exception as e:
        return {
            "status": {
                "code": 500,
                "label": "INTERNAL_ERROR",
                "message": f"發生錯誤: {str(e)}"
            }
        }

def download_file(api_key, download_id, output_dir="."):
    """
    從 Check Point Threat Prevention API 下載檔案
    """
    # 檢查並創建輸出目錄
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # API 端點
    url = f"https://{TE SERVER}:18194/tecloud/api/v1/file/download"
    
    # 設定 headers
    headers = {
        'Authorization': api_key,
        'Content-Type': 'application/json'
    }
    
    try:
        # 準備請求內容
        payload = {
            "request": [{
                "md5": download_id,  # 嘗試使用 md5 作為識別符
                "features": ["te"],
                "te": {
                    "reports": ["full"]
                }
            }]
        }
        
        # 發送 POST 請求
        response = requests.post(url, headers=headers, json=payload, verify=False, stream=True)
        
        # 檢查回應
        if response.status_code == 200:
            # 檢查回應是否為 JSON 錯誤訊息
            try:
                error_json = response.json()
                if 'response' in error_json:
                    response_data = error_json['response'][0]
                    if 'status' in response_data:
                        status = response_data['status']
                        return {
                            "response": [{
                                "status": {
                                    "code": status.get('code', 400),
                                    "label": status.get('label', 'ERROR'),
                                    "message": status.get('message', '未知錯誤')
                                }
                            }]
                        }
            except json.JSONDecodeError:
                # 不是 JSON，表示是實際的檔案內容
                pass
            
            # 從 Content-Disposition 取得檔案名稱，如果沒有就用 download_id
            content_disposition = response.headers.get('content-disposition')
            if content_disposition:
                filename = content_disposition.split('filename=')[-1].strip('"')
            else:
                filename = f"download_{download_id}"
            
            # 組合完整的輸出路徑
            output_path = os.path.join(output_dir, filename)
            
            # 寫入檔案
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            return {
                "response": [{
                    "status": {
                        "code": 200,
                        "label": "DOWNLOAD_SUCCESS",
                        "message": f"檔案已成功下載至: {output_path}"
                    }
                }]
            }
        else:
            return {
                "response": [{
                    "status": {
                        "code": response.status_code,
                        "label": "DOWNLOAD_ERROR",
                        "message": f"下載失敗: {response.text}"
                    }
                }]
            }
            
    except Exception as e:
        return {
            "response": [{
                "status": {
                    "code": 500,
                    "label": "INTERNAL_ERROR",
                    "message": f"發生錯誤: {str(e)}"
                }
            }]
        }

def main():
    # 設定命令列參數
    parser = argparse.ArgumentParser(description='Check Point Threat Prevention API 工具')
    subparsers = parser.add_subparsers(dest='command', help='可用的命令')
    
    # 上傳檔案的子命令
    upload_parser = subparsers.add_parser('upload', help='上傳檔案進行分析')
    upload_parser.add_argument('file_path', help='要分析的檔案路徑')
    
    # 查詢結果的子命令
    query_parser = subparsers.add_parser('query', help='查詢分析結果')
    query_parser.add_argument('query_id', help='要查詢的檔案 MD5/SHA1/SHA256 雜湊值')
    
    # 下載檔案的子命令
    download_parser = subparsers.add_parser('download', help='下載分析報告或其他檔案')
    download_parser.add_argument('download_id', help='要下載的檔案 ID')
    download_parser.add_argument('-o', '--output-dir', help='輸出目錄路徑', default='.')
    
    args = parser.parse_args()
    
    # API 金鑰
    API_KEY = "{YOUR API KEY}"
    
    if args.command == 'upload':
        result = upload_file_to_threat_prevention(API_KEY, args.file_path)
    elif args.command == 'query':
        result = query_threat_prevention(API_KEY, args.query_id)
    elif args.command == 'download':
        result = download_file(API_KEY, args.download_id, args.output_dir)
    else:
        parser.print_help()
        return
    
    # 格式化輸出完整回應
    print(json.dumps(result, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main() 
