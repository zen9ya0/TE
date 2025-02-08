import os
import sys
import email
import argparse
import json
from email import policy
import extract_msg
from datetime import datetime

class MailExtractor:
    def __init__(self, output_dir=None):
        """
        初始化郵件解析器
        
        Args:
            output_dir (str): 輸出目錄路徑，如果未指定則使用當前目錄下的 extracted_files
        """
        if output_dir:
            self.output_dir = output_dir
        else:
            self.output_dir = os.path.join(os.getcwd(), 'extracted_files')
        
        # 確保輸出目錄存在
        os.makedirs(self.output_dir, exist_ok=True)
    
    def detect_file_type(self, file_path):
        """
        檢測郵件檔案類型
        
        Args:
            file_path (str): 郵件檔案路徑
            
        Returns:
            str: 'eml' 或 'msg'
        """
        _, ext = os.path.splitext(file_path.lower())
        if ext == '.eml':
            return 'eml'
        elif ext == '.msg':
            return 'msg'
        else:
            # 嘗試通過檔案內容判斷
            try:
                with open(file_path, 'rb') as f:
                    header = f.read(4096)
                    if b'MIME-Version' in header:
                        return 'eml'
                    elif b'Microsoft Outlook' in header:
                        return 'msg'
            except Exception:
                pass
        return None

    def extract_eml(self, file_path):
        """
        解析 EML 檔案並提取附件
        
        Args:
            file_path (str): EML 檔案路徑
            
        Returns:
            list: 提取的附件資訊列表
        """
        try:
            with open(file_path, 'rb') as f:
                msg = email.message_from_bytes(f.read(), policy=policy.default)
            
            attachments = []
            for part in msg.iter_attachments():
                filename = part.get_filename()
                if filename:
                    # 生成唯一檔名
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    safe_filename = f"{timestamp}_{filename}"
                    output_path = os.path.join(self.output_dir, safe_filename)
                    
                    # 保存附件
                    with open(output_path, 'wb') as f:
                        f.write(part.get_payload(decode=True))
                    
                    attachments.append({
                        'original_name': filename,
                        'saved_path': output_path,
                        'size': os.path.getsize(output_path)
                    })
            
            return {
                'status': 'success',
                'file_type': 'eml',
                'attachments': attachments
            }
        
        except Exception as e:
            return {
                'status': 'error',
                'file_type': 'eml',
                'error_message': str(e),
                'attachments': []
            }

    def extract_msg(self, file_path):
        """
        解析 MSG 檔案並提取附件
        
        Args:
            file_path (str): MSG 檔案路徑
            
        Returns:
            list: 提取的附件資訊列表
        """
        try:
            msg = extract_msg.Message(file_path)
            attachments = []
            
            for attachment in msg.attachments:
                if attachment.longFilename:
                    filename = attachment.longFilename
                else:
                    filename = attachment.shortFilename
                
                if filename:
                    # 生成唯一檔名
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    safe_filename = f"{timestamp}_{filename}"
                    output_path = os.path.join(self.output_dir, safe_filename)
                    
                    # 保存附件
                    with open(output_path, 'wb') as f:
                        f.write(attachment.data)
                    
                    attachments.append({
                        'original_name': filename,
                        'saved_path': output_path,
                        'size': os.path.getsize(output_path)
                    })
            
            msg.close()
            return {
                'status': 'success',
                'file_type': 'msg',
                'attachments': attachments
            }
        
        except Exception as e:
            return {
                'status': 'error',
                'file_type': 'msg',
                'error_message': str(e),
                'attachments': []
            }

    def process_mail(self, file_path):
        """
        處理郵件檔案
        
        Args:
            file_path (str): 郵件檔案路徑
            
        Returns:
            dict: 處理結果和附件資訊
        """
        if not os.path.exists(file_path):
            return {
                'status': 'error',
                'error_message': f"檔案不存在 - {file_path}",
                'file_type': None,
                'attachments': []
            }
        
        file_type = self.detect_file_type(file_path)
        if file_type == 'eml':
            return self.extract_eml(file_path)
        elif file_type == 'msg':
            return self.extract_msg(file_path)
        else:
            return {
                'status': 'error',
                'error_message': f"不支援的檔案格式 - {file_path}",
                'file_type': None,
                'attachments': []
            }

def main():
    parser = argparse.ArgumentParser(description='郵件附件提取工具')
    parser.add_argument('file_path', help='郵件檔案路徑 (EML 或 MSG 格式)')
    parser.add_argument('-o', '--output-dir', help='輸出目錄路徑')
    
    args = parser.parse_args()
    
    extractor = MailExtractor(args.output_dir)
    result = extractor.process_mail(args.file_path)
    
    # 輸出 JSON 格式的結果
    print(json.dumps(result, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main() 