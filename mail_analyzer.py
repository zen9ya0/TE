import os
import json
import argparse
from mail_extractor import MailExtractor
from upload_file_cli import upload_file_to_threat_prevention, query_threat_prevention

class MailAnalyzer:
    def __init__(self, output_dir=None, api_key=None):
        """
        初始化郵件分析器
        
        Args:
            output_dir (str): 輸出目錄路徑
            api_key (str): Threat Prevention API 金鑰
        """
        self.output_dir = output_dir
        self.api_key = api_key or "s2pNbV6HyN6UE26r7nK6Boa8UGmPmCKv"
        self.mail_extractor = MailExtractor(output_dir)

    def analyze_mail(self, mail_path):
        """
        分析郵件檔案及其附件
        
        Args:
            mail_path (str): 郵件檔案路徑
            
        Returns:
            dict: 分析結果
        """
        try:
            # 步驟 1: 提取附件
            extract_result = self.mail_extractor.process_mail(mail_path)
            
            if extract_result['status'] == 'error':
                return {
                    'status': 'error',
                    'error_message': extract_result['error_message'],
                    'file_type': extract_result['file_type'],
                    'analysis_results': []
                }

            # 步驟 2: 分析每個附件
            analysis_results = []
            for attachment in extract_result['attachments']:
                # 上傳附件進行分析
                upload_result = upload_file_to_threat_prevention(
                    self.api_key, 
                    attachment['saved_path']
                )
                
                # 組合分析結果
                analysis_result = {
                    'original_name': attachment['original_name'],
                    'saved_path': attachment['saved_path'],
                    'size': attachment['size'],
                    'analysis': upload_result
                }
                
                # 如果上傳成功且有 MD5，進行查詢
                if ('response' in upload_result and 
                    len(upload_result['response']) > 0 and 
                    'md5' in upload_result['response'][0]):
                    
                    md5 = upload_result['response'][0]['md5']
                    query_result = query_threat_prevention(self.api_key, md5)
                    analysis_result['query_result'] = query_result
                
                analysis_results.append(analysis_result)

            return {
                'status': 'success',
                'file_type': extract_result['file_type'],
                'analysis_results': analysis_results
            }

        except Exception as e:
            return {
                'status': 'error',
                'error_message': str(e),
                'file_type': None,
                'analysis_results': []
            }

def main():
    parser = argparse.ArgumentParser(description='郵件附件分析工具')
    parser.add_argument('mail_path', help='郵件檔案路徑 (EML 或 MSG 格式)')
    parser.add_argument('-o', '--output-dir', help='輸出目錄路徑')
    parser.add_argument('-k', '--api-key', help='Threat Prevention API 金鑰')
    
    args = parser.parse_args()
    
    analyzer = MailAnalyzer(args.output_dir, args.api_key)
    result = analyzer.analyze_mail(args.mail_path)
    
    # 輸出 JSON 格式的結果
    print(json.dumps(result, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main() 